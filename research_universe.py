"""Explicit Phase 4 universe capture and offline coverage audit; no model fitting."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time

from dataset_cli import capture
from dataset_features import build_features
from datasets import DatasetStore
from stock_provider import StockDataError
from stock_service import StockService

UNIVERSE = (("stock", "MSFT"), ("stock", "JNJ"), ("stock", "JPM"),
            ("stock", "XOM"), ("etf", "QQQ"), ("etf", "IWM"),
            ("etf", "DIA"), ("stock", "AAPL"), ("stock", "IBM"), ("etf", "SPY"))


def resolve(catalog, kind, symbol):
    matches = [a for a in catalog if a['asset_class'] == kind and a['symbol'] == symbol]
    if len(matches) != 1:
        raise ValueError('Listing missing or ambiguous; no substitution permitted')
    return matches[0]['id']


def audit(store, identity):
    source = store.load(identity)
    if source['kind'] != 'snapshot':
        raise ValueError('Expected a snapshot')
    features = build_features(source, identity, horizon=5)
    feature_id = store.save(features)
    eligible = [r for r in features['rows'] if r['supervised_ready']]
    blocks = []
    for year in range(2021, 2027):
        start, end = f'{year}-01-01', f'{year}-12-31'
        test = [r for r in eligible if start <= r['session'] <= end and r['label']['end_session'] <= end]
        # Match the protocol's purge against the first eligible feature date.
        boundary = test[0]['session'] if test else start
        train = [r for r in eligible if r['session'] < start and r['label']['end_session'] < boundary]
        partial = year == 2026
        ready = len(train) >= 500 and len(test) >= (1 if partial else 100)
        blocks.append(dict(year=year, partial=partial, training_rows=len(train),
                           completed_test_targets=len(test), eligible=ready,
                           first_test_session=test[0]['session'] if test else None,
                           last_target_session=test[-1]['label']['end_session'] if test else None))
    rows = source['observations']
    missing = source['quality']['missing_sessions']
    return dict(status='audited', asset=source['asset'], snapshot_id=identity, feature_id=feature_id,
                captured_at_utc=source['captured_at_utc'], collection=source.get('collection'),
                expected_sessions=len(source['expected_sessions']), observations=len(rows),
                observed_start=rows[0]['date'], observed_end=rows[-1]['date'],
                missing_sessions=missing, unknown_volume=source['quality']['unknown_volume'],
                supervised_rows=len(eligible), blocks=blocks, limitations=source['limitations'])


def run(store, *, collect=False, service=None, now=None, pause=time.sleep, progress=None):
    now = now or datetime.now(timezone.utc)
    report = dict(protocol='PHASE4_NEXT_PROTOCOL.md', generated_at_utc=now.isoformat(),
                  mode='live_capture' if collect else 'offline_audit', assets=[],
                  limitations=['Selected current listings have survivorship and selection bias.',
                               'Coverage eligibility is not evidence of predictive accuracy.',
                               'No models fitted; no accuracy or calibrated probabilities produced.'])
    catalog = None
    if collect:
        service = service or StockService()
        try:
            catalog_result = service.catalog(now)
            if catalog_result['stale']:
                raise ValueError('Fresh catalog required')
            catalog = catalog_result['assets']
        except StockDataError as error:
            report['catalog_error'] = error.code
        except ValueError:
            report['catalog_error'] = 'catalog_invalid'
    saved = []
    if not collect:
        for entry in store.listing():
            if entry['kind'] == 'snapshot':
                saved.append((entry['id'], store.load(entry['id'])))
    stopped = False
    for index, (kind, symbol) in enumerate(UNIVERSE):
        item = dict(symbol=symbol, asset_class=kind)
        try:
            if collect:
                if catalog is None or stopped:
                    item['status'] = 'not_attempted'
                    item['reason'] = report.get('catalog_error', 'quota_stop')
                else:
                    # Conservative pacing; no retries or account upgrades.
                    pause(10)
                    listing = resolve(catalog, kind, symbol)
                    source = capture(kind, listing, 3653, now=now, stocks=service)
                    item.update(audit(store, store.save(source)))
            else:
                matches = [(key, s) for key, s in saved if s['asset']['symbol'] == symbol
                           and s['asset']['asset_class'] == kind and s['asset']['provider'] == 'twelvedata']
                identities = {s['asset']['id'] for _, s in matches}
                if len(identities) > 1:
                    raise ValueError('Saved listings ambiguous')
                if not matches:
                    item['status'] = 'missing_snapshot'
                else:
                    key, _ = max(matches, key=lambda pair: (pair[1]['captured_at_utc'], pair[0]))
                    item.update(audit(store, key))
        except StockDataError as error:
            item.update(status='capture_failed', reason=error.code)
            if error.code in ('stock_quota', 'stock_access', 'stock_setup_required'):
                stopped = True
        except (ValueError, KeyError, TypeError):
            item.update(status='invalid_or_ambiguous', reason='Validation failed; no substitution or cached fallback')
        report['assets'].append(item)
        if progress:
            progress(f'{index + 1}/{len(UNIVERSE)} {symbol}: {item["status"]}')
    report['all_assets_audited'] = all(a['status'] == 'audited' for a in report['assets'])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', help='Separate research SQLite path')
    parser.add_argument('--capture', action='store_true', help='Explicitly request live provider history for the fixed universe')
    parser.add_argument('--report', help='Write JSON audit to this path (otherwise print it)')
    args = parser.parse_args(argv)
    try:
        if args.capture:
            from local_config import load_local_config
            load_local_config()
        store = DatasetStore(args.store) if args.store else DatasetStore()
        result = run(store, collect=args.capture, progress=print if args.report else None)
        payload = json.dumps(result, indent=2, allow_nan=False)
        if args.report:
            Path(args.report).write_text(payload + '\n', encoding='utf-8')
        else:
            print(payload)
        return 0 if result['all_assets_audited'] else 1
    except (ValueError, OSError, sqlite3.Error):
        print('Research audit failed. Check local configuration, store integrity and report path. No provider details printed.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

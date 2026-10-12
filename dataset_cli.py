"""Explicit research-data commands. Never reads holdings or calls an LLM."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import re
import sqlite3
import pandas as pd
import exchange_calendars
import api
from assets import Asset, crypto_asset
from datasets import DatasetStore, snapshot
from dataset_features import build_features
from history_window import select_daily_window
from stock_service import StockService, session_window
from stock_provider import StockDataError


def capture(asset_class, symbol, days, *, now=None, stocks=None, history=None):
    maximum = 364 if asset_class == 'crypto' else 3660
    if type(days) is not int or not 35 <= days <= maximum:
        raise ValueError(f'Choose 35 to {maximum} calendar days')
    now = now or datetime.now(timezone.utc)
    if asset_class == 'crypto':
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', symbol):
            raise ValueError('Invalid CoinGecko ID')
        asset = crypto_asset(dict(id=symbol, name=symbol))
        # Keep the unfinished current UTC date out of the training snapshot.
        frame = (history or api.fetch_history)(symbol, days + 1, persist=False)
        frame, coverage = select_daily_window(frame, days, now=now - timedelta(days=1))
        sessions = pd.date_range(coverage['expected_start'], coverage['expected_end']).strftime('%Y-%m-%d').tolist()
        rows = []
        for day, row in frame.iterrows():
            volume = row.get('volume')
            if volume is not None and pd.isna(volume):
                volume = None
            rows.append(dict(date=day.date().isoformat(), price=row['price'], volume=volume))
        result = snapshot(asset, rows, sessions, now, adjustment='provider_daily_sample',
                        price_definition='CoinGecko UTC-date daily sample; not guaranteed exchange closing price. Volume not used as a feature.')
        result['collection'] = dict(adapter_version='coingecko-daily-v1', requested_calendar_days=days,
                                    provider_request_days=days + 1, calendar='UTC daily; current date excluded')
        return result
    if asset_class not in ('stock', 'etf'):
        raise ValueError('Unsupported asset class')
    service = stocks or StockService()
    result = service.research(symbol, days, now)
    identity = dict(result['asset']); identity.pop('id')
    asset = Asset(**identity)
    if asset.asset_class != asset_class:
        raise ValueError('Asset class does not match selected listing')
    _, _, sessions = session_window(days, now)
    rows = [dict(date=b['date'], price=b['close'], volume=b['volume'], open=b['open'], high=b['high'], low=b['low']) for b in result['bars']]
    result = snapshot(asset, rows, sessions, now, adjustment='splits',
                    price_definition='Twelve Data regular-session split-adjusted close; excludes dividends.')
    result['collection'] = dict(adapter_version='twelvedata-daily-v1', requested_calendar_days=days,
        calendar='XNYS regular completed sessions', calendar_version=exchange_calendars.__version__)
    return result


def main(argv=None):
    from local_config import load_local_config
    load_local_config()
    parser = argparse.ArgumentParser(description='Versioned datasets and causal features for local research')
    parser.add_argument('--store', help='Optional separate research SQLite path')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list', help='List saved artifact IDs without provider requests')
    show = commands.add_parser('show', help='Inspect an artifact manifest and quality summary')
    show.add_argument('id')
    fetch = commands.add_parser('capture', help='Fetch and save one normalized historical snapshot')
    fetch.add_argument('asset_class', choices=['crypto', 'stock', 'etf'])
    fetch.add_argument('asset', help='CoinGecko ID for crypto; exact catalog asset ID for stocks/ETFs')
    fetch.add_argument('--days', type=int, default=180)
    features = commands.add_parser('features', help='Build an offline feature/label artifact from a saved snapshot')
    features.add_argument('id')
    features.add_argument('--horizon', type=int, default=5)
    features.add_argument('--benchmark', help='Optional saved benchmark snapshot ID with matching timezone/currency/adjustment')
    args = parser.parse_args(argv)
    store = DatasetStore(args.store) if args.store else DatasetStore()
    try:
        if args.command == 'list':
            result = store.listing()
        elif args.command == 'capture':
            artifact = capture(args.asset_class, args.asset, args.days)
            result = dict(id=store.save(artifact), asset=artifact['asset'], quality=artifact['quality'], observations=len(artifact['observations']))
        elif args.command == 'features':
            artifact = build_features(store.load(args.id), args.id, horizon=args.horizon,
                benchmark=store.load(args.benchmark) if args.benchmark else None, benchmark_id=args.benchmark)
            result = dict(id=store.save(artifact), source_id=args.id, quality=artifact['quality'])
        else:
            artifact = store.load(args.id)
            result = {k:v for k,v in artifact.items() if k not in ('observations', 'rows', 'expected_sessions')}
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error, api.UpstreamError, StockDataError):
        # Never print provider exceptions that could contain request credentials.
        print('Dataset command failed. Check the asset ID, provider setup/access, data coverage and store path. No successful artifact is reported.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

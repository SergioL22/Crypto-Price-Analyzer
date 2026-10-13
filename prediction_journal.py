"""Manual prospective predictions and outcomes in an append-only local journal."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import json
import hashlib
import exchange_calendars as calendars
from dataset_features import build_features
from datasets import canonical
from modeling import digest, fit, predict, metrics
from stock_service import session_window

DEFAULT_JOURNAL = Path(__file__).with_name('prediction_journal.db')


class Journal:
    def __init__(self, path=DEFAULT_JOURNAL):
        self.path = Path(path)

    def events(self):
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute('SELECT id, previous_id, payload FROM events ORDER BY sequence').fetchall()
        return self._verified(rows)

    @staticmethod
    def _verified(rows):
        events, previous = [], None
        for identity, parent, payload in rows:
            value = json.loads(payload)
            if parent != previous or digest(dict(previous_id=parent, event=value)) != identity:
                raise ValueError('Journal integrity verification failed')
            events.append(dict(id=identity, event=value))
            previous = identity
        return events

    def append(self, event):
        # One writer transaction covers verification and append; no overwrite API.
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, previous_id TEXT, payload TEXT NOT NULL)')
            db.execute("CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'Append-only journal'); END")
            db.execute("CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'Append-only journal'); END")
            existing = self._verified(db.execute('SELECT id, previous_id, payload FROM events ORDER BY sequence').fetchall())
            if event['kind'] == 'outcome':
                if any(e['event']['kind'] == 'outcome' and e['event']['prediction_id'] == event['prediction_id'] for e in existing):
                    raise ValueError('Outcome already recorded')
                if not any(e['id'] == event['prediction_id'] and e['event']['kind'] == 'prediction' for e in existing):
                    raise ValueError('Prediction not found')
            elif event['kind'] == 'prediction':
                if any(e['event']['kind'] == 'prediction' and e['event']['asset']['id'] == event['asset']['id']
                       and e['event']['as_of_session'] == event['as_of_session'] for e in existing):
                    raise ValueError('A prediction for this asset/session already exists')
            else:
                raise ValueError('Invalid journal event')
            parent = existing[-1]['id'] if existing else None
            identity = digest(dict(previous_id=parent, event=event))
            db.execute('INSERT INTO events(id,previous_id,payload) VALUES (?,?,?)', (identity, parent, canonical(event)))
        return identity


def utc_now(now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('UTC issuance time required')
    return now.astimezone(timezone.utc)


def fresh_source(source, now):
    if source['kind'] != 'snapshot' or source['asset']['asset_class'] not in ('stock', 'etf'):
        raise ValueError('Stock/ETF snapshot required')
    captured = datetime.fromisoformat(source['captured_at_utc'])
    if captured > now or now-captured > timedelta(hours=24):
        raise ValueError('Snapshot capture is stale or in the future')
    _, _, completed = session_window(35, now)
    if not completed or source['observations'][-1]['date'] != completed[-1] or source['quality']['missing_sessions']:
        raise ValueError('Reject stale/incomplete input; capture the latest completed session')
    close=calendars.get_calendar('XNYS').session_close(completed[-1]).to_pydatetime()
    if captured < close:
        raise ValueError('Snapshot predates the completed session')
    return completed[-1]


def issue(store, journal, snapshot_id, *, now=None):
    now = utc_now(now)
    source = store.load(snapshot_id)
    as_of = fresh_source(source, now)
    features = build_features(source, snapshot_id, horizon=5)
    last = features['rows'][-1]
    if last['session'] != as_of or not last['feature_ready']:
        raise ValueError('Latest features unavailable')
    train = [r for r in features['rows'] if r['supervised_ready'] and r['label']['end_session'] <= as_of]
    if len(train) < 500:
        raise ValueError('At least 500 completed training targets required')
    model = fit(train)
    feature_id = store.save(features)
    calendar = calendars.get_calendar('XNYS', start=as_of, end=str((now+timedelta(days=30)).date()))
    future = calendar.sessions_in_range(as_of, str((now+timedelta(days=30)).date())).strftime('%Y-%m-%d').tolist()[1:6]
    if len(future) != 5:
        raise ValueError('Target calendar unavailable')
    probability = float(predict(model, [last])[0])
    event = dict(kind='prediction', issued_at_utc=now.isoformat(), asset=source['asset'],
                 source_id=snapshot_id, feature_id=feature_id, feature_row_sha256=digest(last['features']),
                 model_sha256=digest(model), model=model, as_of_session=as_of,
                 as_of_price=source['observations'][-1]['price'], horizon_sessions=5,
                 target_sessions=future, probability_up=probability,
                 direction='up' if probability >= .5 else 'down_or_flat',
                 training_rows=len(train), prospective=True, calibrated=False,
                 baseline_probabilities=dict(always_up=1.0,training_prior=model['training_positive_rate'],momentum=float(last['features']['return_5']>0)),
                 protocol_sha256=hashlib.sha256(Path(__file__).with_name('PHASE4_NEXT_PROTOCOL.md').read_bytes()).hexdigest(),
                 implementation_sha256=hashlib.sha256(b''.join(Path(__file__).with_name(name).read_bytes() for name in ('prediction_journal.py','modeling.py','dataset_features.py','analysis.py'))).hexdigest(),
                 limitations=['Research only; no recommendation or probability calibration.',
                              'Five-session close-to-close direction excludes dividends and trading costs.'])
    return dict(id=journal.append(event), event=event)


def settle(store, journal, prediction_id, snapshot_id, *, now=None):
    now = utc_now(now)
    found = [e for e in journal.events() if e['id'] == prediction_id and e['event']['kind'] == 'prediction']
    if len(found) != 1:
        raise ValueError('Prediction not found')
    prediction = found[0]['event']
    source = store.load(snapshot_id)
    if source['asset'] != prediction['asset'] or source['adjustment'] != 'splits':
        raise ValueError('Outcome identity/adjustment mismatch')
    if datetime.fromisoformat(source['captured_at_utc']) > now or datetime.fromisoformat(prediction['issued_at_utc']) >= now:
        raise ValueError('Invalid outcome timing')
    _, _, completed = session_window(35, now)
    if prediction['target_sessions'][-1] > completed[-1]:
        raise ValueError('Target has not completed')
    if datetime.fromisoformat(source['captured_at_utc']) < calendars.get_calendar('XNYS').session_close(prediction['target_sessions'][-1]).to_pydatetime():
        raise ValueError('Outcome snapshot predates target completion')
    observations = {r['date']: r['price'] for r in source['observations']}
    required = [prediction['as_of_session']] + prediction['target_sessions']
    if any(d not in observations for d in required):
        raise ValueError('Incomplete outcome window')
    if observations[prediction['as_of_session']] != prediction['as_of_price']:
        raise ValueError('Origin price revised; outcome requires review, not automatic scoring')
    change = observations[required[-1]]/prediction['as_of_price']-1
    outcome = dict(kind='outcome', prediction_id=prediction_id, recorded_at_utc=now.isoformat(),
                   source_id=snapshot_id, end_session=required[-1], forward_return=change,
                   up=int(change > 0), correct=(prediction['probability_up'] >= .5) == (change > 0))
    return dict(id=journal.append(outcome), event=outcome)


def summary(journal):
    events = journal.events()
    predictions = {e['id']: e['event'] for e in events if e['event']['kind'] == 'prediction'}
    outcomes = [e['event'] for e in events if e['event']['kind'] == 'outcome']
    scores = metrics([e['up'] for e in outcomes], [predictions[e['prediction_id']]['probability_up'] for e in outcomes]) if outcomes else None
    baselines={name:metrics([e['up'] for e in outcomes],[predictions[e['prediction_id']]['baseline_probabilities'][name] for e in outcomes]) for name in ('always_up','training_prior','momentum')} if outcomes else {}
    by_asset=[]
    for asset_id in sorted({p['asset']['id'] for p in predictions.values()}):
        matched=[e for e in outcomes if predictions[e['prediction_id']]['asset']['id']==asset_id]
        by_asset.append(dict(asset_id=asset_id,completed_outcomes=len(matched),
            metrics=metrics([e['up'] for e in matched],[predictions[e['prediction_id']]['probability_up'] for e in matched]) if matched else None))
    calibration=[]
    for index,lower in enumerate((0,.2,.4,.6,.8)):
        matched=[e for e in outcomes if min(4,int(predictions[e['prediction_id']]['probability_up']*5))==index]
        calibration.append(dict(lower=lower,upper=round(lower+.2,1),count=len(matched),
            mean_probability=sum(predictions[e['prediction_id']]['probability_up'] for e in matched)/len(matched) if matched else None,
            observed_up_rate=sum(e['up'] for e in matched)/len(matched) if matched else None))
    return dict(predictions=len(predictions), completed_outcomes=len(outcomes), pending=len(predictions)-len(outcomes),
                metrics=scores, baseline_metrics=baselines, by_asset=by_asset, calibration_bins=calibration, promoted=False, calibrated=False,
                limitations=['Fresh outcomes count only after issuance and completion.',
                             'Overlapping outcomes and selected assets are dependent; small samples are inconclusive.',
                             'No automatic promotion to recommendations.'])

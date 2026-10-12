"""Immutable, content-addressed research artifacts in a separate SQLite store."""
from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from assets import Asset

SCHEMA_VERSION = 1
DEFAULT_STORE = Path(__file__).resolve().parent / 'research_datasets.db'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def valid_dates(values):
    if not isinstance(values, list) or not values:
        raise ValueError('Expected a nonempty date list')
    if any(not isinstance(v, str) or date.fromisoformat(v).isoformat() != v for v in values):
        raise ValueError('Invalid session date')
    if values != sorted(set(values)):
        raise ValueError('Session dates must be unique and sorted')


def snapshot(asset, rows, sessions, captured_at, *, adjustment, price_definition):
    """A present-day provider snapshot, never a claimed historical vintage."""
    if not isinstance(asset, Asset):
        raise ValueError('An explicit asset identity is required')
    if captured_at.tzinfo is None:
        raise ValueError('Capture time must be timezone-aware')
    valid_dates(sessions)
    if not isinstance(rows, list) or not rows:
        raise ValueError('No observations to save')
    valid_dates([r['date'] for r in rows])
    if not set(r['date'] for r in rows) <= set(sessions):
        raise ValueError('Observed dates must belong to the expected session window')
    if adjustment != ('provider_daily_sample' if asset.asset_class == 'crypto' else 'splits'):
        raise ValueError('Adjustment basis does not match asset class')
    clean = []
    for row in rows:
        price, volume = row['price'], row.get('volume')
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
            raise ValueError('Prices must be positive and finite')
        if volume is not None and (isinstance(volume, bool) or not isinstance(volume, (int, float)) or not math.isfinite(volume) or volume < 0):
            raise ValueError('Volume must be finite and nonnegative or unknown')
        normalized = dict(date=row['date'], price=float(price), volume=None if volume is None else float(volume))
        if any(key in row for key in ('open', 'high', 'low')):
            for key in ('open', 'high', 'low'):
                value = row.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                    raise ValueError('Invalid OHLC values')
                normalized[key] = float(value)
            if not normalized['low'] <= min(normalized['open'], price) <= max(normalized['open'], price) <= normalized['high']:
                raise ValueError('Inconsistent OHLC values')
        clean.append(normalized)
    observed = {r['date'] for r in clean}
    return dict(kind='snapshot', schema_version=SCHEMA_VERSION, asset=asset.public(),
        captured_at_utc=captured_at.astimezone(timezone.utc).isoformat(), adjustment=adjustment,
        price_definition=price_definition, expected_sessions=sessions, observations=clean,
        quality=dict(missing_sessions=[s for s in sessions if s not in observed],
                     unknown_volume=sum(r['volume'] is None for r in clean)),
        historical_vintage_available=False,
        limitations=['Provider data may have been revised before capture; this is not a historical point-in-time archive.',
                     'No guaranteed delisted coverage or historical universe membership.',
                     'No dividend-inclusive total return or transaction costs.'])


class DatasetStore:
    """Inserts only; a hash covers the complete serialized payload."""
    def __init__(self, path=DEFAULT_STORE):
        self.path = Path(path)

    def save(self, artifact):
        if artifact.get('kind') not in ('snapshot', 'features') or artifact.get('schema_version') != SCHEMA_VERSION:
            raise ValueError('Unsupported artifact schema')
        payload = canonical(artifact)
        identity = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO artifacts VALUES (?,?,?)', (identity, artifact['kind'], payload))
            stored = db.execute('SELECT payload FROM artifacts WHERE id=?', (identity,)).fetchone()[0]
            if stored != payload:
                raise ValueError('Stored artifact failed integrity verification')
        return identity

    def load(self, identity):
        if not isinstance(identity, str) or not re.fullmatch('[a-f0-9]{64}', identity):
            raise ValueError('Invalid artifact ID')
        if not self.path.exists():
            raise ValueError('Dataset store does not exist')
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT payload FROM artifacts WHERE id=?', (identity,)).fetchone()
        if row is None:
            raise ValueError('Artifact not found')
        if hashlib.sha256(row[0].encode('utf-8')).hexdigest() != identity:
            raise ValueError('Stored artifact failed integrity verification')
        result = json.loads(row[0])
        if result.get('schema_version') != SCHEMA_VERSION:
            raise ValueError('Unsupported artifact schema')
        return result

    def listing(self):
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(self.path)) as db:
            return [dict(id=r[0], kind=r[1]) for r in db.execute('SELECT id,kind FROM artifacts ORDER BY rowid')]

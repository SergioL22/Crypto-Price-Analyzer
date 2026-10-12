"""CLI-compatible alert configuration and dashboard-only trigger history."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3


class AlertConflict(ValueError):
    pass


class AlertStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else Path(__file__).resolve().parent / 'crypto_data.db'

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                conn.execute('''CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY, coin_id TEXT NOT NULL, alert_type TEXT NOT NULL,
                    threshold REAL NOT NULL, direction TEXT NOT NULL, is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP, last_triggered TEXT)''')
                conn.execute('''CREATE TABLE IF NOT EXISTS dashboard_alert_state (
                    alert_id INTEGER PRIMARY KEY, signature TEXT NOT NULL, matching INTEGER NOT NULL)''')
                conn.execute('''CREATE TABLE IF NOT EXISTS dashboard_alert_events (
                    id INTEGER PRIMARY KEY, alert_id INTEGER, coin_id TEXT NOT NULL, alert_type TEXT NOT NULL,
                    threshold REAL NOT NULL, direction TEXT NOT NULL, value REAL NOT NULL,
                    checked_at TEXT NOT NULL, observed_at TEXT NOT NULL)''')
            yield conn
        finally:
            conn.close()

    def listing(self):
        with self.connection() as conn:
            alerts = [dict(row) for row in conn.execute('SELECT * FROM alerts ORDER BY id')]
            if len(alerts) > 100:
                raise AlertConflict('Too many alerts; manage the list in the CLI.')
            events = [dict(row) for row in conn.execute('SELECT * FROM dashboard_alert_events ORDER BY id DESC LIMIT 100')]
            return dict(alerts=alerts, events=events)

    def create(self, body):
        with self.connection() as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT count(*) FROM alerts').fetchone()[0] >= 100:
                raise AlertConflict('The limit is 100 saved alerts.')
            if conn.execute('SELECT count(*) FROM alerts WHERE is_active=1').fetchone()[0] >= 20:
                raise AlertConflict('Pause an alert first; the limit is 20 active alerts.')
            duplicate = conn.execute('SELECT id FROM alerts WHERE coin_id=? AND alert_type=? AND threshold=? AND direction=?',
                                     (body.coin_id, body.alert_type, body.threshold, body.direction)).fetchone()
            if duplicate:
                raise AlertConflict('This alert already exists. Resume it if paused.')
            conn.execute('INSERT INTO alerts (coin_id,alert_type,threshold,direction) VALUES (?,?,?,?)',
                         (body.coin_id, body.alert_type, body.threshold, body.direction))
        return self.listing()

    def change(self, alert_id, active=None):
        with self.connection() as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone()
            if row is None:
                raise AlertConflict('Alert no longer exists. Reload the list.')
            if active is None:
                conn.execute('DELETE FROM alerts WHERE id=?', (alert_id,))
                conn.execute('DELETE FROM dashboard_alert_state WHERE alert_id=?', (alert_id,))
            else:
                if active and not row['is_active'] and conn.execute('SELECT count(*) FROM alerts WHERE is_active=1').fetchone()[0] >= 20:
                    raise AlertConflict('Pause an alert first; the limit is 20 active alerts.')
                conn.execute('UPDATE alerts SET is_active=? WHERE id=?', (int(active), alert_id))
                # Retain state across pauses: resume does not duplicate an existing trigger.
        return self.listing()

    def record(self, alert, value, checked_at, observed_at):
        matching = value > alert['threshold'] if alert['direction'] == 'above' else value < alert['threshold']
        keys = ('coin_id', 'alert_type', 'threshold', 'direction', 'created_at')
        signature = json.dumps([alert[key] for key in keys])
        with self.connection() as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            current = conn.execute('SELECT * FROM alerts WHERE id=?', (alert['id'],)).fetchone()
            if current is None or not current['is_active'] or any(current[key] != alert[key] for key in keys):
                return 'changed'
            previous = conn.execute('SELECT * FROM dashboard_alert_state WHERE alert_id=?', (alert['id'],)).fetchone()
            new_match = matching and (previous is None or previous['signature'] != signature or not previous['matching'])
            conn.execute('INSERT OR REPLACE INTO dashboard_alert_state VALUES (?,?,?)', (alert['id'], signature, int(matching)))
            if new_match:
                conn.execute('INSERT INTO dashboard_alert_events (alert_id,coin_id,alert_type,threshold,direction,value,checked_at,observed_at) VALUES (?,?,?,?,?,?,?,?)',
                             (alert['id'], alert['coin_id'], alert['alert_type'], alert['threshold'], alert['direction'], value, checked_at, observed_at))
                conn.execute('UPDATE alerts SET last_triggered=? WHERE id=?', (checked_at, alert['id']))
                conn.execute('DELETE FROM dashboard_alert_events WHERE id NOT IN (SELECT id FROM dashboard_alert_events ORDER BY id DESC LIMIT 1000)')
        return 'triggered' if new_match else 'already_matching' if matching else 'not_matching'

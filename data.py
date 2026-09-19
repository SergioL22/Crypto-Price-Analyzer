"""SQLite and file persistence. Paths remain relative to the working directory."""
from contextlib import closing
import json
import os
import sqlite3
from datetime import datetime
from typing import Optional
import pandas as pd

DB_FILE = "crypto_data.db"
PORTFOLIO_FILE = "portfolio.json"
ALERTS_LOG_FILE = "alerts.log"


def init_database() -> None:
    """Initialize SQLite database for data persistence."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create price history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY,
            coin_id TEXT NOT NULL,
            date TEXT NOT NULL,
            price REAL NOT NULL,
            volume REAL,
            market_cap REAL,
            timestamp INTEGER,
            UNIQUE(coin_id, date)
        )
    ''')

    # Create alerts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY,
            coin_id TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            threshold REAL NOT NULL,
            direction TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_triggered TEXT
        )
    ''')

    # Create backtest results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY,
            coin_id TEXT NOT NULL,
            strategy TEXT NOT NULL,
            period_days INTEGER NOT NULL,
            total_trades INTEGER,
            winning_trades INTEGER,
            losing_trades INTEGER,
            win_rate REAL,
            avg_return REAL,
            max_drawdown REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


def save_price_data(coin_id: str, df: pd.DataFrame) -> None:
    """Save price data to database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR REPLACE INTO price_history
            (coin_id, date, price, volume, market_cap, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            coin_id,
            row['date'].isoformat(),
            row['price'],
            row.get('volume'),
            None,  # market_cap not available in current data
            int(pd.Timestamp(row['date']).timestamp())
        ))

    conn.commit()
    conn.close()


def load_price_data(coin_id: str, days: int = 30) -> Optional[pd.DataFrame]:
    """Load price data from database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Stored dates are date-only strings ("YYYY-MM-DD"). Comparing against a
    # cutoff that includes a time-of-day component (the old behavior) silently
    # dropped the earliest requested day, since the string "2026-01-01" sorts
    # before "2026-01-01T00:00:00" in a plain text comparison.
    cutoff_date = (datetime.now() - pd.Timedelta(days=days)).date().isoformat()

    cursor.execute('''
        SELECT date, price, volume FROM price_history
        WHERE coin_id = ? AND date >= ?
        ORDER BY date ASC
    ''', (coin_id, cutoff_date))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=['date', 'price', 'volume'])
    df['date'] = pd.to_datetime(df['date'])
    return df.set_index('date')


def save_alert(coin_id: str, alert_type: str, threshold: float, direction: str) -> None:
    """Save alert configuration to database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO alerts (coin_id, alert_type, threshold, direction)
        VALUES (?, ?, ?, ?)
    ''', (coin_id, alert_type, threshold, direction))

    conn.commit()
    conn.close()


def load_alerts(active_only: bool = False) -> list[dict]:
    """Load alerts from database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    query = 'SELECT * FROM alerts'
    if active_only:
        query += ' WHERE is_active = 1'
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    alerts = []
    for row in rows:
        alerts.append({
            'id': row[0],
            'coin_id': row[1],
            'alert_type': row[2],
            'threshold': row[3],
            'direction': row[4],
            'is_active': row[5],
            'created_at': row[6],
            'last_triggered': row[7]
        })
    return alerts


def delete_alert(alert_id: int) -> None:
    """Permanently delete an alert."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()


def toggle_alert(alert_id: int) -> bool | None:
    """Flip an alert's active state. Returns new state, or None if not found."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return None
    new_state = 0 if row[0] else 1
    cursor.execute("UPDATE alerts SET is_active = ? WHERE id = ?", (new_state, alert_id))
    conn.commit()
    conn.close()
    return bool(new_state)


def load_portfolio() -> dict:
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}


def save_portfolio(portfolio: dict) -> None:
    """Write portfolio.json atomically so a crash mid-write can't corrupt it."""
    tmp_path = f"{PORTFOLIO_FILE}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(portfolio, file, indent=2)
    os.replace(tmp_path, PORTFOLIO_FILE)


def save_backtest_result(result: dict) -> None:
    """Persist summary metrics from a completed backtest."""
    with closing(sqlite3.connect(DB_FILE)) as conn, conn:
        conn.execute("""
            INSERT INTO backtest_results
            (coin_id, strategy, period_days, total_trades, winning_trades,
             losing_trades, win_rate, avg_return, max_drawdown)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tuple(result[key] for key in (
            'coin_id', 'strategy', 'period_days', 'total_trades', 'winning_trades',
            'losing_trades', 'win_rate', 'avg_return', 'max_drawdown')))



def mark_alert_triggered(alert_id: int) -> None:
    """Record the last trigger time for a price alert."""
    with closing(sqlite3.connect(DB_FILE)) as conn, conn:
        conn.execute('UPDATE alerts SET last_triggered = ? WHERE id = ?',
                     (datetime.now().isoformat(), alert_id))


def append_alert_log(message: str) -> None:
    with open(ALERTS_LOG_FILE, 'a', encoding='utf-8') as file:
        file.write(message + '\n')


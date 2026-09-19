"""Regression tests for the accuracy/reliability fixes made to main.py.

Each test class documents the bug it guards against so a future change that
reintroduces the bug fails loudly here instead of surfacing as a bad
recommendation or a crashed session.
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import api
import data
import analysis
import ui
from api import _get
from data import load_price_data, save_price_data, init_database, save_portfolio, load_portfolio
from analysis import compute_rsi, find_support_resistance, detect_head_and_shoulders, detect_double_top_bottom, backtest_strategy
from ui import check_alerts



def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


# ── compute_rsi: Wilder smoothing + the all-gains NaN bug ────────────────────

class TestRsiWilderSmoothing:
    def test_all_gains_returns_100_not_nan(self):
        # Previously: loss.replace(0, nan) turned an all-gains series into
        # rs = NaN -> rsi = NaN, silently returned instead of the correct 100.
        prices = _series(list(range(1, 40)))  # strictly increasing
        rsi = compute_rsi(prices)
        assert rsi == 100.0

    def test_all_losses_returns_0(self):
        prices = _series(list(range(40, 1, -1)))
        rsi = compute_rsi(prices)
        assert rsi == 0.0

    def test_too_short_returns_neutral_50_not_crash(self):
        rsi = compute_rsi(_series([100.0, 101.0]))
        assert rsi == 50.0

    def test_uses_exponential_not_simple_rolling_mean(self):
        # A late, large jump should move Wilder-smoothed (EMA-style) RSI more
        # than it would move a simple-rolling-mean RSI, because the recursive
        # smoothing keeps some weight on the most recent bar indefinitely
        # while a plain rolling mean would too -- so instead we directly check
        # the RSI is NOT computed via a plain rolling mean of clipped deltas
        # (the old formula), by comparing against that formula on a series
        # where they diverge.
        prices = _series([100 + (i % 3) * 2 - 1 for i in range(40)])
        delta = prices.diff()
        old_gain = delta.clip(lower=0).rolling(14).mean()
        old_loss = (-delta.clip(upper=0)).rolling(14).mean()
        old_rs = old_gain / old_loss.replace(0, float("nan"))
        old_rsi = float((100 - (100 / (1 + old_rs))).iloc[-1])

        new_rsi = compute_rsi(prices)
        assert abs(new_rsi - old_rsi) > 0.01


# ── zigzag pivot filter: false pattern detections on noisy data ─────────────

class TestZigzagNoiseFiltering:
    def test_small_daily_noise_has_no_support_resistance(self):
        # +/-1% day-to-day noise around a flat price should not register as
        # meaningful swing highs/lows (the old single-bar peak check would
        # flag almost every wiggle here).
        import random
        random.seed(7)
        prices = _series([100 * (1 + random.uniform(-0.01, 0.01)) for _ in range(60)])
        support, resistance = find_support_resistance(prices, threshold_pct=3.0)
        assert support == []
        assert resistance == []

    def test_small_daily_noise_gives_no_head_and_shoulders(self):
        import random
        random.seed(7)
        prices = _series([100 * (1 + random.uniform(-0.01, 0.01)) for _ in range(60)])
        assert detect_head_and_shoulders(prices, threshold_pct=3.0) is False

    def test_real_swing_still_detected_as_support_resistance(self):
        # A genuine >3% swing must still register -- the filter should cut
        # noise, not real structure.
        prices = _series([100, 110, 100, 90, 100, 130, 100, 70, 100, 120, 100])
        support, resistance = find_support_resistance(prices, threshold_pct=3.0, top_n=2)
        assert resistance and support
        assert all(r > s for r in resistance for s in support)

    def test_flat_series_has_no_pivots(self):
        prices = _series([100.0] * 10)
        support, resistance = find_support_resistance(prices)
        assert support == [] and resistance == []

    def test_classic_head_and_shoulders_still_detected(self):
        prices = _series([5, 10, 5, 15, 5, 10, 5])
        assert detect_head_and_shoulders(prices) is True

    def test_classic_double_top_still_detected(self):
        prices = _series([5, 10, 5, 10.1, 5])
        double_top, _ = detect_double_top_bottom(prices)
        assert double_top is True


# ── load_price_data: date-cutoff string comparison bug ───────────────────────

class TestLoadPriceDataDateCutoff:
    def test_earliest_requested_day_is_not_dropped(self, tmp_path, monkeypatch):
        db_file = tmp_path / "test.db"
        monkeypatch.setattr(data, "DB_FILE", str(db_file))
        init_database()

        # Insert a row dated exactly `days` ago -- the boundary day that the
        # old string-comparison bug silently excluded.
        today = datetime.now().date()
        boundary_date = today - timedelta(days=5)
        conn = sqlite3.connect(str(db_file))
        conn.execute(
            "INSERT INTO price_history (coin_id, date, price, volume, market_cap, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("bitcoin", boundary_date.isoformat(), 50000.0, 1.0, None, 0),
        )
        conn.commit()
        conn.close()

        df = load_price_data("bitcoin", days=5)
        assert df is not None
        assert boundary_date.isoformat() in [d.isoformat() for d in df.index.date]


# ── backtest_strategy: must fetch fresh data for the requested window ───────

class TestBacktestFetchesFreshData:
    def test_backtest_calls_fetch_history_with_requested_days(self, tmp_path, monkeypatch):
        monkeypatch.setattr(data, "DB_FILE", str(tmp_path / "test.db"))
        init_database()

        calls = []

        def fake_fetch_history(coin_id, days):
            calls.append((coin_id, days))
            idx = pd.date_range(end=datetime.now(), periods=days, freq="D")
            df = pd.DataFrame({"price": [100.0 + i for i in range(days)]}, index=idx)
            return df

        def fake_load_price_data(coin_id, days):
            idx = pd.date_range(end=datetime.now(), periods=days, freq="D")
            return pd.DataFrame({"price": [100.0 + i for i in range(days)]}, index=idx)

        monkeypatch.setattr(api, "fetch_history", fake_fetch_history)
        monkeypatch.setattr(data, "load_price_data", fake_load_price_data)

        result = backtest_strategy("bitcoin", "rsi_ma", days=45)

        assert calls == [("bitcoin", 45)]
        assert "error" not in result
        assert result["period_days"] == 45

    def test_backtest_reports_fetch_failure_instead_of_stale_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr(data, "DB_FILE", str(tmp_path / "test.db"))
        init_database()

        def failing_fetch(coin_id, days):
            raise RuntimeError("CoinGecko network error: boom")

        monkeypatch.setattr(api, "fetch_history", failing_fetch)
        result = backtest_strategy("bitcoin", "rsi_ma", days=45)
        assert "error" in result


# ── save_portfolio: atomic write ─────────────────────────────────────────────

class TestSavePortfolioAtomic:
    def test_writes_via_temp_file_and_no_temp_left_behind(self, tmp_path, monkeypatch):
        portfolio_file = tmp_path / "portfolio.json"
        monkeypatch.setattr(data, "PORTFOLIO_FILE", str(portfolio_file))
        monkeypatch.chdir(tmp_path)

        save_portfolio({"bitcoin": {"symbol": "BTC", "amount": 1.5, "avg_buy_price": 40000}})

        assert portfolio_file.exists()
        assert not (tmp_path / "portfolio.json.tmp").exists()
        loaded = load_portfolio()
        assert loaded["bitcoin"]["amount"] == 1.5


# ── _get: must not kill the process on a bad request ─────────────────────────

class TestGetRaisesInsteadOfExiting:
    def test_network_error_raises_runtime_error(self, monkeypatch):
        def broken_get(*args, **kwargs):
            raise requests.exceptions.ConnectionError("no network")

        monkeypatch.setattr(api.requests, "get", broken_get)
        with pytest.raises(RuntimeError):
            _get("coins/markets")

    def test_http_error_raises_runtime_error_not_sys_exit(self, monkeypatch):
        class FakeResponse:
            status_code = 500

            def raise_for_status(self):
                raise requests.exceptions.HTTPError(response=self)

            def json(self):
                return {}

        def broken_get(*args, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(api.requests, "get", broken_get)
        with pytest.raises(RuntimeError):
            _get("coins/markets")


# ── check_alerts: RSI alerts must not be skipped for coins outside top 10 ────

class TestCheckAlertsRsiNotGatedOnPriceMap:
    def test_rsi_alert_checked_even_if_coin_missing_from_price_map(self, monkeypatch, tmp_path):
        monkeypatch.setattr(data, "ALERTS_LOG_FILE", str(tmp_path / "alerts.log"))
        monkeypatch.setattr(ui.time, "sleep", lambda _: None)
        # Regression: the old code did `if coin_id not in price_map: continue`
        # before branching on alert_type, so an RSI alert on a coin that
        # dropped out of the top 10 (and thus isn't in `coins`) never fired.
        monkeypatch.setattr(data, "load_alerts", lambda active_only=True: [
            {"id": 1, "coin_id": "some-altcoin", "alert_type": "rsi",
             "threshold": 50, "direction": "above"}
        ])

        called = []

        def fake_fetch_history(coin_id, days):
            called.append(coin_id)
            idx = pd.date_range(end=datetime.now(), periods=days, freq="D")
            return pd.DataFrame({"price": list(range(days))}, index=idx)

        monkeypatch.setattr(api, "fetch_history", fake_fetch_history)

        # `coins` (top 10) does NOT include "some-altcoin".
        check_alerts([{"id": "bitcoin", "current_price": 50000}])

        assert called == ["some-altcoin"]

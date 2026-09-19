"""Unit tests for indicator calculations in analysis.py.

All tests use synthetic price series so no network or database access is needed.
"""

import sys
import os

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from analysis import (
    compute_rsi,
    compute_ema,
    compute_macd,
    compute_bollinger_bands,
    find_support_resistance,
    detect_head_and_shoulders,
    detect_double_top_bottom,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


# ── compute_rsi ───────────────────────────────────────────────────────────────

class TestComputeRsi:
    def test_mostly_gains_gives_high_rsi(self):
        # Zigzag: +3 then -1, trending up — RS = 1.5/0.5 → RSI ≈ 75
        values = [100.0]
        for i in range(29):
            values.append(values[-1] + (3.0 if i % 2 == 0 else -1.0))
        rsi = compute_rsi(_series(values))
        assert rsi > 70

    def test_all_losses_gives_low_rsi(self):
        prices = _series(list(range(30, 1, -1)))  # strictly decreasing
        rsi = compute_rsi(prices)
        assert rsi < 10

    def test_rsi_bounded(self):
        import random
        random.seed(42)
        prices = _series([100 + random.uniform(-5, 5) for _ in range(50)])
        rsi = compute_rsi(prices)
        assert 0 <= rsi <= 100

    def test_short_series_returns_float(self):
        # Should not raise, returns 0.0 when series is too short
        result = compute_rsi(_series([100.0, 101.0]))
        assert isinstance(result, float)


# ── compute_ema ───────────────────────────────────────────────────────────────

class TestComputeEma:
    def test_constant_series(self):
        prices = _series([50.0] * 30)
        ema = compute_ema(prices, span=10)
        assert abs(ema.iloc[-1] - 50.0) < 1e-6

    def test_ema_length_matches_input(self):
        prices = _series(range(1, 41))
        ema = compute_ema(prices, span=12)
        assert len(ema) == len(prices)

    def test_ema_reacts_faster_than_sma_to_jump(self):
        base = [100.0] * 20
        jump = [200.0] * 10
        prices = _series(base + jump)
        ema = compute_ema(prices, span=5)
        sma = prices.rolling(5).mean()
        # Three steps into the jump the SMA window still contains 100s, but EMA
        # has already moved further toward 200.
        assert ema.iloc[22] > sma.iloc[22]


# ── compute_macd ──────────────────────────────────────────────────────────────

class TestComputeMacd:
    def test_macd_equals_fast_minus_slow_ema(self):
        prices = _series([float(i) + (i % 5) for i in range(60)])
        macd, signal, hist = compute_macd(prices)
        fast = compute_ema(prices, 12)
        slow = compute_ema(prices, 26)
        expected_macd = fast - slow
        pd.testing.assert_series_equal(macd, expected_macd, check_names=False)

    def test_histogram_equals_macd_minus_signal(self):
        prices = _series([100 + i * 0.5 for i in range(60)])
        macd, signal, hist = compute_macd(prices)
        pd.testing.assert_series_equal(hist, macd - signal, check_names=False)

    def test_output_length_matches_input(self):
        prices = _series(range(1, 61))
        macd, signal, hist = compute_macd(prices)
        assert len(macd) == len(prices)
        assert len(signal) == len(prices)
        assert len(hist) == len(prices)


# ── compute_bollinger_bands ───────────────────────────────────────────────────

class TestComputeBollingerBands:
    def test_mid_equals_rolling_mean(self):
        prices = _series([float(i) for i in range(1, 51)])
        mid, upper, lower = compute_bollinger_bands(prices, window=20)
        expected_mid = prices.rolling(20).mean()
        pd.testing.assert_series_equal(mid, expected_mid, check_names=False)

    def test_upper_lower_symmetric_around_mid(self):
        prices = _series([float(i) for i in range(1, 51)])
        mid, upper, lower = compute_bollinger_bands(prices, window=20, num_std=2)
        # upper - mid == mid - lower at every non-NaN point
        diff_up = (upper - mid).dropna()
        diff_lo = (mid - lower).dropna()
        pd.testing.assert_series_equal(diff_up, diff_lo, check_names=False)

    def test_constant_prices_zero_bandwidth(self):
        prices = _series([100.0] * 30)
        mid, upper, lower = compute_bollinger_bands(prices, window=20)
        assert (upper.dropna() == lower.dropna()).all()


# ── find_support_resistance ───────────────────────────────────────────────────

class TestFindSupportResistance:
    def _wave(self) -> pd.Series:
        # Creates clear peaks at 110/130 and troughs at 90/70
        return _series([100, 110, 100, 90, 100, 130, 100, 70, 100, 120, 100])

    def test_resistance_above_support(self):
        support, resistance = find_support_resistance(self._wave(), top_n=2)
        assert all(r > s for r in resistance for s in support)

    def test_returns_requested_count(self):
        support, resistance = find_support_resistance(self._wave(), top_n=2)
        assert len(support) <= 2
        assert len(resistance) <= 2

    def test_flat_series_returns_empty(self):
        prices = _series([100.0] * 10)
        support, resistance = find_support_resistance(prices)
        assert support == []
        assert resistance == []


# ── detect_head_and_shoulders ─────────────────────────────────────────────────

class TestDetectHeadAndShoulders:
    def test_classic_pattern_detected(self):
        # left shoulder=10, head=15, right shoulder=10, with valleys between
        prices = _series([5, 10, 5, 15, 5, 10, 5])
        assert detect_head_and_shoulders(prices) is True

    def test_no_pattern_on_flat(self):
        prices = _series([100.0] * 20)
        assert detect_head_and_shoulders(prices) is False

    def test_monotonic_increase_no_pattern(self):
        prices = _series(list(range(1, 20)))
        assert detect_head_and_shoulders(prices) is False


# ── detect_double_top_bottom ──────────────────────────────────────────────────

class TestDetectDoubleTopBottom:
    def test_double_top_detected(self):
        # Two peaks at roughly the same level
        prices = _series([5, 10, 5, 10.1, 5])
        double_top, double_bottom = detect_double_top_bottom(prices)
        assert double_top is True

    def test_double_bottom_detected(self):
        # Two troughs at roughly the same level
        prices = _series([10, 5, 10, 4.9, 10])
        double_top, double_bottom = detect_double_top_bottom(prices)
        assert double_bottom is True

    def test_no_pattern_on_monotonic(self):
        prices = _series(list(range(1, 15)))
        double_top, double_bottom = detect_double_top_bottom(prices)
        assert double_top is False
        assert double_bottom is False

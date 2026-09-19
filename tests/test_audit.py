"""Independent numerical and behavioral regressions from the external audit."""
import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest

import analysis
import ui


def frame(values):
    return pd.DataFrame({'price': values}, index=pd.date_range('2026-01-01', periods=len(values)))


def reference_rsi(values, period=14):
    """Simple arithmetic oracle: initial average, then Wilder's recurrence."""
    changes = [b - a for a, b in zip(values, values[1:])]
    gain = sum(max(d, 0) for d in changes[:period]) / period
    loss = sum(max(-d, 0) for d in changes[:period]) / period
    result = [None] * period
    for i in range(period, len(values)):
        if i > period:
            gain = (gain * (period - 1) + max(changes[i - 1], 0)) / period
            loss = (loss * (period - 1) + max(-changes[i - 1], 0)) / period
        result.append(100 if loss == 0 and gain > 0 else 50 if loss == gain == 0 else 100 - 100 / (1 + gain / loss))
    return result


def test_rsi_uses_initial_average_then_wilder_recurrence():
    values = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
              45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00]
    assert analysis.compute_rsi(pd.Series(values[:15])) == pytest.approx(70.4641350211)
    assert analysis.compute_rsi(pd.Series(values)) == pytest.approx(66.2496185536)


def test_backtest_trades_match_causal_full_history_reference():
    rng = random.Random(19)
    values = [100.0]
    for _ in range(399):
        values.append(values[-1] * (1 + rng.uniform(-0.06, 0.06)))
    df = frame(values)
    rsi = reference_rsi(values)
    expected = []
    position = False
    for i in range(25, len(values)):
        ma7 = sum(values[i-6:i+1]) / 7
        if not position and rsi[i] < 30 and values[i] > ma7:
            expected.append(('BUY', df.index[i], values[i]))
            position = True
        elif position and rsi[i] > 70:
            expected.append(('SELL', df.index[i], values[i]))
            position = False
    assert expected  # Ensure the regression actually exercises trading.
    actual = analysis.backtest_dataframe(df, 'bitcoin')['trades']
    assert [(t['type'], t['date'], t['price']) for t in actual] == expected
    # Future observations cannot change historical trade decisions.
    prefix = analysis.backtest_dataframe(df.iloc[:250], 'bitcoin')['trades']
    assert prefix == [t for t in actual if t['date'] <= df.index[249]]


@pytest.mark.parametrize('prefix', [[], [50, 55, 51]])
def test_declining_endpoint_is_not_support(prefix):
    tail = [100, 97, 94, 91, 88, 85, 82, 79, 76, 73, 70]
    support, _ = analysis.find_support_resistance(pd.Series(prefix + tail, dtype=float))
    assert 70 not in support


def test_second_bottom_requires_its_own_reversal():
    values = [100, 50, 100, 70, 100, 95, 90, 85, 80, 75, 71]
    assert analysis.detect_double_top_bottom(pd.Series(values))[1] is False
    assert analysis.detect_double_top_bottom(pd.Series(values + [74]))[1] is True


def test_second_top_requires_its_own_reversal():
    values = [50, 100, 50, 80, 50, 55, 60, 65, 70, 75, 79]
    assert analysis.detect_double_top_bottom(pd.Series(values))[0] is False
    assert analysis.detect_double_top_bottom(pd.Series(values + [76]))[0] is True


def test_unknown_strategy_is_rejected():
    result = analysis.backtest_dataframe(frame(range(100, 140)), 'bitcoin', strategy='typo')
    assert 'error' in result


def test_backtest_ui_discloses_actual_history_and_open_position(monkeypatch, capsys):
    df = frame(list(range(100, 60, -1)) + [65, 65, 65])
    result = analysis.backtest_dataframe(df, 'bitcoin', days=90)
    monkeypatch.setattr(analysis, 'backtest_strategy', lambda *a: result)
    answers = iter(['BTC', '1', '90'])
    monkeypatch.setattr('builtins.input', lambda *a: next(answers))
    ui.run_backtest([{'id': 'bitcoin', 'symbol': 'btc'}])
    output = capsys.readouterr().out
    assert 'Requested window: 90 days' in output
    assert '2026-01-01' in output
    assert '43 observations' in output
    assert 'Underlying asset max drawdown' in output
    assert 'Open position: YES' in output
    assert 'Win rate (closed trades): N/A' in output
    assert 'fees' in output.lower()


def test_shared_rsi_series_matches_reference_and_each_prefix():
    values = [100 + (i % 7) * 2 - i * 0.2 for i in range(70)]
    prices = pd.Series(values)
    actual = analysis.compute_rsi_series(prices)
    assert actual.iloc[:14].isna().all()
    assert actual.iloc[14:].tolist() == pytest.approx(reference_rsi(values)[14:])
    for i in range(14, len(values)):
        assert actual.iloc[i] == pytest.approx(analysis.compute_rsi(prices.iloc[:i+1]))


def test_right_shoulder_requires_its_own_reversal():
    values = [5, 10, 5, 15, 5, 10]
    assert analysis.detect_head_and_shoulders(pd.Series(values)) is False
    assert analysis.detect_head_and_shoulders(pd.Series(values + [5])) is True


def test_ai_evidence_excludes_unconfirmed_bottom_and_uses_shared_rsi():
    from recommendations import build_evidence
    values = [100] * 35 + [100, 50, 100, 70, 100, 95, 90, 85, 80, 75, 71]
    history = pd.DataFrame({'price': values}, index=pd.date_range(end=pd.Timestamp.now(tz='UTC').normalize(), periods=len(values)))
    result = build_evidence('bitcoin', history)
    assert 71 not in result['indicators']['support']
    assert 'Possible Double Bottom' not in result['indicators']['patterns']
    assert result['indicators']['rsi_14'] == pytest.approx(reference_rsi(values)[-1])

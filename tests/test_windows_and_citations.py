"""Window boundaries, stale-cache isolation, and complete evidence references."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

import analysis
import api
import data
import llm
import recommendations as rec
from history_window import select_daily_window

NOW = pd.Timestamp('2026-09-18T23:27:31Z')


def history(n=90):
    return pd.DataFrame({'price': range(100, 100+n)}, index=pd.date_range(end=NOW.normalize(), periods=n))


def test_complete_90_days_has_no_incomplete_warning():
    result = rec.build_evidence('bitcoin', history(), now=NOW)
    window = result['window']
    assert window['expected_start'] == '2026-06-21'
    assert window['start'] == '2026-06-21'
    assert window['complete'] is True
    assert window['observations'] == 90
    assert window['missing_days'] == 0
    assert not any('missing' in text or 'entire requested' in text for text in result['limitations'])


@pytest.mark.parametrize('drop,expected', [([0], (1, 0, 0)), ([45], (0, 1, 0)), ([89], (0, 0, 1)), ([0,45,89], (1,1,1))])
def test_coverage_distinguishes_boundary_and_internal_gaps(drop, expected):
    values = history()
    result = rec.build_evidence('bitcoin', values.drop(values.index[drop]), now=NOW)
    coverage = result['window']
    assert tuple(coverage[k] for k in ('leading_missing_days', 'internal_missing_days', 'trailing_missing_days')) == expected
    assert coverage['missing_days'] == sum(expected)
    assert coverage['complete'] is False
    assert any('Requested window is missing' in text for text in result['limitations'])


def test_window_filters_older_and_future_rows_and_normalizes_timezone():
    values = history(91)
    values.loc[NOW.normalize()+pd.Timedelta(days=1)] = [999999]
    result, coverage = select_daily_window(values, 90, now=NOW.tz_convert('America/Chicago'))
    assert len(result) == 90
    assert result.index[0] == pd.Timestamp('2026-06-21', tz='UTC')
    assert result.index[-1] == NOW.normalize()
    assert coverage['complete']


def test_empty_and_duplicate_windows():
    values = history()
    with pytest.raises(ValueError, match='unique'):
        select_daily_window(pd.concat([values, values.tail(1)]), 90, now=NOW)
    result, coverage = select_daily_window(values, 90, now=NOW + pd.Timedelta(days=200))
    assert result.empty
    assert coverage['missing_days'] == 90
    assert coverage['start'] is None


def test_backtest_ignores_cache_even_when_fresh_response_is_short(monkeypatch):
    fresh = pd.DataFrame({'date': pd.date_range(end=pd.Timestamp.now(tz='UTC').normalize(), periods=10), 'price': range(100,110)})
    monkeypatch.setattr(api, 'fetch_history', lambda *args: fresh)
    def forbidden(*args): raise AssertionError('Cache or result persistence must not run')
    monkeypatch.setattr(data, 'load_price_data', forbidden)
    monkeypatch.setattr(data, 'save_backtest_result', forbidden)
    assert 'error' in analysis.backtest_strategy('bitcoin', 'rsi_ma', 90)


def test_backtest_uses_fresh_rows_and_reports_actual_coverage(monkeypatch):
    fresh = pd.DataFrame({'date': pd.date_range(end=pd.Timestamp.now(tz='UTC').normalize(), periods=45), 'price': range(100,145)})
    monkeypatch.setattr(api, 'fetch_history', lambda *args: fresh)
    def forbidden(*args): raise AssertionError('Cached rows must not enter the backtest')
    monkeypatch.setattr(data, 'load_price_data', forbidden)
    saved = []
    monkeypatch.setattr(data, 'save_backtest_result', saved.append)
    result = analysis.backtest_strategy('bitcoin', 'rsi_ma', 90)
    assert result['observations'] == 45
    assert result['window']['leading_missing_days'] == 45
    assert saved == [result]


@pytest.mark.parametrize('days', [1, 7, 14, 30, 90, 180, 365])
def test_ohlc_sends_exact_supported_window(monkeypatch, days):
    calls=[]
    def get(endpoint, params):
        calls.append(params['days'])
        return [[1700000000000, 100, 110, 90, 105]]
    monkeypatch.setattr(api, '_get', get)
    assert len(api.fetch_ohlc('bitcoin', days)) == 1
    assert calls == [days]


@pytest.mark.parametrize('days', [8, 45, 60, 364, 366, 0, True])
def test_unsupported_ohlc_window_fails_before_network(monkeypatch, days):
    def forbidden(*args): raise AssertionError('Must not make an API call')
    monkeypatch.setattr(api, '_get', forbidden)
    with pytest.raises(RuntimeError, match='Unsupported OHLC window'):
        api.fetch_ohlc('bitcoin', days)


def valid_decision():
    return {'action':'HOLD', 'confidence':'low', 'confidence_explanation':'Limited history.',
            'summary':'Mixed evidence.',
            'reasons':[{'evidence_keys':['indicators.latest_history_price_usd','indicators.ma_7','indicators.ma_25'], 'explanation':'Price is above both averages.'}],
            'risks':[{'evidence_keys':['backtest.closed_trades','limitations'], 'explanation':'No closed-trade evidence.'}]}


def test_multiple_references_allowed_for_reasons_and_risks():
    evidence = rec.build_evidence('bitcoin', history(), now=NOW)
    decision = valid_decision()
    assert rec.validate_recommendation(decision, evidence) == decision
    schema = llm.recommendation_schema(evidence)
    for category in ('reasons','risks'):
        assert 'evidence_keys' in schema['properties'][category]['items']['required']


@pytest.mark.parametrize('category', ['reasons','risks'])
@pytest.mark.parametrize('keys', [[], ['invented'], ['limitations','invented'], ['limitations','limitations'], 'limitations', [None]])
def test_all_citation_paths_are_validated(category, keys):
    evidence = rec.build_evidence('bitcoin', history(), now=NOW)
    decision = valid_decision()
    decision[category][0]['evidence_keys'] = keys
    with pytest.raises(rec.RecommendationError): rec.validate_recommendation(decision, evidence)

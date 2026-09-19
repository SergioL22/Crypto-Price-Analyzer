"""Integer interoperability without silently accepting boolean/fractional windows."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pytest
import analysis
import api
import data
import recommendations as rec
from history_window import select_daily_window


def history():
    return pd.DataFrame({'price': range(100,190)}, index=pd.date_range(end=pd.Timestamp.now(tz='UTC').normalize(), periods=90))


@pytest.mark.parametrize('integer', [int, np.int32, np.int64, np.uint64])
def test_integer_windows_are_accepted_and_normalized(integer, monkeypatch):
    frame=history()
    _, coverage=select_daily_window(frame, integer(90))
    assert type(coverage['requested_days']) is int
    evidence=rec.build_evidence('bitcoin', frame, days=integer(90))
    json.dumps(evidence, allow_nan=False)
    assert type(evidence['window']['requested_days']) is int
    calls=[]
    def fetch(coin, days):
        assert type(days) is int
        calls.append(days)
        return frame
    monkeypatch.setattr(api, 'fetch_history', fetch)
    monkeypatch.setattr(data, 'save_backtest_result', lambda result: None)
    result=analysis.backtest_strategy('bitcoin','rsi_ma',integer(90))
    assert type(result['period_days']) is int
    assert calls == [90]
    def get(endpoint, params):
        assert type(params['days']) is int
        return []
    monkeypatch.setattr(api,'_get',get)
    assert api.fetch_ohlc('bitcoin',integer(90)).empty
    assert analysis.compute_rsi(frame['price'],integer(14)) == analysis.compute_rsi(frame['price'],14)


@pytest.mark.parametrize('invalid', [True, False, np.bool_(True), 90.0, np.float64(90), 90.5, '90', None])
def test_invalid_window_types_rejected_without_network(invalid, monkeypatch):
    def forbidden(*a,**kw): raise AssertionError('Invalid windows must not call network')
    monkeypatch.setattr(api,'_get',forbidden)
    monkeypatch.setattr(api,'fetch_history',forbidden)
    with pytest.raises(ValueError): select_daily_window(history(),invalid)
    with pytest.raises(rec.RecommendationError): rec.build_evidence('bitcoin',history(),days=invalid)
    with pytest.raises(RuntimeError): api.fetch_ohlc('bitcoin',invalid)
    assert 'error' in analysis.backtest_strategy('bitcoin','rsi_ma',invalid)
    with pytest.raises(ValueError): analysis.compute_rsi(history()['price'],invalid)

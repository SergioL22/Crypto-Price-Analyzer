"""Synthetic holdings only: saved user data is never opened by these tests."""
from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient
import api
import portfolio_view
from backend import create_app
from backend_service import BackendService, BackendError

NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)


def service(raw=None, quotes=None):
    return BackendService(portfolio_loader=Mock(return_value={} if raw is None else raw),
                          portfolio_prices_fetcher=Mock(return_value={} if quotes is None else quotes),
                          now=lambda: NOW)


def quote(price=100, age=0):
    return {'usd': price, 'last_updated_at': NOW.timestamp() - age}


def test_full_valuation_and_allocation():
    backend = service({'bitcoin': {'amount': 2, 'avg_buy_price': 80},
                       'ethereum': {'amount': 3, 'avg_buy_price': 120}},
                      {'bitcoin': quote(), 'ethereum': quote()})
    result = backend.portfolio()
    assert result.total_value_usd == 500
    assert result.unrealized_pnl_usd == -20
    assert [row.allocation_pct for row in result.holdings] == [40, 60]
    backend.portfolio_prices_fetcher.assert_called_once_with(['bitcoin', 'ethereum'])


@pytest.mark.parametrize('bad_quote', [None, {}, quote(None), quote(True), quote(-1), quote(0),
                                      quote(float('inf')), quote(age=901), quote(age=-61)])
def test_missing_invalid_stale_quotes_never_become_zero(bad_quote):
    result = service({'bitcoin': {'amount': 1, 'avg_buy_price': 10},
                      'ethereum': {'amount': 2, 'avg_buy_price': 10}},
                     {'bitcoin': quote(), 'ethereum': bad_quote}).portfolio()
    assert result.total_value_usd is None
    assert result.priced_value_usd == 100
    assert result.unrealized_pnl_usd is None
    assert result.holdings[1].value_usd is None
    assert result.holdings[0].allocation_pct == 100


def test_unknown_cost_and_empty_portfolio():
    result = service({'bitcoin': {'amount': 1}}, {'bitcoin': quote()}).portfolio()
    assert result.total_value_usd == 100
    assert result.unrealized_pnl_usd is None
    backend = service({'bitcoin': {'amount': 0}})
    assert backend.portfolio().holdings == []
    backend.portfolio_prices_fetcher.assert_not_called()


@pytest.mark.parametrize('raw', [[], {'bad/id': {'amount': 1}}, {'bitcoin': {'amount': True}},
                                {'bitcoin': {'amount': -1}}, {'bitcoin': {'amount': '1'}},
                                {'bitcoin': {'amount': float('nan')}},
                                {'bitcoin': {'amount': 1e308, 'avg_buy_price': 1e308}}])
def test_invalid_file_fails_before_price_fetch(raw):
    backend = service(raw)
    with pytest.raises(BackendError) as error:
        backend.portfolio()
    assert error.value.code == 'portfolio_unavailable'
    backend.portfolio_prices_fetcher.assert_not_called()


def test_provider_failure_preserves_holdings_and_no_valuation():
    backend = service({'bitcoin': {'amount': 1}})
    backend.portfolio_prices_fetcher.side_effect = api.UpstreamError('private detail')
    result = backend.portfolio()
    assert result.total_holdings == 1
    assert result.total_value_usd is None


def test_route_is_explicit_read_only_and_origin_protected():
    backend = service({'bitcoin': {'amount': 1}}, {'bitcoin': quote()})
    with TestClient(create_app(backend), base_url='http://127.0.0.1:8000') as client:
        client.get('/')
        backend.portfolio_loader.assert_not_called()
        assert client.get('/v1/portfolio', headers={'Origin': 'https://evil.example'}).status_code == 403
        backend.portfolio_loader.assert_not_called()
        response = client.get('/v1/portfolio')
        assert response.status_code == 200
        assert response.json()['total_value_usd'] == 100
        assert response.headers['cache-control'] == 'no-store'
        assert client.post('/v1/portfolio').status_code == 405


def test_saved_file_location_and_no_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio_view, '__file__', str(tmp_path / 'portfolio_view.py'))
    assert portfolio_view.load_saved_portfolio() == {}
    path = tmp_path / 'portfolio.json'
    content = '{"bitcoin": {"amount": 2, "avg_buy_price": 50}}'
    path.write_text(content)
    assert portfolio_view.load_saved_portfolio()['bitcoin']['amount'] == 2
    assert path.read_text() == content


def test_quote_adapter_requests_ids_and_timestamps(monkeypatch):
    fetch = Mock(return_value={'bitcoin': quote()})
    monkeypatch.setattr(api, '_get', fetch)
    api.fetch_portfolio_prices(['bitcoin', 'ethereum'])
    fetch.assert_called_once_with('simple/price', {'ids': 'bitcoin,ethereum', 'vs_currencies': 'usd', 'include_last_updated_at': 'true'})


def test_portfolio_capacity_and_read_error_are_sanitized():
    backend = service()
    with backend.market_gate.enter(), backend.market_gate.enter(), backend.market_gate.enter(), backend.market_gate.enter():
        with pytest.raises(BackendError) as error:
            backend.portfolio()
        assert error.value.status == 429
        backend.portfolio_loader.assert_not_called()
    backend.portfolio_loader.side_effect = OSError('private path')
    with pytest.raises(BackendError) as error:
        backend.portfolio()
    assert 'private path' not in error.value.message


def test_holdings_limit_and_overflow():
    backend = service({f'coin-{index}': {'amount': 1} for index in range(101)})
    with pytest.raises(BackendError):
        backend.portfolio()
    backend.portfolio_prices_fetcher.assert_not_called()
    result = service({'bitcoin': {'amount': 1e308}}, {'bitcoin': quote(1e308)}).portfolio()
    assert result.total_value_usd is None

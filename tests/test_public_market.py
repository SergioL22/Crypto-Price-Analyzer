"""Public embeds must not widen permissions for synthetic or private routes."""
from fastapi.testclient import TestClient
from public_demo import create_app


def test_market_page_is_opt_in_and_practice_stays_isolated(monkeypatch):
    monkeypatch.setenv('PUBLIC_DEMO_ORIGIN','https://testserver')
    monkeypatch.delenv('PUBLIC_MARKET_WIDGETS',raising=False)
    client=TestClient(create_app(),base_url='https://testserver')
    assert 'SYNTHETIC DEMO' in client.get('/').text
    monkeypatch.setenv('PUBLIC_MARKET_WIDGETS','1')
    for path in ('/','/index.html','/market-watchlist.html'):
        response=client.get(path)
        assert response.status_code==200
        assert response.headers['x-research-data']=='embedded-market'
        assert 'https://s3.tradingview.com' in response.headers['content-security-policy']
        assert 'https://www.tradingview.com' in response.headers['content-security-policy']
        assert 'https://*.tradingview-widget.com' in response.headers['content-security-policy']
        assert '/assets/stocks.js' not in response.text
        assert 'listing-kind' in response.text
        assert 'listing-matches' in response.text
    practice=client.get('/stocks.html')
    assert 'SYNTHETIC DEMO' in practice.text
    assert 'Back to real market charts' in practice.text
    assert 'tradingview.com' not in practice.headers['content-security-policy']
    assert client.get('/v1/portfolio').status_code==404
    assert client.get('/v1/recommendations').status_code==404


def test_market_mode_still_checks_origin_and_method(monkeypatch):
    monkeypatch.setenv('PUBLIC_DEMO_ORIGIN','https://testserver')
    monkeypatch.setenv('PUBLIC_MARKET_WIDGETS','1')
    client=TestClient(create_app(),base_url='https://testserver')
    assert client.get('/',headers={'Origin':'https://foreign.example'}).status_code==403
    assert client.post('/').status_code==405

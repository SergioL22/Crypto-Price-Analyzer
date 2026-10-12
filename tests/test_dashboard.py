"""Offline dashboard serving and local request boundary checks."""
from pathlib import Path
from unittest.mock import Mock
import pytest
pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient
from backend import create_app

ORIGIN = 'http://127.0.0.1:8000'

@pytest.mark.parametrize('headers', [
    {'host': 'evil.example:8000'}, {'host': '127.0.0.1:9000'},
    {'origin': 'https://evil.example'}, {'origin': 'null'},
    {'origin': 'http://localhost:8000'}, {'origin': ORIGIN + '/'},
    [('host', '127.0.0.1:8000'), ('host', 'evil.example')],
    [('origin', ORIGIN), ('origin', ORIGIN)],
])
def test_untrusted_requests_do_not_reach_service(headers):
    service = Mock()
    with TestClient(create_app(service), base_url=ORIGIN) as client:
        response = client.post('/v1/recommendations', json={'coin_id':'bitcoin'}, headers=headers)
    assert response.status_code == 403
    assert response.json()['error']['code'] == 'origin_forbidden'
    assert service.mock_calls == []

@pytest.mark.parametrize('origin', [None, ORIGIN])
def test_same_origin_and_nonbrowser_health(origin):
    with TestClient(create_app(), base_url=ORIGIN) as client:
        response = client.get('/health', headers={} if origin is None else {'Origin':origin})
    assert response.status_code == 200

@pytest.mark.parametrize('origin', ['https://127.0.0.1:8000', 'http://evil.example:8000', 'http://127.0.0.1', 'http://127.0.0.1:0', 'http://127.0.0.1:65536', 'http://127.0.0.1:08000', 'http://127.0.0.1:8000/'])
def test_invalid_configuration_fails_closed(origin):
    with pytest.raises(ValueError): create_app(allowed_origin=origin)

def test_custom_port_and_hostname():
    with TestClient(create_app(allowed_origin='http://localhost:9000'), base_url='http://localhost:9000') as client:
        assert client.get('/health', headers={'Origin':'http://localhost:9000'}).status_code == 200
        assert client.get('/health', headers={'Origin':ORIGIN}).status_code == 403


def test_stock_page_is_separate_and_loads_only_shared_and_stock_scripts():
    with TestClient(create_app(), base_url=ORIGIN) as client:
        crypto = client.get('/crypto.html').text
        page = client.get('/stocks.html')
        assert page.status_code == 200
        assert 'id="stock-options"' not in crypto
        assert 'href="/"' in crypto
        assert '/assets/stocks.js' not in crypto
        assert 'id="stock-options"' in page.text
        assert '/assets/dashboard.js' not in page.text
        assert '/assets/common.js' in page.text
        assert "frame-ancestors 'none'" in page.headers['content-security-policy']


@pytest.mark.parametrize('path,section', [('/crypto.html', 'controls-title'),('/','stocks-title'),('/watchlist.html','watchlist-title'),('/portfolio.html','portfolio-title'),('/backups.html','backup-title'),('/alerts.html','alerts-title')])
def test_each_page_has_its_own_section_and_shared_navigation(path, section):
    paths = ['/crypto.html', '/', '/watchlist.html', '/portfolio.html', '/backups.html', '/alerts.html']
    sections = ['controls-title','stocks-title','watchlist-title','portfolio-title','backup-title','alerts-title']
    with TestClient(create_app(), base_url=ORIGIN) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert f'id="{section}"' in response.text
    for other in sections:
        if other != section:
            assert f'id="{other}"' not in response.text
    for target in paths:
        assert f'href="{target}"' in response.text
    assert f'href="{path}" aria-current="page"' in response.text
    assert "frame-ancestors 'none'" in response.headers['content-security-policy']

def test_static_assets_and_routes_from_other_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = Mock()
    with TestClient(create_app(service), base_url=ORIGIN) as client:
        page = client.get('/')
        assert page.status_code == 200
        assert '<h1>Stocks &amp; ETFs</h1>' in page.text
        assert "frame-ancestors 'none'" in page.headers['content-security-policy']
        for asset in ('dashboard.js','dashboard.css'):
            assert client.get('/assets/' + asset).status_code == 200
        assert client.get('/health').json() == {'status':'ok'}
        assert len(client.get('/openapi.json').json()['paths']) == 16
        for path in ('/assets/%2e%2e/%2e%2e/backend.py', '/backend.py', '/crypto_data.db'):
            assert client.get(path).status_code == 404
    assert service.mock_calls == []

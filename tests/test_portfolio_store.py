from unittest.mock import Mock
import json
import pytest
pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient
from backend import create_app
from backend_service import BackendService
from portfolio_store import PortfolioStore, PortfolioConflict


def test_add_update_preserves_other_holdings_and_metadata(tmp_path):
    path = tmp_path / 'portfolio.json'
    path.write_text(json.dumps({'ethereum': {'amount': 2, 'avg_buy_price': 50, 'symbol': 'ETH', 'note': 'keep'}}))
    store = PortfolioStore(path)
    saved = store.update('bitcoin', 1.5, 100, store.read()['version'])
    saved = store.update('ethereum', 3, 60, saved['version'])
    raw = json.loads(path.read_text())
    assert raw['ethereum'] == {'amount': 3, 'avg_buy_price': 60, 'symbol': 'ETH', 'note': 'keep'}
    assert raw['bitcoin']['amount'] == 1.5
    assert saved['holdings'][1]['cost_basis_usd'] == 180


def test_stale_editor_does_not_overwrite(tmp_path):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    version = store.read()['version']
    assert not store.path.exists()
    store.update('bitcoin', 1, 0, version)
    before = store.path.read_bytes()
    with pytest.raises(PortfolioConflict):
        store.update('ethereum', 2, 0, version)
    assert store.path.read_bytes() == before


def test_replace_failure_preserves_file_and_cleans_temp(tmp_path, monkeypatch):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    store.path.write_text('{}')
    monkeypatch.setattr('portfolio_store.os.replace', Mock(side_effect=OSError('failure')))
    with pytest.raises(OSError):
        store.update('bitcoin', 1, 10, store.read()['version'])
    assert store.path.read_text() == '{}'
    assert list(tmp_path.glob('.portfolio-*.tmp')) == []


def test_corrupt_file_not_overwritten(tmp_path):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    store.path.write_text('broken')
    with pytest.raises(ValueError):
        store.update('bitcoin', 1, 0, 'a' * 64)
    assert store.path.read_text() == 'broken'


def test_http_edit_validation_conflicts_and_no_providers(tmp_path):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    provider = Mock(side_effect=AssertionError('No providers during edits'))
    service = BackendService(portfolio_store=store, portfolio_prices_fetcher=provider, recommender_factory=provider)
    with TestClient(create_app(service), base_url='http://127.0.0.1:8000') as client:
        version = client.get('/v1/holdings').json()['version']
        body = dict(coin_id='bitcoin', amount=1.0, avg_buy_price=0.0, version=version)
        assert client.put('/v1/holdings', json=body, headers={'Origin': 'https://evil.example'}).status_code == 403
        assert not store.path.exists()
        for field, value in [('amount', 0), ('amount', True), ('amount', '2'), ('amount', -1), ('avg_buy_price', -5), ('coin_id', '../secret')]:
            assert client.put('/v1/holdings', json={**body, field:value}).status_code == 422
        assert not store.path.exists()
        assert client.put('/v1/holdings', json=body).status_code == 200
        assert client.put('/v1/holdings', json=body).status_code == 409
        assert client.get('/v1/holdings').headers['cache-control'] == 'no-store'
    provider.assert_not_called()


def test_remove_preserves_other_holdings_and_rejects_stale_requests(tmp_path):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    saved = store.update('bitcoin', 2, 100, store.read()['version'])
    saved = store.update('ethereum', 3, 50, saved['version'])
    result = store.remove('bitcoin', saved['version'])
    assert [h['coin_id'] for h in result['holdings']] == ['ethereum']
    assert result['holdings'][0]['cost_basis_usd'] == 150
    before = store.path.read_bytes()
    with pytest.raises(PortfolioConflict):
        store.remove('ethereum', saved['version'])
    with pytest.raises(PortfolioConflict):
        store.remove('bitcoin', result['version'])
    assert store.path.read_bytes() == before
    assert store.remove('ethereum', result['version'])['holdings'] == []
    assert json.loads(store.path.read_text()) == {}


def test_failed_removal_preserves_original(tmp_path, monkeypatch):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    saved = store.update('bitcoin', 1, 10, store.read()['version'])
    before = store.path.read_bytes()
    monkeypatch.setattr('portfolio_store.os.replace', Mock(side_effect=OSError('failure')))
    with pytest.raises(OSError):
        store.remove('bitcoin', saved['version'])
    assert store.path.read_bytes() == before
    assert list(tmp_path.glob('.portfolio-*.tmp')) == []


def test_removal_route_origin_validation_and_no_provider_calls(tmp_path):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    saved = store.update('bitcoin', 1, 10, store.read()['version'])
    provider = Mock(side_effect=AssertionError('No provider requests'))
    service = BackendService(portfolio_store=store, portfolio_prices_fetcher=provider, recommender_factory=provider)
    with TestClient(create_app(service), base_url='http://127.0.0.1:8000') as client:
        body = {'coin_id': 'bitcoin', 'version': saved['version']}
        assert client.request('DELETE', '/v1/holdings', json=body, headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.request('DELETE', '/v1/holdings', json={**body, 'extra': True}).status_code == 422
        assert len(store.read()['holdings']) == 1
        response = client.request('DELETE', '/v1/holdings', json=body)
        assert response.status_code == 200
        assert response.json()['holdings'] == []
        assert client.request('DELETE', '/v1/holdings', json=body).status_code == 409
    provider.assert_not_called()


def test_export_preserves_saved_data_without_writes(tmp_path):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    assert json.loads(store.export()) == {}
    assert not store.path.exists()
    raw = {'bitcoin': {'amount': 1.25, 'avg_buy_price': 123.45, 'symbol': 'BTC', 'note': 'original'},
           'ethereum': {'amount': 0, 'avg_buy_price': 0, 'symbol': 'ETH'}}
    store.path.write_text(json.dumps(raw))
    before = store.path.read_bytes()
    assert json.loads(store.export()) == raw
    assert store.path.read_bytes() == before
    assert list(tmp_path.glob('.portfolio-*.tmp')) == []


def test_export_attachment_security_and_errors(tmp_path):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    provider = Mock(side_effect=AssertionError('No providers'))
    service = BackendService(portfolio_store=store, portfolio_prices_fetcher=provider, recommender_factory=provider)
    with TestClient(create_app(service), base_url='http://127.0.0.1:8000') as client:
        response = client.get('/v1/holdings/export')
        assert response.status_code == 200
        assert response.json() == {}
        assert response.headers['content-disposition'] == 'attachment; filename="portfolio-backup.json"'
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert not store.path.exists()
        assert client.get('/v1/holdings/export', headers={'Origin':'https://evil.example'}).status_code == 403
        store.path.write_text('private invalid content')
        error = client.get('/v1/holdings/export')
        assert error.status_code == 503
        assert 'content-disposition' not in error.headers
        assert 'private invalid content' not in error.text
        assert store.path.read_text() == 'private invalid content'
    provider.assert_not_called()

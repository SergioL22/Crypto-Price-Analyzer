"""Phase 1 completion: isolated restore and alert workflows."""
import json
import sqlite3
from datetime import datetime, timezone
from unittest.mock import Mock
import pandas as pd
import pytest
pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient
from backend import create_app
from backend_service import BackendService
from backend_models import AlertCreate
from alert_store import AlertStore, AlertConflict
from portfolio_store import PortfolioStore, PortfolioConflict

NOW = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
ORIGIN = 'http://127.0.0.1:8000'


def rule(coin='bitcoin', kind='price', threshold=100, direction='above'):
    return AlertCreate(coin_id=coin, alert_type=kind, threshold=threshold, direction=direction)


def test_restore_preview_then_atomic_replace_with_recovery_copy(tmp_path):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    store.update('bitcoin', 1, 10, store.read()['version'])
    before = store.path.read_bytes()
    content = json.dumps({'ethereum': {'amount': 0, 'avg_buy_price': 0, 'symbol': 'ETH'}})
    preview = store.preview_restore(content)
    assert preview['removed'] == ['bitcoin'] and preview['added'] == ['ethereum']
    assert preview['holdings'][0]['amount'] == 0
    assert store.path.read_bytes() == before
    assert not list(tmp_path.glob('portfolio-backup-*.json'))
    store.restore(content, preview['version'])
    assert json.loads(store.path.read_text()) == json.loads(content)
    backup = list(tmp_path.glob('portfolio-backup-*.json'))
    assert len(backup) == 1 and json.loads(backup[0].read_text()) == json.loads(before)


@pytest.mark.parametrize('content', ['[]', 'null', 'broken', '{"bitcoin":{"amount":1,"amount":2}}',
                                     '{"bitcoin":{"amount":NaN}}', '{"bitcoin":{"amount":true}}',
                                     '{"bitcoin":{"amount":-1}}', '{"../bad":{"amount":1}}', ' ' * 500001],
                         ids=['array','null','syntax','duplicate','nan','boolean','negative','invalid-id','oversize'])
def test_bad_backups_cannot_preview_or_write(tmp_path, content):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    with pytest.raises((ValueError, TypeError)):
        store.preview_restore(content)
    assert not store.path.exists()
    assert not list(tmp_path.glob('portfolio-backup-*.json'))


def test_restore_conflict_and_write_failure_preserve_original(tmp_path, monkeypatch):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    preview = store.preview_restore('{}')
    current = store.update('bitcoin', 1, 0, preview['version'])
    before = store.path.read_bytes()
    with pytest.raises(PortfolioConflict):
        store.restore('{}', preview['version'])
    monkeypatch.setattr('portfolio_store.os.replace', Mock(side_effect=OSError('denied')))
    with pytest.raises(OSError):
        store.restore('{}', current['version'])
    assert store.path.read_bytes() == before
    assert len(list(tmp_path.glob('portfolio-backup-*.json'))) == 1


def test_restore_http_boundary(tmp_path):
    store = PortfolioStore(tmp_path / 'portfolio.json')
    with TestClient(create_app(BackendService(portfolio_store=store)), base_url=ORIGIN) as client:
        payload = {'content':'{"bitcoin":{"amount":1,"avg_buy_price":5}}'}
        assert client.post('/v1/holdings/restore/preview',json=payload,headers={'Origin':'https://evil.example'}).status_code == 403
        preview = client.post('/v1/holdings/restore/preview',json=payload).json()
        assert not store.path.exists()
        assert client.post('/v1/holdings/restore',json={**payload,'version':preview['version']}).status_code == 200
        assert client.post('/v1/holdings/restore',json={**payload,'version':preview['version']}).status_code == 409


def test_alert_crud_is_cli_compatible_and_history_survives_delete(tmp_path):
    store = AlertStore(tmp_path / 'crypto_data.db')
    saved = store.create(rule())['alerts'][0]
    with sqlite3.connect(store.path) as conn:
        assert len(conn.execute('SELECT * FROM alerts').fetchone()) == 8
    with pytest.raises(AlertConflict):
        store.create(rule())
    assert store.record(saved, 101, NOW.isoformat(), NOW.isoformat()) == 'triggered'
    assert store.record(saved, 102, NOW.isoformat(), NOW.isoformat()) == 'already_matching'
    assert store.change(saved['id'], False)['alerts'][0]['is_active'] == 0
    assert store.record(saved, 102, NOW.isoformat(), NOW.isoformat()) == 'changed'
    store.change(saved['id'], True)
    assert store.record(saved, 102, NOW.isoformat(), NOW.isoformat()) == 'already_matching'
    assert store.record(saved, 100, NOW.isoformat(), NOW.isoformat()) == 'not_matching'
    assert store.record(saved, 101, NOW.isoformat(), NOW.isoformat()) == 'triggered'
    result = store.change(saved['id'])
    assert result['alerts'] == [] and len(result['events']) == 2


def test_price_checks_freshness_rearming_and_no_ai(tmp_path):
    store = AlertStore(tmp_path / 'crypto_data.db'); store.create(rule())
    quotes = Mock(return_value={'bitcoin': {'usd': 101, 'last_updated_at': NOW.timestamp()}})
    ai = Mock(side_effect=AssertionError('No AI calls'))
    service = BackendService(alert_store=store, portfolio_prices_fetcher=quotes, recommender_factory=ai, now=lambda:NOW)
    assert service.check_alerts()['results'][0]['status'] == 'triggered'
    quotes.return_value = {'bitcoin': {'usd': 99, 'last_updated_at': NOW.timestamp()-901}}
    assert service.check_alerts()['results'][0]['status'] == 'unavailable'
    quotes.return_value = {'bitcoin': {'usd': 101, 'last_updated_at': NOW.timestamp()}}
    assert service.check_alerts()['results'][0]['status'] == 'already_matching'
    quotes.return_value = {'bitcoin': {'usd': 90, 'last_updated_at': NOW.timestamp()}}
    assert service.check_alerts()['results'][0]['status'] == 'not_matching'
    ai.assert_not_called()


def test_rsi_fetch_once_per_coin_and_missing_history_does_not_trigger(tmp_path):
    store = AlertStore(tmp_path / 'crypto_data.db'); store.create(rule(kind='rsi',threshold=70)); store.create(rule(kind='rsi',threshold=80))
    frame = pd.DataFrame({'price':list(range(100,190))},index=pd.date_range(end=NOW.date(),periods=90,tz='UTC'))
    fetcher = Mock(return_value=frame)
    service = BackendService(alert_store=store, history_fetcher=fetcher, now=lambda:NOW)
    result = service.check_alerts()
    assert all(row['status']=='triggered' for row in result['results'])
    fetcher.assert_called_once_with('bitcoin',90,persist=False)
    fetcher.return_value = frame.iloc[1:]
    result = service.check_alerts()
    assert all(row['status']=='unavailable' for row in result['results'])
    assert len(result['events']) == 2


def test_alert_limits_and_check_gate(tmp_path):
    store = AlertStore(tmp_path / 'crypto_data.db')
    for index in range(20):
        store.create(rule(coin=f'coin-{index}'))
    with pytest.raises(AlertConflict):
        store.create(rule(coin='extra'))
    store.change(1,False)
    store.create(rule(coin='extra'))
    with pytest.raises(AlertConflict):
        store.change(1,True)
    service = BackendService(alert_store=store)
    with service.alert_gate.enter(), pytest.raises(Exception) as error:
        service.check_alerts()
    assert error.value.status == 429


def test_alert_routes_validation_and_host_protection(tmp_path):
    store = AlertStore(tmp_path / 'crypto_data.db')
    with TestClient(create_app(BackendService(alert_store=store)),base_url=ORIGIN) as client:
        body=rule().model_dump()
        assert not store.path.exists()
        assert client.post('/v1/alerts',json=body,headers={'Origin':'https://evil.example'}).status_code == 403
        assert not store.path.exists()
        assert client.post('/v1/alerts',json={**body,'threshold':True}).status_code == 422
        assert client.post('/v1/alerts',json={**body,'alert_type':'rsi','threshold':101}).status_code == 422
        response=client.post('/v1/alerts',json=body)
        assert response.status_code == 200
        assert client.patch('/v1/alerts/1',json={'active':False}).json()['alerts'][0]['is_active']==0
        assert client.post('/v1/alerts/check').json()['results']==[]
        assert client.delete('/v1/alerts/1').json()['alerts']==[]

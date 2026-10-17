from datetime import datetime,timezone,timedelta
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from account_backend import create_app
from account_settings import AccountSettings
from account_research import Research,DisabledResearch,COINS,crypto_result
from account_store import AccountError

NOW=datetime(2026,10,13,17,tzinfo=timezone.utc)
ORIGIN='http://127.0.0.1:8001'


@pytest.fixture
def app(tmp_path):
    settings=AccountSettings(ORIGIN,'sqlite:///'+(tmp_path/'research.db').as_posix(),'test-signing-secret-at-least-32-characters',demo=True)
    app=create_app(settings,research=Research(now=lambda:NOW))
    yield app
    app.state.store.engine.dispose()


def login(app):
    client=TestClient(app,base_url=ORIGIN,client=('127.0.0.1',50000))
    assert client.post('/auth/demo',json={'profile':'avery'},headers={'Origin':ORIGIN}).status_code==200
    return client


def test_research_requires_session_and_keeps_legacy_routes_closed(app):
    c=TestClient(app,base_url=ORIGIN,client=('127.0.0.1',50000))
    assert c.get('/v2/research/assets?kind=stock').status_code==401
    assert c.get('/v2/research/analysis?kind=stock&asset_id=anything&days=90').status_code==401
    assert c.get('/v1/portfolio').status_code==404


@pytest.mark.parametrize('kind',['stock','etf','crypto'])
def test_sample_research_is_offline_complete_and_never_saves_a_position(app,kind):
    c=login(app)
    assets=c.get('/v2/research/assets',params={'kind':kind}).json()['assets']
    assert all(a['asset_class']==kind for a in assets)
    result=c.get('/v2/research/analysis',params={'kind':kind,'asset_id':assets[0]['id'],'days':90})
    assert result.status_code==200,result.text
    data=result.json()
    assert data['data_mode']=='sample' and data['window']['complete']
    assert data['indicators']['rsi_14'] is not None
    assert data['history'][-1]['date']<'2026-10-13'
    assert bool(data['bars'])==(kind!='crypto')
    assert c.get('/v2/workspace').json()['workspace']['holdings']==[]


def test_crypto_live_adapter_is_read_only_and_excludes_unfinished_utc_day():
    calls=[]
    def history(*args,**kwargs):
        calls.append((args,kwargs))
        return pd.DataFrame({'date':pd.date_range('2026-07-15',periods=91),'price':[100+i for i in range(91)]})
    research=Research(sample=False,history=history,now=lambda:NOW)
    data=research.analyze('crypto',COINS[0]['id'],90)
    assert calls==[(('bitcoin',91),{'persist':False})]
    assert data['history'][-1]['date']=='2026-10-12'
    assert data['window']['complete'] and len(data['history'])==90
    assert data['data_mode']=='local-live'


def test_crypto_gaps_suppress_indicators_and_overlays():
    frame=pd.DataFrame({'price':[100+i for i in range(89)]},index=pd.date_range('2026-07-15',periods=89))
    result=crypto_result(COINS[0],frame,90,NOW)
    assert result['window']['missing_sessions']==['2026-10-12']
    assert result['indicators'] is None
    assert all(p['ma_7'] is None for p in result['history'])


def test_crypto_window_and_unknown_asset_are_rejected():
    r=Research(now=lambda:NOW)
    with pytest.raises(AccountError):r.analyze('crypto',COINS[0]['id'],365)
    with pytest.raises(AccountError):r.analyze('crypto','unlisted',90)


def test_provider_errors_and_invalid_selection_recover(app):
    c=login(app)
    assert c.get('/v2/research/assets?kind=unknown').status_code==422
    assert c.get('/v2/research/analysis?kind=crypto&asset_id=unlisted&days=90').status_code==404
    assert c.get('/v2/research/assets?kind=crypto').status_code==200


def test_managed_factory_cannot_enable_private_live_adapter(tmp_path):
    settings=AccountSettings('https://research.example','sqlite:///'+(tmp_path/'hosted.db').as_posix(),'test-signing-secret-at-least-32-characters',issuer='https://identity.example',client_id='test',client_secret='test')
    with pytest.raises(ValueError,match='loopback-only'):create_app(settings,research=Research(sample=False))


def test_disabled_market_adapter_has_no_provider_fallback():
    with pytest.raises(AccountError,match='market_not_enabled'):DisabledResearch().catalog('stock')


def test_interactive_budget_returns_retry_after_for_signed_in_research(app,monkeypatch):
    from stock_service import StockService
    from stock_provider import StockDataError
    client=login(app)
    asset=client.get('/v2/research/assets?kind=stock').json()['assets'][0]['id']
    def limited(*args,**kwargs):raise StockDataError('stock_budget','Wait for history budget',retry_after_seconds=23)
    monkeypatch.setattr(StockService,'research',limited)
    response=client.get('/v2/research/analysis',params={'kind':'stock','asset_id':asset,'days':90})
    assert response.status_code==429 and response.headers['Retry-After']=='23'
    assert response.json()['error']['code']=='stock_budget'


def test_company_profiles_require_login_and_sample_accounts_never_call_live_profiles(app,monkeypatch):
    from company_profiles import CompanyProfiles
    monkeypatch.setattr(CompanyProfiles,'load',lambda *a,**k:pytest.fail('Sample must not call live profiles'))
    anonymous=TestClient(app,base_url=ORIGIN,client=('127.0.0.1',50000))
    assert anonymous.get('/v2/research/company-profile?asset_id=anything').status_code==401
    client=login(app);asset=client.get('/v2/research/assets?kind=stock').json()['assets'][0]['id']
    response=client.get('/v2/research/company-profile',params={'asset_id':asset})
    assert response.status_code==200 and response.json()['status']=='not_supported'
    assert response.json()['profile'] is None

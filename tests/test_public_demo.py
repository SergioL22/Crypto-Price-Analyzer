from datetime import datetime,timezone
from fastapi.testclient import TestClient
import pytest
from public_demo import create_app,SyntheticProvider,NOTICE
from stock_provider import TwelveData
from company_profiles import CompanyProfiles

ORIGIN='https://synthetic.example'
ASSET='demo:stock:XNYS:USD:SIMSUN'

@pytest.fixture
def demo(monkeypatch,tmp_path):
    monkeypatch.setenv('PUBLIC_DEMO_ORIGIN',ORIGIN)
    monkeypatch.setenv('TWELVE_DATA_API_KEY','synthetic-must-never-be-used')
    monkeypatch.setenv('FINNHUB_API_KEY','synthetic-must-never-be-used')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-must-never-be-used')
    monkeypatch.chdir(tmp_path)
    def fail(*args,**kwargs):pytest.fail('Live provider constructed by public demo')
    monkeypatch.setattr(TwelveData,'__init__',fail)
    monkeypatch.setattr(CompanyProfiles,'__init__',fail)
    return TestClient(create_app(),base_url=ORIGIN)

def test_anonymous_pages_are_labeled_and_have_no_duplicate_demo_flags(demo):
    for path in ['/','/stocks.html','/watchlist.html','/portfolio.html','/alerts.html','/backups.html']:
        response=demo.get(path)
        assert response.status_code==200
        assert NOTICE in response.text and response.text.count('data-demo="true"')==1
        assert response.headers['x-research-data']=='synthetic'
        assert "connect-src 'self'" in response.headers['content-security-policy']
    assert demo.get('/health').json()['mode']=='synthetic-demo'

def test_catalog_research_and_profiles_work_without_provider_construction(demo,tmp_path):
    catalog=demo.get('/v1/assets').json()
    assert len(catalog['assets'])==5 and all(a['provider']=='demo' for a in catalog['assets'])
    assert 'fictional' in catalog['coverage']
    assert len(demo.get('/v1/assets?asset_class=etf').json()['assets'])==3
    response=demo.get('/v1/stock-analysis',params={'asset_id':ASSET,'days':90})
    assert response.status_code==200
    result=response.json();assert result['window']['complete'] and result['history'] and result['indicators']
    assert result['adjustment']=='synthetic'
    assert NOTICE in result['limitations'] and result['asset']['provider']=='demo'
    profile=demo.get('/v1/company-profile',params={'asset_id':ASSET}).json()
    assert profile['profile'] is None and profile['source']=='Synthetic demo generator'
    assert not list(tmp_path.glob('*.db')) and not list(tmp_path.glob('.env'))

@pytest.mark.parametrize('path',['/v1/holdings','/v1/portfolio','/v1/alerts','/v1/recommendations','/v1/predictions','/v2/workspace','/account.html','/crypto.html','/.env','/openapi.json'])
def test_public_demo_exposes_no_private_or_paid_routes(demo,path):
    assert demo.get(path).status_code==404

def test_real_listing_ids_are_rejected_and_no_post_or_cross_origin(demo):
    assert demo.get('/v1/stock-analysis',params={'asset_id':'twelvedata:stock:XNGS:USD:AAPL','days':90}).status_code==404
    assert demo.get('/v1/assets?asset_class=crypto').status_code==422
    assert demo.get('/v1/stock-analysis',params={'asset_id':ASSET,'days':99999}).status_code==422
    assert demo.post('/v1/assets').status_code==405
    assert demo.get('/',headers={'Origin':'https://other.example'}).status_code==403
    assert demo.get('/',headers={'Host':'other.example'}).status_code==403

def test_synthetic_history_is_prefix_stable_and_assets_have_distinct_paths():
    provider=SyntheticProvider();assets=provider.catalog()
    first=provider.history(assets[0],'2026-09-01','2026-09-30')
    extended=provider.history(assets[0],'2026-09-01','2026-10-16')
    assert first==[row for row in extended if row['date']<='2026-09-30']
    second=provider.history(assets[1],'2026-09-01','2026-09-30')
    assert first!=second
    assert all(b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high'] for b in first)

def test_demo_config_does_not_enable_private_preview(monkeypatch):
    from hosted_preview import create_app as private_app
    monkeypatch.setenv('PUBLIC_DEMO_ORIGIN',ORIGIN)
    monkeypatch.delenv('HOSTED_ORIGIN',raising=False)
    monkeypatch.delenv('RENDER_EXTERNAL_URL',raising=False)
    monkeypatch.delenv('HOSTED_PREVIEW_PASSWORD',raising=False)
    with pytest.raises(ValueError):private_app()

def test_demo_requires_https_outside_explicit_loopback(monkeypatch):
    monkeypatch.setenv('PUBLIC_DEMO_ORIGIN','http://example.com')
    with pytest.raises(ValueError):create_app()

def test_separate_deployment_recipe_has_no_key_or_password_prompts():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    recipe=(root/'render-demo.yaml').read_text(encoding='utf-8')
    assert 'name: research-desk-demo' in recipe and 'plan: free' in recipe
    assert 'API_KEY' not in recipe and 'PASSWORD' not in recipe
    assert 'public_demo:create_app' in (root/'Dockerfile.demo').read_text(encoding='utf-8')
    assert 'hosted_preview:create_app' in (root/'Dockerfile').read_text(encoding='utf-8')

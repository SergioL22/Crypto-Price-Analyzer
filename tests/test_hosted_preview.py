from datetime import datetime,timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from account_research import SampleProvider
from company_profiles import CompanyProfiles
from stock_service import StockService
from hosted_preview import create_app,RequestBudget

ORIGIN='https://research-preview.example'
PASSWORD='synthetic-password-for-offline-tests-only'
ASSET='twelvedata:stock:XNYS:USD:DEMO'

@pytest.fixture
def preview(monkeypatch,tmp_path):
    monkeypatch.setenv('HOSTED_ORIGIN',ORIGIN)
    monkeypatch.setenv('HOSTED_PREVIEW_PASSWORD',PASSWORD)
    monkeypatch.chdir(tmp_path)
    stocks=StockService(provider=SampleProvider(),profiles=CompanyProfiles(key=''))
    return TestClient(create_app(stocks=stocks,now=lambda:datetime(2026,10,17,tzinfo=timezone.utc)),base_url=ORIGIN)

@pytest.mark.parametrize('path',['/','/stocks.html','/assets/common.js','/v1/assets','/v1/stock-analysis','/v1/company-profile','/v1/holdings'])
def test_preview_requires_auth_before_any_data(preview,path):
    response=preview.get(path)
    assert response.status_code==401 and 'Basic' in response.headers['www-authenticate']

def test_only_health_is_public_and_never_leaks_configuration(preview):
    assert preview.get('/health').json()=={'status':'ok'}
    for credentials in [('preview','wrong'),('wrong',PASSWORD)]:
        response=preview.get('/',auth=credentials)
        assert response.status_code==401 and PASSWORD not in response.text
    assert preview.get('/',headers={'Authorization':'Basic !!!'}).status_code==401

def test_authorized_stock_flow_and_all_stock_pages(preview):
    auth=('preview',PASSWORD)
    for path in ['/','/stocks.html','/watchlist.html','/portfolio.html','/alerts.html','/backups.html','/assets/research-tools.js']:
        response=preview.get(path,auth=auth)
        assert response.status_code==200
        assert response.headers['cache-control']=='no-store'
        assert "frame-ancestors 'none'" in response.headers['content-security-policy']
        assert response.headers['strict-transport-security']
    catalog=preview.get('/v1/assets',auth=auth).json()
    assert any(a['id']==ASSET for a in catalog['assets'])
    response=preview.get('/v1/stock-analysis',params={'asset_id':ASSET,'days':90},auth=auth)
    assert response.status_code==200 and response.json()['window']['latest_closed_session']=='2026-10-16'
    assert preview.get('/v1/company-profile',params={'asset_id':ASSET},auth=auth).json()['status']=='setup_required'

@pytest.mark.parametrize('path',['/crypto.html','/account.html','/v1/holdings','/v1/portfolio','/v1/alerts','/v1/recommendations','/v2/workspace','/.env','/openapi.json','/docs','/assets/../.env'])
def test_private_and_unrelated_routes_are_absent(preview,path):
    assert preview.get(path,auth=('preview',PASSWORD)).status_code==404

def test_tls_origin_method_and_parameter_boundaries(preview):
    auth=('preview',PASSWORD)
    for headers in [{'Host':'other.example'},{'Origin':'https://other.example'},{'Sec-Fetch-Site':'cross-site'}]:
        assert preview.get('/v1/assets',headers=headers,auth=auth).status_code==403
    assert preview.get('http://research-preview.example/',auth=auth).status_code==403
    assert preview.post('/v1/assets',auth=auth).status_code==405
    assert preview.get('/v1/assets?asset_class=crypto',auth=auth).status_code==422
    assert preview.get('/v1/stock-analysis?asset_id=x&days=999999',auth=auth).status_code==422

def test_preview_configuration_never_falls_back_to_local_env(monkeypatch):
    monkeypatch.setenv('HOSTED_ORIGIN','http://127.0.0.1:8000')
    monkeypatch.setenv('HOSTED_PREVIEW_PASSWORD',PASSWORD)
    with pytest.raises(ValueError):create_app()
    monkeypatch.setenv('HOSTED_ORIGIN',ORIGIN)
    monkeypatch.setenv('HOSTED_PREVIEW_PASSWORD','short')
    with pytest.raises(ValueError):create_app()

def test_request_budget_recovers_after_window():
    now=[0.];budget=RequestBudget(limit=2,clock=lambda:now[0])
    assert budget.allow() and budget.allow() and not budget.allow()
    now[0]=60
    assert budget.allow()

def test_preview_stock_flow_creates_no_database_or_portfolio_files(preview,tmp_path):
    preview.get('/v1/stock-analysis',params={'asset_id':ASSET,'days':90},auth=('preview',PASSWORD))
    assert not list(tmp_path.glob('*.db')) and not list(tmp_path.glob('*portfolio*'))

def test_render_recipe_uses_hosted_factory_and_secret_free_build_context():
    root=Path(__file__).resolve().parents[1]
    recipe=(root/'render.yaml').read_text(encoding='utf-8')
    assert 'plan: free' in recipe and 'generateValue: true' in recipe and 'sync: false' in recipe
    docker=(root/'Dockerfile').read_text(encoding='utf-8')
    assert 'hosted_preview:create_app' in docker and 'USER appuser' in docker
    assert 'COPY . .' not in docker and 'OPENAI_API_KEY' not in docker
    ignored=(root/'.dockerignore').read_text(encoding='utf-8').splitlines()
    assert '**' in ignored and '!*.py' in ignored and '!.env' not in ignored and '!*.db' not in ignored


def test_hosted_catalog_is_compressed_without_changing_contract(preview):
    response=preview.get('/v1/stock-analysis',params={'asset_id':ASSET,'days':90},auth=('preview',PASSWORD),headers={'Accept-Encoding':'gzip'})
    assert response.status_code==200 and response.headers['content-encoding']=='gzip'
    assert response.json()['asset']['id']==ASSET and response.json()['history']

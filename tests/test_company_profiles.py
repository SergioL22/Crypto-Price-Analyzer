from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import requests
import pytest
from assets import Asset
from company_profiles import CompanyProfiles,normalize_profile
from stock_provider import StockDataError
from stock_service import StockService
from account_research import SampleProvider

NOW=datetime(2026,10,16,21,tzinfo=timezone.utc)
A=Asset('stock','twelvedata','DEMO','Demo','XNGS','USD','America/New_York')
ETF=Asset('etf','twelvedata','FUND','Fund','ARCX','USD','America/New_York')


def payload():return dict(ticker='DEMO',exchange='NASDAQ NMS - GLOBAL MARKET',name='Example Company',finnhubIndustry='Technology',country='GB',currency='GBP',weburl='https://example.com',ipo='2000-01-01')


class Response:
    def __init__(self,body=None,status=200):self.body=payload() if body is None else body;self.status_code=status
    def json(self):return self.body


def test_optional_setup_and_etf_support_make_no_finnhub_calls():
    def fail(*args,**kwargs):pytest.fail('Unexpected request')
    assert CompanyProfiles(key='',get=fail).load(A,NOW)['status']=='setup_required'
    assert CompanyProfiles(key='test',get=fail).load(ETF,NOW)['status']=='not_supported'


def test_free_endpoint_header_auth_and_fields_do_not_change_quote_identity():
    calls=[]
    def get(url,**kwargs):calls.append((url,kwargs));return Response()
    data=CompanyProfiles(key=' test-placeholder ',get=get).load(A,NOW)
    assert calls[0][0]=='https://finnhub.io/api/v1/stock/profile2'
    assert calls[0][1]['params']=={'symbol':'DEMO'}
    assert calls[0][1]['headers']=={'X-Finnhub-Token':'test-placeholder'}
    assert calls[0][1]['allow_redirects'] is False
    assert data['asset_id']==A.id and data['profile']['reporting_currency']=='GBP'
    assert data['identity_scope']=='symbol_operating_exchange' and data['provider_updated_at_utc'] is None
    assert data['profile']['finnhub_industry']=='Technology'


@pytest.mark.parametrize('change',[{'ticker':'OTHER'},{'ticker':'demo'},{'exchange':'NYSE'},{'exchange':'NASDAQ FAKE'},{'exchange':None},{'ipo':'2999-01-01'},{'ipo':'20000101'},{'weburl':'javascript:alert(1)'},{'weburl':'https://user:password@example.com'},{'finnhubIndustry':True},{'currency':'GB'},{'name':'x'*301}])
def test_invalid_or_mismatched_profiles_are_rejected(change):
    body=payload();body.update(change)
    with pytest.raises(StockDataError) as error:CompanyProfiles(key='test',get=lambda *a,**k:Response(body)).load(A,NOW)
    assert error.value.code=='profile_invalid'


@pytest.mark.parametrize('status,code',[(429,'profile_rate_limited'),(401,'profile_access'),(403,'profile_access'),(500,'profile_unavailable'),(302,'profile_unavailable')])
def test_http_errors_are_sanitized(status,code):
    with pytest.raises(StockDataError) as error:CompanyProfiles(key='private-test-key',get=lambda *a,**k:Response({'error':'secret'},status)).load(A,NOW)
    assert error.value.code==code and 'secret' not in str(error.value) and 'private-test-key' not in str(error.value)


@pytest.mark.parametrize('body',[[],{'error':'private provider details'},'secret'])
def test_payload_errors_are_sanitized(body):
    with pytest.raises(StockDataError) as error:CompanyProfiles(key='test',get=lambda *a,**k:Response(body)).load(A,NOW)
    assert error.value.code=='profile_unavailable' and 'secret' not in str(error.value)


def test_empty_or_partial_results_never_invent_fields():
    service=CompanyProfiles(key='test',get=lambda *a,**k:Response({}))
    assert service.load(A,NOW)['status']=='not_found'
    data=CompanyProfiles(key='test',get=lambda *a,**k:Response({'ticker':'DEMO','exchange':'NASDAQ'})).load(A,NOW)
    assert len(data['missing_fields'])==6 and all(value is None for value in data['profile'].values())


def test_profile_cache_is_copied_bounded_and_expires_without_stale_fallback():
    clock=[0.];calls=[];fail=[False]
    def get(*a,**k):
        calls.append(1)
        if fail[0]:raise requests.Timeout('secret')
        return Response()
    service=CompanyProfiles(key='test',get=get,clock=lambda:clock[0],ttl=100,capacity=1)
    first=service.load(A,NOW);first['profile']['name']='changed'
    clock[0]=30;cached=service.load(A,NOW)
    assert cached['cache_hit'] and cached['profile']['name']=='Example Company' and len(calls)==1
    assert cached['fetched_at_utc']==first['fetched_at_utc']
    clock[0]=101;fail[0]=True
    with pytest.raises(StockDataError):service.load(A,NOW)
    with pytest.raises(StockDataError) as error:service.load(A,NOW)
    assert error.value.retry_after_seconds==60 and len(calls)==2


def test_distinct_concurrent_profiles_share_a_budget_and_cache_hits_still_work():
    calls=[]
    def get(url,**kwargs):calls.append(1);body=payload();body['ticker']=kwargs['params']['symbol'];return Response(body)
    service=CompanyProfiles(key='test',get=get,request_limit=2)
    assets=[Asset('stock','twelvedata','D'+str(i),'Example','XNGS','USD','America/New_York') for i in range(6)]
    def attempt(asset):
        try:service.load(asset,NOW);return True
        except StockDataError as e:assert e.code=='profile_rate_limited';return False
    with ThreadPoolExecutor(6) as pool:assert sum(pool.map(attempt,assets))==2
    assert len(calls)==2


def test_api_profiles_are_separate_from_prices_and_have_optional_setup_state():
    from fastapi.testclient import TestClient
    from backend import create_app
    from backend_service import BackendService
    profiles=CompanyProfiles(key='')
    stocks=StockService(provider=SampleProvider(),profiles=profiles)
    client=TestClient(create_app(BackendService(stocks=stocks,now=lambda:NOW)),base_url='http://127.0.0.1:8000')
    asset='twelvedata:stock:XNYS:USD:DEMO'
    result=client.get('/v1/company-profile',params={'asset_id':asset})
    assert result.status_code==200 and result.json()['status']=='setup_required'
    assert 'FINNHUB_API_KEY' in result.json()['message']
    assert client.get('/v1/stock-analysis',params={'asset_id':asset,'days':90}).status_code==200


def test_lru_eviction_and_cached_profiles_survive_other_provider_failures():
    clock=[0.];calls=[];fail=[False]
    def get(url,**kwargs):
        calls.append(kwargs['params']['symbol'])
        if fail[0]:raise requests.Timeout('private')
        body=payload();body['ticker']=kwargs['params']['symbol'];return Response(body)
    service=CompanyProfiles(key='test',get=get,clock=lambda:clock[0],capacity=1,request_limit=10)
    other=Asset('stock','twelvedata','OTHER','Other','XNGS','USD','America/New_York')
    service.load(A,NOW);service.load(other,NOW);service.load(A,NOW)
    assert calls==['DEMO','OTHER','DEMO']
    fail[0]=True
    with pytest.raises(StockDataError):service.load(other,NOW)
    assert service.load(A,NOW)['cache_hit'] and len(calls)==4


def test_public_route_validated_profile_and_retry_header():
    from fastapi.testclient import TestClient
    from backend import create_app
    from backend_service import BackendService
    calls=[]
    def get(url,**kwargs):
        calls.append(1);body=payload();body['exchange']='NYSE';return Response(body)
    profiles=CompanyProfiles(key='test',get=get,request_limit=1,ttl=1,clock=lambda:len(calls)*2)
    stocks=StockService(provider=SampleProvider(),profiles=profiles)
    client=TestClient(create_app(BackendService(stocks=stocks,now=lambda:NOW)),base_url='http://127.0.0.1:8000')
    asset='twelvedata:stock:XNYS:USD:DEMO'
    response=client.get('/v1/company-profile',params={'asset_id':asset})
    assert response.status_code==200 and response.json()['profile']['name']=='Example Company'
    # Expire the cache without consuming a second provider request.
    profiles.ttl=0.1;profiles.clock=lambda:3
    response=client.get('/v1/company-profile',params={'asset_id':asset})
    assert response.status_code==429 and int(response.headers['retry-after'])>0 and len(calls)==1

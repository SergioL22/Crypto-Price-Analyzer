from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
import api
from coin_catalog import CoinCatalog

COINS = [{'id':'other-token','name':'Other Token','symbol':'same'}, {'id':'another-token','name':'Another Token','symbol':'same'}]

def test_cache_expiry_failure_backoff_and_recovery():
    clock=[0]; calls=[]; failing=[False]
    def fetch():
        calls.append(1)
        if failing[0]: raise api.UpstreamError('secret')
        return COINS
    cache=CoinCatalog(fetch,clock=lambda:clock[0],ttl=10,retry_delay=5)
    first=cache.get()
    assert len(first['coins']) == 2
    assert cache.get() == first and len(calls)==1
    clock[0]=10; failing[0]=True
    assert cache.get()['stale'] and len(calls)==2
    clock[0]=12
    assert cache.get()['stale'] and len(calls)==2
    clock[0]=15; failing[0]=False
    assert not cache.get()['stale'] and len(calls)==3

@pytest.mark.parametrize('raw',[None,{},[],[{'id':'x','name':'X'}]])
def test_bad_initial_catalog_does_not_poison_cache(raw):
    cache=CoinCatalog(lambda:raw)
    with pytest.raises(api.UpstreamError): cache.get()
    assert cache.cached is None

def test_concurrent_requests_share_single_refresh():
    entered=Event(); release=Event(); calls=[]
    def fetch():
        calls.append(1); entered.set(); assert release.wait(3); return COINS
    cache=CoinCatalog(fetch)
    with ThreadPoolExecutor(2) as pool:
        a=pool.submit(cache.get)
        assert entered.wait(2)
        b=pool.submit(cache.get)
        release.set()
        assert a.result()==b.result()
    assert len(calls)==1

def test_endpoint_contract_and_sanitized_failure():
    pytest.importorskip('fastapi'); pytest.importorskip('httpx')
    from fastapi.testclient import TestClient
    from backend import create_app
    from backend_service import BackendService
    service=BackendService(catalog=CoinCatalog(lambda:COINS))
    with TestClient(create_app(service),base_url='http://127.0.0.1:8000') as client:
        assert len(client.get('/v1/coins').json()['coins'])==2
        assert client.get('/v1/coins',headers={'Origin':'https://evil.example'}).status_code==403
        service.catalog=CoinCatalog(lambda:None)
        response=client.get('/v1/coins')
        assert response.status_code==503
        assert response.json()['error']['code']=='catalog_unavailable'

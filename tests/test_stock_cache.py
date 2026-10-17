from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from account_research import SampleProvider
from stock_service import StockService
from stock_provider import StockDataError
from stock_cache import HistoryCache

NOW=datetime(2026,10,15,19,59,tzinfo=timezone.utc)
ASSET='twelvedata:stock:XNYS:USD:DEMO'


class Provider(SampleProvider):
    def __init__(self):self.calls=0;self.fail=False;self.missing=False
    def history(self,*args):
        self.calls+=1
        if self.fail:raise StockDataError('stock_quota','Quota reached')
        rows=super().history(*args)
        if self.missing:rows.pop(10)
        return rows


def setup():
    p=Provider();clock=[0.]
    return p,clock,StockService(provider=p,clock=lambda:clock[0])


def test_repeated_browsing_reuses_bars_and_preserves_original_fetch_time():
    p,clock,s=setup();first=s.research(ASSET,90,NOW,use_cache=True)
    clock[0]=30;second=s.research(ASSET,90,NOW+timedelta(seconds=30),use_cache=True)
    assert p.calls==1 and second['history_source']['cache_hit']
    assert second['history_source']['fetched_at_utc']==first['history_source']['fetched_at_utc']
    assert second['history_source']['age_seconds']==30
    second['bars'][0]['close']=9999
    assert s.research(ASSET,90,NOW,use_cache=True)['bars'][0]['close']!=9999


def test_different_window_and_new_completed_session_never_reuse_wrong_bars():
    p,_,s=setup();s.research(ASSET,90,NOW,use_cache=True)
    s.research(ASSET,91,NOW,use_cache=True);assert p.calls==2
    after=s.research(ASSET,90,NOW+timedelta(minutes=2),use_cache=True)
    assert p.calls==3 and after['history'][-1]['date']=='2026-10-15'
    assert not after['history_source']['cache_hit']


def test_expiration_and_explicit_refresh_fetch_again():
    p,clock,s=setup();s.research(ASSET,90,NOW,use_cache=True)
    s.research(ASSET,90,NOW,use_cache=True,refresh=True);assert p.calls==2
    clock[0]=301;s.research(ASSET,90,NOW,use_cache=True);assert p.calls==3


def test_dataset_capture_bypasses_an_existing_interactive_cache():
    from dataset_cli import capture
    p,_,s=setup();s.research(ASSET,90,NOW,use_cache=True)
    snapshot=capture('stock',ASSET,90,now=NOW,stocks=s)
    assert p.calls==2 and snapshot['observations'][-1]['date']=='2026-10-14'
    capture('stock',ASSET,90,now=NOW,stocks=s);assert p.calls==3


def test_quota_cooldown_blocks_new_calls_and_never_serves_expired_history():
    p,clock,s=setup();s.research(ASSET,90,NOW,use_cache=True)
    clock[0]=301;p.fail=True
    with pytest.raises(StockDataError) as error:s.research(ASSET,90,NOW,use_cache=True)
    assert error.value.retry_after_seconds==60 and p.calls==2
    with pytest.raises(StockDataError):s.research(ASSET,91,NOW,use_cache=True,refresh=True)
    assert p.calls==2
    clock[0]=362;p.fail=False
    assert s.research(ASSET,90,NOW,use_cache=True)['window']['complete'] and p.calls==3


def test_still_valid_cache_can_be_read_during_another_request_cooldown():
    p,_,s=setup();s.research(ASSET,90,NOW,use_cache=True);p.fail=True
    with pytest.raises(StockDataError):s.research(ASSET,91,NOW,use_cache=True)
    assert s.research(ASSET,90,NOW,use_cache=True)['history_source']['cache_hit'] and p.calls==2
    # Fresh research calls must surface the provider error, not reuse the UI cache.
    with pytest.raises(StockDataError):s.research(ASSET,90,NOW)
    assert p.calls==3


def test_partial_history_stays_explicit_and_refresh_can_recover_it():
    p,_,s=setup();p.missing=True
    first=s.research(ASSET,90,NOW,use_cache=True)
    assert first['indicators'] is None and not first['window']['complete']
    p.missing=False
    recovered=s.research(ASSET,90,NOW,use_cache=True,refresh=True)
    assert recovered['indicators'] is not None and recovered['window']['complete']


def test_cache_capacity_and_concurrent_misses_are_bounded():
    cache=HistoryCache(capacity=1);calls=[];entered=Event();release=Event()
    def fetch():calls.append(1);entered.set();assert release.wait(5);return [{'price':1}]
    with ThreadPoolExecutor(2) as pool:
        first=pool.submit(cache.load,'a',fetch,NOW);assert entered.wait(5)
        second=pool.submit(cache.load,'a',fetch,NOW);release.set()
        assert first.result()[0]==second.result()[0] and len(calls)==1
    cache.load('b',lambda:[],NOW)
    cache.load('a',lambda:calls.append(1) or [],NOW)
    assert len(calls)==2


def test_http_response_exposes_cache_metadata_and_retry_header():
    from fastapi.testclient import TestClient
    from backend import create_app
    from backend_service import BackendService
    p,_,s=setup();app=create_app(BackendService(stocks=s,now=lambda:NOW))
    c=TestClient(app,base_url='http://127.0.0.1:8000')
    params=dict(asset_id=ASSET,days=90)
    assert c.get('/v1/stock-analysis',params=params).json()['history_source']['cache_hit'] is False
    assert c.get('/v1/stock-analysis',params=params).json()['history_source']['cache_hit'] is True
    p.fail=True
    r=c.get('/v1/stock-analysis',params=dict(params,refresh=True))
    assert r.status_code==503 and r.headers['Retry-After']=='60'
    assert p.calls==2


def test_rolling_budget_blocks_fresh_calls_but_allows_cached_history():
    clock=[0.];calls=[]
    cache=HistoryCache(clock=lambda:clock[0],request_limit=2)
    fetch=lambda:calls.append(1) or [{'price':10}]
    cache.load('a',fetch,NOW);clock[0]=10;cache.load('b',fetch,NOW)
    clock[0]=20
    with pytest.raises(StockDataError) as e:cache.load('c',fetch,NOW)
    assert e.value.code=='stock_budget' and e.value.retry_after_seconds==40
    assert cache.load('a',fetch,NOW)[1]['cache_hit'] and len(calls)==2
    with pytest.raises(StockDataError):cache.load('a',fetch,NOW,refresh=True)
    clock[0]=60;cache.load('c',fetch,NOW)
    with pytest.raises(StockDataError) as e:cache.load('d',fetch,NOW)
    assert e.value.retry_after_seconds==10 and len(calls)==3


def test_failed_provider_attempt_consumes_budget_without_changing_capture_behavior():
    clock=[0.];cache=HistoryCache(clock=lambda:clock[0],request_limit=1,budget_window=120,cooldown=10)
    def fail():raise StockDataError('stock_quota','Unavailable')
    with pytest.raises(StockDataError):cache.load('a',fail,NOW)
    clock[0]=11
    with pytest.raises(StockDataError) as e:cache.load('b',lambda:[],NOW)
    assert e.value.code=='stock_budget' and e.value.retry_after_seconds==109
    p,_,s=setup();s.history_cache=HistoryCache(request_limit=1)
    s.research(ASSET,90,NOW,use_cache=True)
    with pytest.raises(StockDataError):s.research(ASSET,91,NOW,use_cache=True)
    s.research(ASSET,91,NOW)
    assert p.calls==2


@pytest.mark.parametrize('limit,window',[(0,60),(True,60),(1,0),(1,float('inf')),(1,True)])
def test_invalid_interactive_budgets_are_rejected(limit,window):
    with pytest.raises(ValueError):HistoryCache(request_limit=limit,budget_window=window)


def test_budget_http_retry_time_and_cache_hit_are_preserved():
    from fastapi.testclient import TestClient
    from backend import create_app
    from backend_service import BackendService
    p,_,s=setup();s.history_cache=HistoryCache(request_limit=1)
    client=TestClient(create_app(BackendService(stocks=s,now=lambda:NOW)),base_url='http://127.0.0.1:8000')
    params=dict(asset_id=ASSET,days=90)
    assert client.get('/v1/stock-analysis',params=params).status_code==200
    response=client.get('/v1/stock-analysis',params=dict(params,refresh=True))
    assert response.status_code==429 and response.json()['error']['code']=='stock_budget'
    assert 1<=int(response.headers['Retry-After'])<=60
    assert client.get('/v1/stock-analysis',params=params).json()['history_source']['cache_hit']
    assert p.calls==1


def test_concurrent_different_misses_share_one_budget():
    cache=HistoryCache(request_limit=2);calls=[]
    def attempt(key):
        try:cache.load(key,lambda:calls.append(key) or [],NOW);return True
        except StockDataError as error:
            assert error.code=='stock_budget';return False
    with ThreadPoolExecutor(8) as pool:results=list(pool.map(attempt,range(8)))
    assert sum(results)==2 and len(calls)==2

"""Offline HTTP contracts, isolation, and real-thread admission tests."""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest
pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient

import api
import data
from backend import create_app
from backend_service import BackendService, BackendError, AdmissionGate
from recommendations import RecommendationError

NOW = pd.Timestamp('2026-09-18T20:00:00Z')


def history(n=90):
    return pd.DataFrame({'price': range(100,100+n), 'volume': [1000]*n},
                        index=pd.date_range(end=NOW.normalize(), periods=n))


def decision():
    return {'action': 'HOLD', 'confidence': 'low', 'confidence_explanation': 'No closed trades.',
            'summary': 'Mixed evidence.', 'reasons': [{'explanation': 'Compare price and moving average.',
            'evidence_keys': ['indicators.latest_history_price_usd','indicators.ma_7']}],
            'risks': [{'explanation': 'No closed trades.', 'evidence_keys': ['backtest.closed_trades','limitations']}]}


class Provider:
    model = 'mock-model'
    def __init__(self): self.calls=[]
    def recommend(self, evidence):
        self.calls.append(evidence)
        return decision()


@pytest.fixture
def setup(monkeypatch):
    provider=Provider()
    calls=[]
    def fetch(coin_id, days, *, persist):
        assert persist is False
        calls.append((coin_id,days))
        return history(days)
    def forbidden(*a,**kw): raise AssertionError('Backend must not touch local storage')
    for name in ('save_price_data','load_price_data','init_database','load_portfolio','save_portfolio','save_backtest_result'):
        monkeypatch.setattr(data,name,forbidden)
    service=BackendService(history_fetcher=fetch,prices_fetcher=lambda:[{'id':'bitcoin', 'current_price':None}],
                           recommender_factory=lambda:provider,now=lambda:NOW)
    with TestClient(create_app(service), base_url="http://127.0.0.1:8000") as client:
        yield client,service,provider,calls


def test_health_prices_and_analysis(setup):
    client,service,provider,calls=setup
    assert client.get('/health').json()=={'status':'ok'}
    assert calls==[]
    markets=client.get('/v1/prices').json()['markets']
    assert markets[0]['current_price'] is None
    assert markets[0]['market_cap'] is None
    response=client.get('/v1/analysis/bitcoin?days=90')
    assert response.status_code==200, response.text
    body=response.json()
    assert body['window']['complete']
    assert body['portfolio']=={'included':False}
    assert provider.calls==[]
    assert calls==[('bitcoin',90)]


def test_backtest_json_and_missing_metrics(setup):
    client,_,_,_=setup
    response=client.post('/v1/backtests',json={'coin_id':'bitcoin','days':30})
    assert response.status_code==200,response.text
    body=response.json()
    assert body['window']['observations']==30
    assert body['summary']['win_rate_pct'] is None
    assert body['summary']['average_closed_trade_return_pct'] is None
    assert body['summary']['asset_max_drawdown_pct']==0
    json.dumps(body,allow_nan=False)


def test_trades_serialize_to_utc_and_dates_stay_in_window(setup):
    client,service,_,_=setup
    values=list(range(100,60,-1))+list(range(65,120))
    raw=pd.DataFrame({'price':values},index=pd.date_range(end=NOW.normalize(),periods=len(values)))
    service.history_fetcher=lambda *a,**k:raw
    response=client.post('/v1/backtests',json={'coin_id':'bitcoin','days':95})
    assert response.status_code==200,response.text
    trades=response.json()['trades']
    assert [t['type'] for t in trades]==['BUY','SELL']
    assert all(t['date'].endswith('+00:00') for t in trades)
    assert trades[0]['pnl'] is None
    assert trades[1]['pnl']>0


def test_recommendation_sends_exact_returned_evidence_once(setup):
    client,_,provider,calls=setup
    response=client.post('/v1/recommendations',json={'coin_id':'bitcoin','selected_position':{'amount':2,'avg_buy_price':100}})
    assert response.status_code==200,response.text
    body=response.json()
    assert body['recommendation_status']=='completed'
    assert body['recommendation']==decision()
    assert body['evidence']==provider.calls[0]
    assert body['evidence']['portfolio']['amount']==2
    assert calls==[('bitcoin',90)]
    assert len(provider.calls)==1


def test_missing_key_returns_evidence_not_500(setup,monkeypatch):
    from llm import OpenAIRecommender
    client,service,_,_=setup
    service.recommender_factory=OpenAIRecommender.from_environment
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    body=client.post('/v1/recommendations',json={'coin_id':'bitcoin'}).json()
    assert body['recommendation_status']=='unavailable'
    assert body['evidence']['portfolio']=={'included':False}
    assert body['recommendation'] is None
    assert body['ai_error']['code']=='ai_unavailable'


@pytest.mark.parametrize('failure', ['exception','invalid'])
def test_provider_failure_retains_evidence_and_releases_gate(setup,failure):
    client,service,provider,calls=setup
    def fail(evidence):
        if failure=='exception': raise RecommendationError('SECRET upstream body')
        result=decision();result['reasons'][0]['evidence_keys']=['invented'];return result
    provider.recommend=fail
    for _ in range(2):
        response=client.post('/v1/recommendations',json={'coin_id':'bitcoin'})
        assert response.status_code==200
        assert response.json()['recommendation_status']=='unavailable'
        assert 'SECRET' not in response.text
    assert len(calls)==2


@pytest.mark.parametrize('endpoint', ['/v1/backtests','/v1/recommendations'])
@pytest.mark.parametrize('fields', [
    {'days':True},{'days':90.0},{'days':'90'},{'days':20},{'days':366},
    {'coin_id':'BTC'},{'coin_id':'../bitcoin'},{'coin_id':''},{'coin_id':'a'*101},
    {'unknown':'SECRET'},
])
def test_bad_requests_rejected_before_upstream(setup,endpoint,fields):
    client,_,_,calls=setup
    response=client.post(endpoint,json={'coin_id':'bitcoin',**fields})
    assert response.status_code==422,response.text
    assert calls==[]
    assert 'SECRET' not in response.text


@pytest.mark.parametrize('position', [{'amount':True},{'amount':'2'},{'amount':-1},{'amount':2,'avg_buy_price':-1},{'amount':2,'secret':'SECRET'}])
def test_invalid_position_is_422(setup,position):
    client,_,_,calls=setup
    response=client.post('/v1/recommendations',json={'coin_id':'bitcoin','selected_position':position})
    assert response.status_code==422
    assert calls==[]


@pytest.mark.parametrize('path', ['/v1/analysis/BTC','/v1/analysis/bitcoin?days=34','/v1/analysis/bitcoin?days=90.5'])
def test_query_validation(setup,path):
    client,_,_,calls=setup
    assert client.get(path).status_code==422
    assert calls==[]


@pytest.mark.parametrize('endpoint', ['/v1/backtests','/v1/recommendations','/v1/analysis/bitcoin'])
@pytest.mark.parametrize('bad', [float('nan'),float('inf'),-1,0,'100','invalid',True])
def test_shared_bad_prices_are_502(setup,endpoint,bad):
    client,service,_,_=setup
    raw=history();raw['price']=raw['price'].astype(object);raw.iloc[-1,raw.columns.get_loc('price')]=bad
    service.history_fetcher=lambda *a,**k:raw
    response=(client.get(endpoint) if endpoint.startswith('/v1/analysis/')
              else client.post(endpoint,json={'coin_id':'bitcoin'}))
    assert response.status_code==502,response.text
    assert response.json()['error']['code']=='invalid_market_data'


@pytest.mark.parametrize('endpoint', ['/v1/backtests','/v1/recommendations','/v1/analysis/bitcoin'])
@pytest.mark.parametrize('case', ['short','stale','duplicate','upstream'])
def test_error_taxonomy(setup,endpoint,case):
    client,service,_,_=setup
    raw=history()
    if case=='short': raw=raw.tail(10)
    if case=='stale': raw.index-=pd.Timedelta(days=5)
    if case=='duplicate': raw=pd.concat([raw,raw.tail(1)])
    def fetch(*a,**k):
        if case=='upstream': raise api.UpstreamError('SECRET')
        return raw
    service.history_fetcher=fetch
    response=(client.get(endpoint) if endpoint.startswith('/v1/analysis/')
              else client.post(endpoint,json={'coin_id':'bitcoin'}))
    assert response.status_code==(503 if case in ('short','stale') else 502),response.text
    assert 'SECRET' not in response.text
    if case in ('short','stale'): assert 'coverage' in response.json()


def test_unexpected_exception_sanitized_and_gate_released(setup):
    client,service,_,_=setup
    def fail(*a,**k): raise RuntimeError('SECRET')
    service.history_fetcher=fail
    for _ in range(2):
        response=client.post('/v1/recommendations',json={'coin_id':'bitcoin'})
        assert response.status_code==500
        assert 'SECRET' not in response.text


def test_real_threads_enforce_capacity_and_release():
    gate=AdmissionGate(2)
    entered=[Event(),Event()];release=Event()
    def work(i):
        with gate.enter():
            entered[i].set()
            assert release.wait(5)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(work,i) for i in range(2)]
        try:
            assert all(event.wait(3) for event in entered)
            with pytest.raises(BackendError) as error:
                with gate.enter(): pass
            assert error.value.status==429
        finally: release.set()
        for future in futures: future.result(timeout=3)
    with pytest.raises(ValueError):
        with gate.enter(): raise ValueError('forced failure')
    with gate.enter(): pass


def test_health_remains_responsive_and_other_work_is_rejected():
    entered=Event();release=Event()
    def fetch(*a,**k):
        entered.set()
        assert release.wait(5)
        return history()
    service=BackendService(history_fetcher=fetch,now=lambda:NOW,market_capacity=1)
    with TestClient(create_app(service), base_url="http://127.0.0.1:8000") as client, ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(client.post,'/v1/backtests',json={'coin_id':'bitcoin'})
        try:
            assert entered.wait(3)
            health=pool.submit(client.get,'/health').result(timeout=2)
            assert health.status_code==200
            busy=pool.submit(client.get,'/v1/analysis/bitcoin').result(timeout=2)
            assert busy.status_code==429
        finally: release.set()
        assert first.result(timeout=3).status_code==200


def test_recommendation_gate_rejects_before_second_fetch(setup):
    client,service,_,calls=setup
    with service.recommendation_gate.enter():
        response=client.post('/v1/recommendations',json={'coin_id':'bitcoin'})
    assert response.status_code==429
    assert calls==[]


@pytest.mark.parametrize('existing', [True,False])
def test_persist_false_does_not_create_or_modify_database(tmp_path,monkeypatch,existing):
    path=tmp_path/'crypto_data.db'
    if existing:path.write_bytes(b'existing database sentinel')
    before=path.stat().st_mtime_ns if existing else None
    monkeypatch.setattr(data,'DB_FILE',str(path))
    monkeypatch.setattr(api,'_get',lambda *a,**k:{'prices':[[1700000000000,100]],'total_volumes':[]})
    assert len(api.fetch_history('bitcoin',90,persist=False))==1
    assert path.exists()==existing
    if existing:
        assert path.stat().st_mtime_ns==before
        assert path.read_bytes()==b'existing database sentinel'


def test_import_and_app_creation_have_no_cli_storage_or_credentials(tmp_path):
    root=str(Path(__file__).resolve().parents[1])
    code='''
import sys
class BlockPresentation:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'ui','main','typer','colorama','tabulate','matplotlib','plotly','mplfinance'}:
            raise AssertionError(fullname)
sys.meta_path.insert(0,BlockPresentation())
import backend
backend.create_app()
'''
    env={k:v for k,v in os.environ.items() if k not in ('OPENAI_API_KEY','OPENAI_MODEL')}
    env.update(PYTHONPATH=root,PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run([sys.executable,'-c',code],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert list(tmp_path.iterdir())==[]


def test_openapi_contract_and_no_cors(setup):
    client,_,_,_=setup
    spec=client.get('/openapi.json').json()
    assert set(spec['paths'])=={'/health','/v1/prices','/v1/analysis/{coin_id}','/v1/backtests','/v1/recommendations'}
    response=client.get('/health',headers={'Origin':'https://example.com'})
    assert 'access-control-allow-origin' not in response.headers


@pytest.mark.parametrize('payload',[{},[],{'prices':None},{'prices':[[1,2,3]]}])
def test_malformed_history_envelope_is_typed_upstream_error(monkeypatch,payload):
    monkeypatch.setattr(api,'_get',lambda *a,**k:payload)
    with pytest.raises(api.UpstreamError): api.fetch_history('bitcoin',90,persist=False)


@pytest.mark.parametrize('field', ['current_price', 'market_cap', 'total_volume'])
def test_negative_market_values_are_upstream_errors(setup, field):
    client, service, _, _ = setup
    service.prices_fetcher = lambda: [{'id': 'bitcoin', field: -5}]
    response = client.get('/v1/prices')
    assert response.status_code == 502
    assert response.json()['error']['code'] == 'invalid_market_data'


@pytest.mark.parametrize('value', [None, 0, 123.5])
def test_nonnegative_and_unknown_market_values_preserved(setup, value):
    client, service, _, _ = setup
    fields = ('current_price', 'market_cap', 'total_volume')
    changes = ('price_change_percentage_1h_in_currency',
               'price_change_percentage_24h_in_currency',
               'price_change_percentage_7d_in_currency')
    service.prices_fetcher = lambda: [{'id': 'bitcoin', **dict.fromkeys(fields, value),
                                       **dict.fromkeys(changes, -5.5)}]
    response = client.get('/v1/prices')
    assert response.status_code == 200
    market = response.json()['markets'][0]
    assert all(market[field] == value for field in fields)
    assert all(market[field] == -5.5 for field in changes)

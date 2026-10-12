from datetime import datetime, timezone
import pytest
from assets import Asset, crypto_asset
from stock_provider import TwelveData, StockDataError
from stock_service import StockService, session_window

NOW = datetime(2026, 9, 28, 22, tzinfo=timezone.utc)
A = Asset('stock', 'twelvedata', 'ABC', 'Example', 'XNYS', 'USD', 'America/New_York')


class Response:
    status_code = 200
    def __init__(self, payload): self.payload = payload
    def json(self): return self.payload


def test_identity_is_exchange_and_class_qualified():
    other = Asset('stock', 'twelvedata', 'ABC', 'Example', 'XNAS', 'USD', 'America/New_York')
    assert A.id != other.id
    assert crypto_asset(dict(id='bitcoin', name='Bitcoin')).id == 'coingecko:crypto:XCRY:USD:bitcoin'


@pytest.mark.parametrize('mic', ['XNGS', 'XNMS', 'XNCM'])
def test_nasdaq_segment_catalog_and_history_preserve_mic(mic):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith('/stocks'):
            return Response({'data': [dict(symbol='ABC', name='Example', mic_code=mic, currency='USD', country='United States')]})
        if url.endswith('/etf'):
            return Response({'data': []})
        body = payload()
        body['meta']['mic_code'] = mic
        return Response(body)
    provider = TwelveData(key='test-placeholder', get=get)
    asset, = provider.catalog()
    assert asset.exchange == mic and f':{mic}:' in asset.id
    assert provider.history(asset, '2026-09-01', '2026-09-30')[0]['close'] == 11
    assert calls[-1][1]['params']['mic_code'] == mic


def test_missing_key_makes_no_request():
    with pytest.raises(StockDataError, match='TWELVE_DATA_API_KEY'):
        TwelveData(get=lambda *a, **k: pytest.fail('network')).catalog()


def test_large_reference_catalog_has_longer_read_timeout():
    calls = []
    def get(url, **kwargs):
        calls.append(kwargs)
        return Response({'data': []})
    provider = TwelveData(key='test-placeholder', get=get)
    provider.request('stocks', {})
    provider.request('etf', {})
    provider.request('time_series', {})
    assert [call['timeout'] for call in calls] == [(10, 45), (10, 45), 15]
    assert all(call['allow_redirects'] is False for call in calls)


@pytest.mark.parametrize('status,code', [(429,'stock_quota'),(401,'stock_access'),(403,'stock_access'),(500,'stock_unavailable'),(302,'stock_unavailable')])
def test_transport_error_is_sanitized(status,code):
    r = Response({'message':'secret'}); r.status_code=status
    with pytest.raises(StockDataError) as error:
        TwelveData(key='private-key',get=lambda *a,**k:r).catalog()
    assert error.value.code == code
    assert 'secret' not in str(error.value) and 'private-key' not in str(error.value)


def payload():
    return dict(meta=dict(symbol='ABC',mic_code='XNYS',currency='USD',interval='1day',exchange_timezone='America/New_York'),
                values=[dict(datetime='2026-09-25',open='10',high='12',low='9',close='11',volume='100')])


def test_history_request_and_validation():
    calls=[]
    def get(url, **kwargs): calls.append((url,kwargs)); return Response(payload())
    rows=TwelveData(key='key',get=get).history(A,'2026-09-01','2026-09-28')
    assert rows[0]['close']==11
    options=calls[0][1]
    assert options['params']['adjust']=='splits' and options['params']['mic_code']=='XNYS'
    assert 'apikey' not in options['params'] and options['headers']['Authorization']=='apikey key'
    assert options['allow_redirects'] is False


@pytest.mark.parametrize('field,value',[('close','nan'),('close',True),('low','13'),('volume','-1'),('datetime','2026-02-30')])
def test_bad_bars_rejected(field,value):
    p=payload(); p['values'][0][field]=value
    with pytest.raises(StockDataError): TwelveData(key='k',get=lambda *a,**k:Response(p)).history(A,'2026-01-01','2026-12-31')


def test_wrong_exchange_and_duplicate_dates_rejected():
    p=payload(); p['meta']['mic_code']='XNAS'
    with pytest.raises(StockDataError): TwelveData(key='k',get=lambda *a,**k:Response(p)).history(A,'2026-01-01','2026-12-31')
    p=payload(); p['values']*=2
    with pytest.raises(StockDataError): TwelveData(key='k',get=lambda *a,**k:Response(p)).history(A,'2026-01-01','2026-12-31')


def test_holiday_weekend_and_current_session():
    _,_,sessions=session_window(90,datetime(2026,9,8,18,tzinfo=timezone.utc))
    assert '2026-09-07' not in sessions # Labor Day
    assert '2026-09-06' not in sessions
    assert '2026-09-08' not in sessions # still trading
    assert sessions[-1]=='2026-09-04'


def test_early_close():
    _,_,before=session_window(35,datetime(2026,11,27,17,59,tzinfo=timezone.utc))
    _,_,after=session_window(35,datetime(2026,11,27,18,1,tzinfo=timezone.utc))
    assert '2026-11-27' not in before and after[-1]=='2026-11-27'


class Provider:
    def __init__(self): self.calls=0; self.fail=False; self.missing=False
    def catalog(self):
        self.calls+=1
        if self.fail: raise StockDataError('stock_unavailable','Unavailable')
        return [A]
    def history(self,asset,start,end):
        _,_,sessions=session_window(90,NOW)
        return [dict(date=d,open=100+i,high=102+i,low=99+i,close=101+i,volume=1000) for i,d in enumerate(sessions) if not(self.missing and i==20)]


def test_complete_research_and_missing_session_suppresses_indicators():
    p=Provider(); s=StockService(provider=p)
    result=s.research(A.id,90,NOW)
    assert result['window']['complete'] and result['indicators']['rsi_14']==100
    assert all(not r['break_before'] for r in result['history'])
    p.missing=True; result=s.research(A.id,90,NOW)
    assert result['indicators'] is None and len(result['window']['missing_sessions'])==1
    assert sum(r['break_before'] for r in result['history'])==1
    assert all(r['ma_7'] is None for r in result['history'])


def test_cache_and_stale_fallback():
    clock=[0]; p=Provider(); s=StockService(provider=p,clock=lambda:clock[0])
    assert not s.catalog(NOW)['stale']; s.catalog(NOW); assert p.calls==1
    clock[0]=86401; p.fail=True
    assert s.catalog(NOW)['stale']; s.catalog(NOW); assert p.calls==2


def test_api_setup_and_validation():
    from fastapi.testclient import TestClient
    from backend import create_app
    with TestClient(create_app(),base_url='http://127.0.0.1:8000') as c:
        response=c.get('/v1/assets?asset_class=stock')
        assert response.status_code==503 and response.json()['error']['code']=='stock_setup_required'
        assert c.get('/v1/assets?asset_class=invalid').status_code==422
        assert c.get('/v1/stock-analysis?asset_id=x&days=0').status_code==422


def test_api_research_contract():
    from fastapi.testclient import TestClient
    from backend import create_app
    from backend_service import BackendService
    service=BackendService(stocks=StockService(provider=Provider()),now=lambda:NOW)
    with TestClient(create_app(service),base_url='http://127.0.0.1:8000') as c:
        listings=c.get('/v1/assets?asset_class=stock')
        assert listings.status_code==200 and listings.json()['assets'][0]['id']==A.id
        response=c.get('/v1/stock-analysis',params={'asset_id':A.id,'days':90})
        assert response.status_code==200 and response.json()['adjustment']=='splits'
        assert response.json()['window']['complete']
        assert c.get('/v1/stock-analysis',params={'asset_id':'unknown','days':90}).status_code==404


def test_catalog_filters_unsupported_identity_and_retains_exchange_duplicates():
    rows=[dict(symbol='ABC',name='Example',mic_code=mic,currency=currency,country='United States')
          for mic,currency in [('XNYS','USD'),('XNAS','USD'),('XLON','GBP'),('','USD')]]
    provider=TwelveData(key='k',get=lambda url,**kwargs:Response({'data':rows if url.endswith('/stocks') else []}))
    assets=provider.catalog()
    assert len(assets)==2 and len({a.id for a in assets})==2


@pytest.mark.parametrize('code',[401,403,429,400])
def test_provider_error_envelope(code):
    p=TwelveData(key='k',get=lambda *a,**k:Response(dict(status='error',code=code,message='secret raw text')))
    with pytest.raises(StockDataError) as error: p.catalog()
    assert 'secret' not in str(error.value)


def test_no_live_stock_requests_escape_guard(monkeypatch):
    monkeypatch.setenv('TWELVE_DATA_API_KEY','test-placeholder')
    with pytest.raises(AssertionError,match='Live HTTP'):
        TwelveData().catalog()


def test_decade_history_and_short_windows():
    start, end, sessions = session_window(3653, NOW)
    assert start <= '2016-09-28'
    assert 2400 < len(sessions) < 2700
    assert len(session_window(30, NOW)[2]) < 25
    for invalid in (0, 3661, True, 35.5):
        with pytest.raises(ValueError): session_window(invalid, NOW)


def test_ten_year_api_returns_partial_coverage_without_inventing_older_bars():
    from fastapi.testclient import TestClient
    from backend import create_app
    from backend_service import BackendService
    service = BackendService(stocks=StockService(provider=Provider()), now=lambda:NOW)
    with TestClient(create_app(service), base_url='http://127.0.0.1:8000') as client:
        result = client.get('/v1/stock-analysis',params={'asset_id':A.id,'days':3653})
        assert result.status_code == 200
        body = result.json()
        assert body['window']['expected_sessions'] > 2400
        assert not body['window']['complete'] and body['indicators'] is None
        assert body['history'][0]['date'] >= '2026-06-01'
        assert client.get('/v1/stock-analysis',params={'asset_id':A.id,'days':3661}).status_code == 422

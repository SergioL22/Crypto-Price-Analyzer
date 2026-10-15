from datetime import datetime,timezone,timedelta
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from account_backend import create_app
from account_settings import AccountSettings
from account_research import Research,SampleProvider
from stock_service import StockService
from prediction_journal import Journal
from recommendations import RecommendationError
from market_assessment import Assessments,evidence
from account_store import AccountError

NOW=datetime(2026,10,13,17,tzinfo=timezone.utc);ORIGIN='http://127.0.0.1:8001';ASSET='twelvedata:stock:XNYS:USD:DEMO'


def decision():return dict(action='HOLD',confidence='low',summary='Conflicting historical signals.',confidence_explanation='Historical evidence is not measured prediction accuracy.',reasons=[dict(evidence_keys=['history.latest_price_usd'],explanation='Review the latest historical price.')],risks=[dict(evidence_keys=['limitations'],explanation='Trading costs and future uncertainty remain.')])


@pytest.fixture
def environment(tmp_path):
    captured=[]
    class FakeAI:
        def recommend(self,data):captured.append(deepcopy(data));return decision()
    settings=AccountSettings(ORIGIN,'sqlite:///'+(tmp_path/'accounts.db').as_posix(),'test-signing-secret-at-least-32-characters',demo=True)
    research=Research(sample=False,stocks=StockService(provider=SampleProvider()),now=lambda:NOW)
    app=create_app(settings,research=research,assessment_factory=FakeAI,journal=Journal(tmp_path/'journal.db'))
    yield app,captured,research
    app.state.store.engine.dispose()


def client(app,profile='avery'):
    c=TestClient(app,base_url=ORIGIN,client=('127.0.0.1',50000));assert c.post('/auth/demo',json={'profile':profile},headers={'Origin':ORIGIN}).status_code==200
    c.headers.update({'Origin':ORIGIN,'X-CSRF-Token':c.get('/v2/session').json()['csrf_token']});return c


def analyze(c):
    r=c.get('/v2/research/analysis',params=dict(kind='stock',asset_id=ASSET,days=90));assert r.status_code==200,r.text
    return r.json()['analysis_token']


def test_no_auto_ai_and_snapshot_citations_use_displayed_values(environment):
    app,captured,_=environment;c=client(app);token=analyze(c);assert not captured
    response=c.post('/v2/research/recommendation',json=dict(analysis_token=token));assert response.status_code==200,response.text
    data=response.json();assert data['source']=='openai' and data['evidence']['position']=={'included':False}
    assert data['prediction']==dict(promoted=False,calibrated=False,accuracy=None)
    assert 'account_id' not in captured[0] and 'session' not in captured[0]
    assert c.post('/v2/research/recommendation',json=dict(analysis_token=token)).status_code==429
    assert len(captured)==1


def test_token_requires_csrf_same_session_and_current_history(environment):
    app,captured,research=environment;a=client(app);b=client(app,'sam');token=analyze(a)
    assert b.post('/v2/research/recommendation',json=dict(analysis_token=token)).status_code==409
    assert a.post('/v2/research/recommendation',json=dict(analysis_token=token),headers={'X-CSRF-Token':''}).status_code==403
    research.now=lambda:NOW+timedelta(days=1)
    assert a.post('/v2/research/recommendation',json=dict(analysis_token=token)).status_code==409
    assert not captured


def test_position_requires_opt_in_and_includes_only_selected_asset(environment):
    app,captured,_=environment;c=client(app)
    holdings=[dict(id=ASSET,quantity=2,cost=10),dict(id='twelvedata:etf:ARCX:USD:FUND',quantity=100,cost=500)]
    assert c.put('/v2/workspace',json=dict(revision=0,workspace=dict(version=1,listings=[],holdings=holdings,alerts=[]))).status_code==200
    token=analyze(c);r=c.post('/v2/research/recommendation',json=dict(analysis_token=token,include_position=True));assert r.status_code==200
    assert captured[0]['position']==dict(included=True,quantity=2,average_cost_usd=10)
    assert 'FUND' not in str(captured[0]) and 'csrf' not in str(captured[0])


def test_bad_signature_and_expired_snapshot_are_rejected():
    a=Assessments('secret');data=Research(now=lambda:NOW).analyze('stock',ASSET,90);session={'token_hash':'session'}
    token=a.bind(data,session)
    with pytest.raises(AccountError):a.read(token+'x',session,NOW)
    with pytest.raises(AccountError):a.read(token,{'token_hash':'other'},NOW)
    # A correctly signed token with an old timestamp must still fail age validation.
    signer=a.serializer.make_signer();signer.get_timestamp=lambda:1
    old_token=signer.sign(a.serializer.dump_payload(dict(session='session',evidence=evidence(data)))).decode()
    with pytest.raises(AccountError):a.read(old_token,session,NOW)


def test_incomplete_history_cannot_create_ai_token():
    data=Research(now=lambda:NOW).analyze('stock',ASSET,90);data['window']['complete']=False
    assert Assessments('secret').bind(data,{'token_hash':'x'}) is None


def test_unknown_citations_are_rejected_and_raw_analysis_survives():
    class BadAI:
        def recommend(self,data):r=decision();r['reasons'][0]['evidence_keys']=['invented'];return r
    data=Research(now=lambda:NOW).analyze('stock',ASSET,90)
    data['data_mode']='local-live'
    with pytest.raises(RecommendationError):Assessments('secret',factory=BadAI).recommend(evidence(data))
    assert data['history'] and data['indicators']


def test_zero_closed_trades_is_not_a_zero_percent_win_rate():
    data=Research(now=lambda:NOW).analyze('stock',ASSET,90)
    for p in data['history']:p['price']=100
    e=evidence(data)
    assert e['backtest']['closed_trades']==0 and e['backtest']['win_rate_pct'] is None
    assert Assessments('secret').recommend(e)['source']=='offline-sample'


def test_validation_is_authenticated_and_read_only(environment):
    app,_,_=environment;c=client(app)
    r=c.get('/v2/research/validation',params=dict(asset_id=ASSET));assert r.status_code==200 and r.json()['completed']==0
    c.post('/auth/logout');assert c.get('/v2/research/validation').status_code==401


def test_provider_failure_is_sanitized_and_does_not_destroy_analysis(environment,monkeypatch):
    app,_,_=environment;c=client(app);token=analyze(c)
    def unavailable(*args):raise RecommendationError('Private credential details must not be returned')
    monkeypatch.setattr(Assessments,'recommend',unavailable)
    r=c.post('/v2/research/recommendation',json=dict(analysis_token=token))
    assert r.status_code==503 and 'Private credential' not in r.text
    assert c.get('/v2/session').status_code==200 and analyze(c)


def test_logout_during_provider_call_discards_the_result(environment,monkeypatch):
    app,_,_=environment;c=client(app);token=analyze(c)
    def revoke(*args):
        app.state.store.logout(app.state.store.session(c.cookies.get('research-session')))
        return dict(source='openai',recommendation=decision())
    monkeypatch.setattr(Assessments,'recommend',revoke)
    assert c.post('/v2/research/recommendation',json=dict(analysis_token=token)).status_code==401

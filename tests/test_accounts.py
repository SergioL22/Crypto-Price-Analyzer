from copy import deepcopy
import json
import pytest
from fastapi.testclient import TestClient
from account_backend import create_app
from account_settings import AccountSettings
from account_store import AccountStore,AccountError

ORIGIN='http://127.0.0.1:8001'
ASSET='twelvedata:stock:XNYS:USD:DEMO'


@pytest.fixture
def environment(tmp_path):
    clock=[100000.0]
    settings=AccountSettings(ORIGIN,'sqlite:///'+(tmp_path/'accounts.db').as_posix(),'test-signing-secret-at-least-32-characters',demo=True)
    store=AccountStore(settings.database_url,clock=lambda:clock[0])
    app=create_app(settings,store)
    yield app,store,clock
    store.engine.dispose()


def client(app,profile='avery'):
    c=TestClient(app,base_url=ORIGIN,client=("127.0.0.1",50000))
    assert c.post('/auth/demo',json={'profile':profile},headers={'Origin':ORIGIN}).status_code==200
    me=c.get('/v2/session').json()
    c.headers.update({'Origin':ORIGIN,'X-CSRF-Token':me['csrf_token']})
    return c,me


def data():return dict(version=1,listings=[dict(id=ASSET,name='Demo')],holdings=[dict(id=ASSET,quantity=2,cost=10)],alerts=[])


def test_users_are_isolated_and_owner_fields_cannot_override_session(environment):
    app,_,_=environment;a,alice=client(app);b,bob=client(app,'sam')
    assert alice['account_id']!=bob['account_id']
    assert a.put('/v2/workspace',json=dict(revision=0,workspace=data())).status_code==200
    assert b.get('/v2/workspace',params={'owner':alice['account_id']}).json()['workspace']['holdings']==[]
    malicious=dict(revision=0,workspace=data(),owner=alice['account_id'])
    assert b.put('/v2/workspace',json=malicious).status_code==422
    assert TestClient(app,base_url=ORIGIN,client=("127.0.0.1",50000)).get('/v2/workspace').status_code==401
    assert b.get('/v2/export').json()['holdings']==[]


def test_csrf_host_origin_and_logout_revocation(environment):
    app,_,_=environment;c,_=client(app)
    token=c.cookies.get('research-session')
    assert c.put('/v2/workspace',json=dict(revision=0,workspace=data()),headers={'X-CSRF-Token':''}).status_code==403
    assert c.put('/v2/workspace',json=dict(revision=0,workspace=data()),headers={'Origin':'https://evil.example'}).status_code==403
    assert c.get('/v2/workspace',headers={'Host':'evil.example'}).status_code==403
    assert c.post('/auth/logout').status_code==200
    c.cookies.set('research-session',token)
    assert c.get('/v2/workspace').status_code==401


def test_import_preview_is_bound_to_account_session_revision_and_one_use(environment):
    app,_,_=environment;a,_=client(app);b,_=client(app,'sam');second,_=client(app)
    preview=a.post('/v2/import/preview',json=data()).json()
    assert a.get('/v2/workspace').json()['revision']==0
    assert preview['incoming']['holdings']==1 and preview['existing']['holdings']==0
    confirm=dict(token=preview['token'],confirm=True)
    assert b.post('/v2/import/confirm',json=confirm).status_code==404
    assert second.post('/v2/import/confirm',json=confirm).status_code==404
    assert a.post('/v2/import/confirm',json=dict(token=preview['token'],confirm=1)).status_code==422
    result=a.post('/v2/import/confirm',json=confirm)
    assert result.status_code==200 and result.json()['workspace']==data()
    assert a.post('/v2/import/confirm',json=confirm).status_code==404
    preview=a.post('/v2/import/preview',json=data()).json()
    assert a.put('/v2/workspace',json=dict(revision=1,workspace=dict(version=1,listings=[],holdings=[],alerts=[]))).status_code==200
    assert a.post('/v2/import/confirm',json=dict(token=preview['token'],confirm=True)).status_code==409
    assert a.get('/v2/workspace').json()['workspace']['holdings']==[]


def test_expiry_and_cookie_security(environment):
    app,_,clock=environment;c,_=client(app)
    preview=c.post('/v2/import/preview',json=data()).json();clock[0]+=601
    assert c.post('/v2/import/confirm',json=dict(token=preview['token'],confirm=True)).status_code==404
    clock[0]+=8*3600
    assert c.get('/v2/session').status_code==401
    anon=TestClient(app,base_url=ORIGIN,client=("127.0.0.1",50000))
    assert anon.post('/auth/demo',json=dict(profile='avery')).status_code==403
    login=anon.post('/auth/demo',json=dict(profile='avery'),headers={'Origin':ORIGIN},follow_redirects=False)
    assert 'HttpOnly' in login.headers['set-cookie'] and 'SameSite=lax' in login.headers['set-cookie']


@pytest.mark.parametrize('bad',[{'version':True,'listings':[],'holdings':[],'alerts':[]},
                                {'version':1,'listings':[{'id':ASSET,'name':'x'}]*2,'holdings':[],'alerts':[]},
                                {'version':1,'listings':[],'holdings':[{'id':ASSET,'quantity':0,'cost':0}],'alerts':[]},
                                {'version':1,'listings':[],'holdings':[],'alerts':[{'id':ASSET,'type':'rsi','direction':'above','threshold':101,'triggered':False}]}])
def test_invalid_import_leaves_workspace_unchanged(environment,bad):
    app,_,_=environment;c,_=client(app)
    response=c.post('/v2/import/preview',json=bad)
    assert response.status_code==422 and 'input' not in response.text
    assert c.get('/v2/workspace').json()['revision']==0


def test_size_rate_limit_and_legacy_routes_are_not_exposed(environment):
    app,_,_=environment;c,_=client(app)
    assert c.post('/v2/import/preview',content=b'x'*500001).status_code==413
    for _ in range(10):assert c.post('/v2/import/preview',json=data()).status_code==200
    assert c.post('/v2/import/preview',json=data()).status_code==429
    for path in ('/v1/portfolio','/v1/holdings','/v1/alerts','/v1/recommendation','/docs','/openapi.json'):
        assert c.get(path).status_code==404
    assert c.get('/').headers['Cache-Control']=='no-store'


def test_optimistic_updates_preserve_the_winner(environment):
    app,_,_=environment;c,_=client(app)
    assert c.put('/v2/workspace',json=dict(revision=0,workspace=data())).status_code==200
    assert c.put('/v2/workspace',json=dict(revision=0,workspace=dict(version=1,listings=[],holdings=[],alerts=[]))).status_code==409
    assert c.get('/v2/workspace').json()['workspace']==data()


def test_settings_fail_closed_without_production_identity_config():
    with pytest.raises(ValueError):AccountSettings('http://example.com','sqlite:///x.db','x'*32,demo=True)
    with pytest.raises(ValueError):AccountSettings('http://127.0.0.1:8001','sqlite:///x.db','x'*32)
    with pytest.raises(ValueError):AccountSettings('https://example.com','sqlite:///x.db','x'*32)


def test_logout_discards_previews_and_new_login_rotates_tokens(environment):
    app,_,_=environment;c,_=client(app);token=c.cookies.get('research-session')
    preview=c.post('/v2/import/preview',json=data()).json()
    c.post('/auth/demo',json=dict(profile='sam'))
    assert c.cookies.get('research-session')!=token
    c.headers['X-CSRF-Token']=c.get('/v2/session').json()['csrf_token']
    assert c.post('/v2/import/confirm',json=dict(token=preview['token'],confirm=True)).status_code==404
    assert c.get('/v2/workspace').json()['workspace']['holdings']==[]


def test_parallel_edits_and_imports_have_only_one_winner(environment):
    from concurrent.futures import ThreadPoolExecutor
    _,store,_=environment
    session=store.session(store.login('test-issuer','owner','Owner'))
    def edit(name):
        payload=data();payload['listings'][0]['name']=name
        try:return store.save(session['owner'],0,payload)['workspace']['listings'][0]['name']
        except AccountError as error:return error.code
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(edit,['first','second']))
    assert results.count('workspace_changed')==1
    assert store.read(session['owner'])['revision']==1
    preview=store.preview(session,data())
    def confirm(_):
        try:return store.confirm(session,preview['token'])['revision']
        except AccountError as error:return error.code
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(confirm,[1,2]))
    assert results.count(2)==1 and results.count('preview_unavailable')==1


def test_streamed_oversized_import_does_not_modify_data(environment):
    app,_,_=environment;c,_=client(app)
    response=c.post('/v2/import/preview',content=iter([b'x'*300000,b'x'*300000]),headers={'Content-Type':'application/json'})
    assert response.status_code in (400,413)
    assert c.get('/v2/workspace').json()['revision']==0


def test_cancel_revokes_preview_without_mutating_workspace(environment):
    app,_,_=environment;c,_=client(app)
    preview=c.post('/v2/import/preview',json=data()).json()
    assert c.delete('/v2/import/preview').status_code==200
    assert c.post('/v2/import/confirm',json=dict(token=preview['token'],confirm=True)).status_code==404
    assert c.get('/v2/workspace').json()['revision']==0


def test_sample_mode_rejects_remote_clients_even_with_forged_origin_and_host(environment):
    app,_,_=environment
    remote=TestClient(app,base_url=ORIGIN,client=('203.0.113.10',50000))
    assert remote.post('/auth/demo',json={'profile':'avery'},headers={'Origin':ORIGIN}).status_code==403
    assert remote.get('/').status_code==403

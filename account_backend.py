"""Isolated account API. Does not mount legacy unauthenticated application routes."""
from pathlib import Path
import secrets
import ipaddress
from urllib.parse import urlsplit
from fastapi import FastAPI,Request,Query
from fastapi.responses import JSONResponse,FileResponse,RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware
from starlette.concurrency import run_in_threadpool
from account_settings import AccountSettings
from account_store import AccountStore,AccountError
from account_models import Workspace,WorkspaceUpdate,ImportConfirm,DemoLogin,AssessmentRequest
from market_assessment import Assessments
from recommendations import RecommendationError
from prediction_validation import report as validation_report
from prediction_journal import Journal
import hashlib
from backend_service import BackendError,AdmissionGate
from stock_provider import StockDataError
from api import UpstreamError

ROOT=Path(__file__).parent


def create_app(settings=None,store=None,identity=None,research=None,assessment_factory=None,journal=None):
    settings=settings or AccountSettings.from_environment()
    store=store or AccountStore(settings.database_url)
    from account_research import Research,DisabledResearch
    research=research or (Research() if settings.demo else DisabledResearch())
    assessments=Assessments(settings.state_secret,factory=assessment_factory)
    assessment_gate=AdmissionGate(1)
    journal=journal or Journal()
    if not settings.demo and research.mode=='local-live':raise ValueError('Private live provider adapter is loopback-only')
    if not settings.demo and identity is None:
        from account_auth import ManagedOIDC
        identity=ManagedOIDC(settings)
    app=FastAPI(title='Research Desk Accounts',version='0.5.0',docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store=store;app.state.settings=settings
    cookie='research-session' if settings.demo else '__Host-research-session'
    app.add_middleware(SessionMiddleware,secret_key=settings.state_secret,session_cookie='oidc-state' if settings.demo else '__Host-oidc-state',
                       max_age=600,same_site='lax',https_only=not settings.demo)

    @app.exception_handler(AccountError)
    async def account_error(request,error):
        messages={'sign_in_required':'Sign in to access your workspace.','workspace_changed':'Your workspace changed. Reload it and review your changes.',
                  'assessment_expired':'Analysis expired or belongs to another session. Run analysis again.',
                  'assessment_history':'AI assessment requires complete recent history and valid indicators.',
                  'market_not_enabled':'Market data is not enabled for this deployment.',
                  'history_unavailable':'No completed historical observations are available.',
                  'crypto_window':'Crypto history supports up to 364 completed days.',
                  'asset_mismatch':'Choose an asset from the selected market.',
                  'asset_unavailable':'Choose an available asset from the market list.',
                  'preview_unavailable':'This preview expired or is unavailable. Preview the import again.',
                  'rate_limited':'Too many requests. Wait a minute and try again.'}
        return JSONResponse(status_code=error.status,content={'error':{'code':error.code,'message':messages.get(error.code,'The request could not be authorized.')}},
                            headers={'Retry-After':'60'} if error.status==429 else None)

    @app.exception_handler(RequestValidationError)
    async def invalid(request,error):
        return JSONResponse(status_code=422,content={'error':{'code':'invalid_request','message':'Fields do not match the account workspace format.'}})

    @app.exception_handler(BackendError)
    async def capacity_error(request,error):return JSONResponse(status_code=error.status,content={'error':{'code':error.code,'message':'Research is busy. Try again later.'}})

    @app.exception_handler(StockDataError)
    async def stock_error(request,error):return JSONResponse(status_code=503,content={'error':{'code':error.code,'message':'Stock data is unavailable. Check provider setup or quota, then retry manually.'}})

    @app.exception_handler(RecommendationError)
    async def assessment_error(request,error):return JSONResponse(status_code=503,content={'error':{'code':'assessment_unavailable','message':'AI assessment unavailable. Check OpenAI setup or quota; raw analysis remains available. No automatic retry.'}})

    @app.exception_handler(UpstreamError)
    async def crypto_error(request,error):return JSONResponse(status_code=503,content={'error':{'code':'crypto_unavailable','message':'Crypto history is unavailable. Retry manually later.'}})

    @app.middleware('http')
    async def boundary(request,call_next):
        if settings.demo:
            try:loopback=ipaddress.ip_address(request.client.host).is_loopback
            except (ValueError,AttributeError):loopback=False
            if not loopback:return JSONResponse(status_code=403,content={'error':{'code':'staging_local_only','message':'Sample accounts are available only on loopback.'}})
        authority=urlsplit(settings.origin).netloc
        if (request.headers.getlist('host')!=[authority] or request.headers.getlist('origin') not in ([],[settings.origin])
                or not settings.demo and request.url.scheme!='https'):
            return JSONResponse(status_code=403,content={'error':{'code':'origin_forbidden','message':'Origin is not allowed.'}})
        if request.method not in ('GET','HEAD') and request.headers.getlist('origin')!=[settings.origin]:
            return JSONResponse(status_code=403,content={'error':{'code':'origin_required','message':'Same-origin request required.'}})
        length=request.headers.get('content-length','0')
        if not length.isdigit() or int(length)>500000:
            return JSONResponse(status_code=413,content={'error':{'code':'too_large','message':'Request exceeds 500 KB.'}})
        # Bound bodies even when a caller omits Content-Length or streams chunks.
        received=0;original=request._receive
        async def limited_receive():
            nonlocal received
            message=await original()
            received+=len(message.get('body',b''))
            if received>500000:raise AccountError('too_large',413)
            return message
        request._receive=limited_receive
        try:response=await call_next(request)
        except Exception:
            response=JSONResponse(status_code=500,content={'error':{'code':'internal_error','message':'Unexpected account service error.'}})
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
        if not settings.demo:response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    def authenticated(request,write=False):
        session=store.session(request.cookies.get(cookie))
        if write and not secrets.compare_digest(request.headers.get('x-csrf-token',''),session['csrf']):raise AccountError('csrf_required',403)
        return session

    def login_response(token,redirect=True):
        response=RedirectResponse('/',status_code=303) if redirect else JSONResponse({'signed_in':True})
        response.set_cookie(cookie,token,max_age=8*3600,httponly=True,secure=not settings.demo,samesite='lax',path='/')
        return response

    @app.get('/health')
    def health():return {'status':'ok','mode':'sample-staging' if settings.demo else 'accounts'}

    @app.get('/v2/config')
    def config():return {'demo':settings.demo,'market_data':research.mode,'sign_in_url':None if settings.demo else '/auth/login'}

    @app.get('/auth/login')
    async def login(request:Request):
        if settings.demo:raise AccountError('demo_only',404)
        await run_in_threadpool(store.throttle,'login:'+request.client.host)
        try:return await identity.begin(request,settings.origin+'/auth/callback')
        except Exception:raise AccountError('identity_unavailable',503) from None

    @app.get('/auth/callback')
    async def callback(request:Request):
        if settings.demo:raise AccountError('demo_only',404)
        await run_in_threadpool(store.throttle,'callback:'+request.client.host)
        try:
            claims=await identity.complete(request)
            if claims['issuer']!=settings.issuer:raise ValueError('Issuer mismatch')
            old=request.cookies.get(cookie)
            if old:
                try:await run_in_threadpool(store.logout,store.session(old))
                except AccountError:pass
            token=await run_in_threadpool(store.login,claims['issuer'],claims['subject'],claims['name'])
            request.session.clear()
            return login_response(token)
        except Exception:
            request.session.clear()
            raise AccountError('invalid_identity',401) from None

    @app.post('/auth/demo')
    def demo(body:DemoLogin,request:Request):
        if not settings.demo:raise AccountError('demo_only',404)
        store.throttle('demo:'+request.client.host)
        old=request.cookies.get(cookie)
        if old:
            try:store.logout(store.session(old))
            except AccountError:pass
        return login_response(store.login('sample-staging',body.profile,'Avery (sample)' if body.profile=='avery' else 'Sam (sample)'),redirect=False)

    @app.get('/v2/session')
    def me(request:Request):
        session=authenticated(request)
        return {'account_id':session['owner'],'name':session['name'],'csrf_token':session['csrf'],'expires_at':session['expires']}

    @app.post('/auth/logout')
    def logout(request:Request):
        store.logout(authenticated(request,True));response=JSONResponse({'signed_out':True});response.delete_cookie(cookie,path='/');return response

    @app.get('/v2/workspace')
    def workspace(request:Request):
        session=authenticated(request)
        return dict(store.read(session['owner']),account_id=session['owner'])

    @app.put('/v2/workspace')
    def save_workspace(body:WorkspaceUpdate,request:Request):
        session=authenticated(request,True);store.throttle('write:'+session['owner'],60)
        return store.save(session['owner'],body.revision,body.workspace.model_dump())

    @app.post('/v2/import/preview')
    def preview(body:Workspace,request:Request):
        session=authenticated(request,True);store.throttle('preview:'+session['owner'],10)
        return store.preview(session,body.model_dump())

    @app.post('/v2/import/confirm')
    def confirm(body:ImportConfirm,request:Request):return store.confirm(authenticated(request,True),body.token)

    @app.delete('/v2/import/preview')
    def cancel(request:Request):store.cancel_preview(authenticated(request,True));return {'canceled':True}

    @app.get('/v2/export')
    def export(request:Request):
        payload=store.read(authenticated(request)['owner'])['workspace']
        return JSONResponse(payload,headers={'Content-Disposition':'attachment; filename="account-workspace.json"'})

    @app.get('/v2/research/assets')
    def research_assets(request:Request,kind:str=Query(pattern='^(stock|etf|crypto)$')):
        session=authenticated(request);store.throttle('catalog:'+session['owner'],6)
        return research.catalog(kind)

    @app.get('/v2/research/analysis')
    def research_analysis(request:Request,kind:str=Query(pattern='^(stock|etf|crypto)$'),asset_id:str=Query(min_length=1,max_length=160),days:int=Query(ge=35,le=3660)):
        session=authenticated(request);store.throttle('research:'+session['owner'],6)
        data=research.analyze(kind,asset_id,days)
        data['analysis_token']=assessments.bind(data,session)
        return data

    @app.get('/v2/research/validation')
    def validation(request:Request,asset_id:str|None=Query(default=None,max_length=160)):
        session=authenticated(request);store.throttle('validation:'+session['owner'],6)
        if not settings.demo:raise AccountError('market_not_enabled',503)
        return validation_report(journal,asset_id)

    @app.post('/v2/research/recommendation')
    def recommend(body:AssessmentRequest,request:Request):
        session=authenticated(request,True)
        if research.mode not in ('sample','local-live'):raise AccountError('market_not_enabled',503)
        with assessment_gate.enter():
            data=assessments.read(body.analysis_token,session,research.now())
            store.throttle('assessment:'+session['owner'],2)
            store.throttle('assessment-token:'+hashlib.sha256(body.analysis_token.encode()).hexdigest(),1)
            position=None
            if body.include_position:
                position=next((h for h in store.read(session['owner'])['workspace']['holdings'] if h['id']==data['asset']['id']),None)
            result=assessments.recommend(data,position)
            authenticated(request)  # discard a response if the session was revoked during the provider call
            return result

    @app.get('/')
    def home():return FileResponse(ROOT/'static'/'account.html')

    app.mount('/assets',StaticFiles(directory=ROOT/'static'/'assets'),name='assets')
    return app


def create_staging_app():return create_app(AccountSettings.staging())


def create_local_research_app():
    from local_config import load_local_config
    from account_research import Research
    load_local_config()
    return create_app(AccountSettings.staging(),research=Research(sample=False))

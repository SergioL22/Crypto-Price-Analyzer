"""Password-protected, stock-only preview. Never mounts local/private APIs."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import base64
import hashlib
import os
import secrets
from threading import Lock, BoundedSemaphore
from contextlib import contextmanager
from time import monotonic

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Literal

from stock_service import StockService
from stock_provider import StockDataError
from stock_models import AssetCatalog, StockResearch
from profile_models import CompanyProfileResponse

ROOT=Path(__file__).resolve().parent/'static'
PAGES={'/':'index.html','/index.html':'index.html','/stocks.html':'stocks.html',
       '/watchlist.html':'watchlist.html','/portfolio.html':'portfolio.html',
       '/alerts.html':'alerts.html','/backups.html':'backups.html'}


def settings():
    origin=os.environ.get('HOSTED_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL','')
    parsed=urlsplit(origin)
    if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or '*' in parsed.netloc):
        raise ValueError('Set HOSTED_ORIGIN to the exact HTTPS origin (or use Render external URL).')
    password=os.environ.get('HOSTED_PREVIEW_PASSWORD','')
    if len(password)<32 or password.strip()!=password:
        raise ValueError('Set a private HOSTED_PREVIEW_PASSWORD of at least 32 characters.')
    return origin,password


class RequestBudget:
    """Global bounded request window; one process/worker per preview service."""
    def __init__(self,limit=120,clock=monotonic):
        self.limit=limit;self.clock=clock;self.started=clock();self.used=0;self.lock=Lock()

    def allow(self):
        with self.lock:
            now=self.clock()
            if now-self.started>=60:self.started=now;self.used=0
            if self.used>=self.limit:return False
            self.used+=1;return True


def create_app(*,stocks=None,now=None):
    origin,password=settings();authority=urlsplit(origin).netloc
    password_hash=hashlib.sha256(password.encode()).digest()
    stocks=stocks or StockService();now=now or (lambda:datetime.now(timezone.utc))
    requests=RequestBudget();gate=BoundedSemaphore(2)
    @contextmanager
    def admission():
        if not gate.acquire(blocking=False):raise StockDataError('stock_budget','Preview busy.',retry_after_seconds=5)
        try:yield
        finally:gate.release()
    app=FastAPI(title='Private Research Preview',docs_url=None,redoc_url=None,openapi_url=None)

    def error(status,code,message,headers=None):
        return JSONResponse(status_code=status,content={'error':{'code':code,'message':message}},headers=headers)

    @app.middleware('http')
    async def boundary(request:Request,call_next):
        # Health is deliberately data-free and works for platform probes.
        if request.url.path=='/health' and request.method in ('GET','HEAD'):
            return JSONResponse({'status':'ok'},headers={'Cache-Control':'no-store'})
        if request.url.scheme!='https' or request.headers.getlist('host')!=[authority]:
            return error(403,'origin_forbidden','Open the configured HTTPS preview address.')
        if (request.headers.getlist('origin') not in ([],[origin])
                or request.headers.get('sec-fetch-site') in ('cross-site','same-site') and request.url.path not in ('/','/index.html')):
            return error(403,'origin_forbidden','Cross-origin requests are not allowed.')
        if not requests.allow():return error(429,'preview_budget','Preview request limit reached. Retry later.',{'Retry-After':'60'})
        authenticated=False
        try:
            headers=request.headers.getlist('authorization')
            if len(headers)==1:
                scheme,encoded=headers[0].split(' ',1)
                user,provided=base64.b64decode(encoded,validate=True).decode('utf-8').split(':',1)
                authenticated=(scheme.lower()=='basic' and secrets.compare_digest(user,'preview')
                    and secrets.compare_digest(hashlib.sha256(provided.encode()).digest(),password_hash))
        except (ValueError,UnicodeError):pass
        if not authenticated:
            return error(401,'preview_sign_in','Private preview sign-in required.',
                         {'WWW-Authenticate':'Basic realm="Private Research Preview", charset="UTF-8"','Cache-Control':'no-store'})
        if request.method not in ('GET','HEAD'):return error(405,'read_only','This preview exposes research reads only.')
        try:response=await call_next(request)
        except Exception:response=error(500,'internal_error','An unexpected server error occurred.')
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',
            'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
            'Strict-Transport-Security':'max-age=31536000'})
        return response

    @app.exception_handler(StockDataError)
    async def stock_error(request,error):
        status=404 if error.code=='stock_not_found' else 429 if error.code in ('stock_budget','stock_quota','profile_rate_limited') else 503
        messages={'stock_setup_required':'Stock data is not configured on this preview.',
                  'profile_access':'Company profile access is unavailable.',
                  'profile_invalid':'Company profile identity or fields could not be verified.'}
        return JSONResponse(status_code=status,content={'error':{'code':error.code,'message':messages.get(error.code,'Market data is unavailable. Retry manually later.')}},
            headers={'Retry-After':str(error.retry_after_seconds)} if error.retry_after_seconds else None)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,error):return JSONResponse(status_code=422,content={'error':{'code':'invalid_request','message':'Check the selected listing and history window.'}})

    @app.get('/v1/assets',response_model=AssetCatalog)
    def assets(asset_class:Literal['stock','etf']='stock'):
        with admission():
            data=stocks.catalog(now());return dict(data,assets=[a for a in data['assets'] if a['asset_class']==asset_class])

    @app.get('/v1/stock-analysis',response_model=StockResearch)
    def research(asset_id:str=Query(min_length=1,max_length=250),days:int=Query(default=90,ge=1,le=3660),refresh:bool=False):
        with admission():return stocks.research(asset_id,days,now(),use_cache=True,refresh=refresh)

    @app.get('/v1/company-profile',response_model=CompanyProfileResponse)
    def company_profile(asset_id:str=Query(min_length=1,max_length=250)):
        with admission():return stocks.company_profile(asset_id,now())

    app.mount('/assets',StaticFiles(directory=ROOT/'assets'),name='assets')

    @app.get('/{page:path}')
    def page(page:str):
        name=PAGES.get('/'+page)
        if not name:return JSONResponse(status_code=404,content={'error':{'code':'not_found','message':'Not available in this preview.'}})
        content=(ROOT/name).read_text(encoding='utf-8').replace('<header>','<p class="hosted-preview-note">Private hosted preview · saved items stay in this browser · no account sync or AI calls.</p><header>',1)
        return HTMLResponse(content)

    return app

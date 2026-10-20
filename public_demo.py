"""Anonymous synthetic-only demonstration. No credentials or live transports."""
from datetime import datetime,timezone
from urllib.parse import urlsplit
import math
import os
from threading import BoundedSemaphore
from contextlib import contextmanager

from fastapi import FastAPI,Query,Request
from fastapi.responses import HTMLResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.gzip import GZipMiddleware
from typing import Literal

from assets import Asset
from stock_service import StockService,session_window
from stock_provider import StockDataError
from stock_models import AssetCatalog,StockResearch
from profile_models import CompanyProfileResponse
from hosted_preview import RequestBudget,PAGES,ROOT

NOTICE='SYNTHETIC DEMO — fictional companies and generated prices. Not live or historical market data. No AI predictions or trades.'
DEFINITIONS=(
 ('stock','SIMSUN','Fictional Sunworks','XNYS',70,.04,1.0),
 ('stock','SIMRIV','Fictional River Labs','XNGS',110,-.025,1.6),
 ('stock','SIMLUM','Fictional Lumen Systems','XNCM',35,.015,2.0),
 ('stock','SIMOAK','Fictional Oak Industries','XNYS',85,.025,.8),
 ('stock','SIMSKY','Fictional Skylark Research','XNGS',55,.06,1.3),
 ('etf','SIMFND','Fictional Broad Market Fund','ARCX',100,.03,.5),
 ('etf','SIMBAL','Fictional Balanced Fund','ARCX',80,.018,.3),
 ('etf','SIMTEC','Fictional Technology Fund','BATS',65,.045,1.1))


class SyntheticProfiles:
    def load(self,asset,now):
        return dict(asset_id=asset.id,source='Synthetic demo generator',status='not_supported',
                    message='These listings are fictional. No real company profile is requested or displayed.',
                    profile=None,fetched_at_utc=None,provider_updated_at_utc=None,cache_hit=False,
                    identity_scope=None,missing_fields=['name','finnhub_industry','headquarters_country','reporting_currency','website_url','ipo_date'])


class SyntheticProvider:
    def catalog(self):
        return [Asset(kind,'demo',symbol,name,mic,'USD','America/New_York') for kind,symbol,name,mic,*_ in DEFINITIONS]

    def history(self,asset,start,end):
        definition=next((r for r in DEFINITIONS if r[1]==asset.symbol and asset.provider=='demo'),None)
        if definition is None:raise StockDataError('stock_not_found','Unknown fictional listing.')
        _,symbol,_,_,base,trend,amplitude=definition
        phase=next(i for i,row in enumerate(DEFINITIONS) if row[1]==symbol)
        end_time=datetime.fromisoformat(end).replace(hour=23,tzinfo=timezone.utc)
        days=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).days+1
        dates=session_window(days,end_time)[2];rows=[]
        for date in dates:
            index=(datetime.fromisoformat(date)-datetime(2010,1,1)).days
            close=base*math.exp(trend*index/365.25+amplitude*.06*math.sin(index/37+phase))
            opening=close*(1+.006*math.sin(index/7+phase))
            rows.append(dict(date=date,open=opening,high=max(opening,close)*1.012,
                             low=min(opening,close)*.988,close=close,
                             volume=float(90000+phase*18000+(index%19)*2100)))
        return rows


def origin_settings():
    origin=os.environ.get('PUBLIC_DEMO_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL','')
    parsed=urlsplit(origin)
    local=parsed.hostname in ('127.0.0.1','localhost') and parsed.port is not None and parsed.scheme=='http'
    if (not parsed.hostname or not (parsed.scheme=='https' or local) or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or '*' in parsed.netloc):
        raise ValueError('Set the exact PUBLIC_DEMO_ORIGIN or Render external URL. HTTPS is required outside loopback.')
    return origin


def create_app():
    origin=origin_settings();authority=urlsplit(origin).netloc
    # This factory has no provider injection, live flag, key lookup or live fallback.
    stocks=StockService(provider=SyntheticProvider(),profiles=SyntheticProfiles(),history_request_limit=12)
    budget=RequestBudget(limit=120);gate=BoundedSemaphore(2)
    app=FastAPI(title='Synthetic Research Demo',docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(GZipMiddleware,minimum_size=1024,compresslevel=5)

    @contextmanager
    def admission():
        if not gate.acquire(blocking=False):raise StockDataError('stock_budget','Demo busy.',retry_after_seconds=5)
        try:yield
        finally:gate.release()

    @app.middleware('http')
    async def boundary(request:Request,call_next):
        if request.url.path=='/health' and request.method in ('GET','HEAD'):
            return JSONResponse({'status':'ok','mode':'synthetic-demo'},headers={'Cache-Control':'no-store'})
        if (request.url.scheme!=urlsplit(origin).scheme or request.headers.getlist('host')!=[authority]
                or request.headers.getlist('origin') not in ([],[origin])):
            return JSONResponse(status_code=403,content={'error':{'code':'origin_forbidden','message':'Open the configured demo address.'}})
        if request.method not in ('GET','HEAD'):
            return JSONResponse(status_code=405,content={'error':{'code':'read_only','message':'This synthetic demo exposes research reads only.'}})
        if not budget.allow():
            return JSONResponse(status_code=429,content={'error':{'code':'demo_budget','message':'Demo is busy. Retry manually later.'}},headers={'Retry-After':'60'})
        try:response=await call_next(request)
        except Exception:response=JSONResponse(status_code=500,content={'error':{'code':'internal_error','message':'The demo could not complete this request.'}})
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
            'Referrer-Policy':'no-referrer','X-Research-Data':'synthetic',
            'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
        if os.environ.get('PUBLIC_MARKET_WIDGETS')=='1' and request.url.path in ('/','/index.html','/market-watchlist.html'):
            response.headers['X-Research-Data']='embedded-market'
            response.headers['Content-Security-Policy']="default-src 'none'; script-src 'self' https://s3.tradingview.com; style-src 'self'; frame-src https://www.tradingview.com https://s.tradingview.com https://tradingview-widget.com https://*.tradingview-widget.com; img-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        if origin.startswith('https:'):response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.exception_handler(StockDataError)
    async def stock_error(request,error):
        return JSONResponse(status_code=404 if error.code=='stock_not_found' else 429 if error.code=='stock_budget' else 503,
            content={'error':{'code':error.code,'message':'Synthetic demo data is unavailable for this request. No live fallback was attempted.'}},
            headers={'Retry-After':str(error.retry_after_seconds)} if error.retry_after_seconds else None)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,error):
        return JSONResponse(status_code=422,content={'error':{'code':'invalid_request','message':'Choose a fictional listing and a history window of 1–3660 days.'}})

    @app.get('/v1/assets',response_model=AssetCatalog)
    def catalog(asset_class:Literal['stock','etf']='stock'):
        with admission():
            data=stocks.catalog(datetime.now(timezone.utc))
            return dict(data,assets=[a for a in data['assets'] if a['asset_class']==asset_class],coverage=NOTICE)

    @app.get('/v1/stock-analysis',response_model=StockResearch)
    def research(asset_id:str=Query(min_length=1,max_length=250),days:int=Query(default=90,ge=1,le=3660),refresh:bool=False):
        with admission():
            data=stocks.research(asset_id,days,datetime.now(timezone.utc),use_cache=True,refresh=refresh)
            data['adjustment']='synthetic'
            data['limitations']=[NOTICE,'Dates follow completed US exchange sessions, but all prices and volumes are generated formulas. No investment performance or predictive accuracy is established.']
            return data

    @app.get('/v1/company-profile',response_model=CompanyProfileResponse)
    def company_profile(asset_id:str=Query(min_length=1,max_length=250)):
        with admission():return stocks.company_profile(asset_id,datetime.now(timezone.utc))

    app.mount('/assets',StaticFiles(directory=ROOT/'assets'),name='assets')

    @app.get('/{page:path}')
    def page(page:str):
        if os.environ.get('PUBLIC_MARKET_WIDGETS')=='1' and page in ('','index.html','market-watchlist.html'):
            content=(ROOT/'public-market.html').read_text(encoding='utf-8')
            return HTMLResponse(content)
        name=PAGES.get('/'+page)
        if not name:return JSONResponse(status_code=404,content={'error':{'code':'not_found','message':'Not part of the synthetic demo.'}})
        content=(ROOT/name).read_text(encoding='utf-8')
        if os.environ.get('PUBLIC_MARKET_WIDGETS')=='1':
            content=content.replace('<header>','<p class="hosted-preview-note"><a href="/">Back to real market charts &amp; watchlist</a> · Synthetic practice area</p><header>',1)
        content=content.replace('<body ', '<body data-demo="true" ',1)
        content=content.replace('<header>',f'<aside class="synthetic-demo-banner" role="note"><strong>{NOTICE}</strong><p>Try the interface with fictional data. Saved demo items stay in this browser and are separate from your private workspace.</p></aside><header>',1)
        content=content.replace('uses provider quota','uses demo request budget').replace('Research only · no trade execution · historical closing prices · split-adjusted · excludes dividends.','Synthetic demonstration only · generated prices · no trades or predictions.')
        content=content.replace('Research Desk</title>','Synthetic Demo</title>')
        # Remove live-research disclosures rather than implying that model tests apply to this example.
        import re
        content=re.sub(r'<details class="research-disclosure">.*?</details>','',content,flags=re.S)
        content=content.replace('Ten years are requested by default. Returned history depends on the listing and provider access; missing years are never filled.','Ten years of generated demo prices are available. They do not represent actual market history.')
        return HTMLResponse(content)
    return app

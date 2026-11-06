"""Anonymous synthetic-only demonstration. No credentials or live transports."""
from datetime import datetime,timezone
from urllib.parse import urlsplit
import json
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
import sec_edgar
import sec_live
from sec_edgar import SNAPSHOT as SEC_SNAPSHOT

SEC_NOTICE=('Company fundamentals, filings and ETF holdings come from public SEC EDGAR filings. '
            'Values are as reported to the SEC and are refreshed periodically, not live. No stock prices are used. Research only, not advice.')


class SecUnavailable(Exception):
    def __init__(self,status,code,message):
        super().__init__(message);self.status=status;self.code=code;self.message=message


_sec_cache={}
def sec_snapshot(path=None):
    """The SEC research snapshot, read once per process. The web app never calls EDGAR itself."""
    path=path or SEC_SNAPSHOT
    if path not in _sec_cache:
        try:_sec_cache[path]=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):raise SecUnavailable(503,'sec_snapshot_missing','SEC research data has not been generated for this deployment.')
    return _sec_cache[path]

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


def create_app(sec_fetch=None,sec_lookup=None,sec_insiders=None):
    origin=origin_settings();authority=urlsplit(origin).netloc
    # Live SEC access needs an identifying User-Agent; without one, only the snapshot is served.
    if os.environ.get('SEC_USER_AGENT') and None in (sec_fetch,sec_lookup,sec_insiders):
        http=sec_live.SecHttp(os.environ['SEC_USER_AGENT'])
        sec_fetch=sec_fetch or http.submissions;sec_lookup=sec_lookup or sec_live.CompanyLookup(http.json)
        sec_insiders=sec_insiders or sec_live.InsiderActivity(http.json,http.text)
    live_filings=sec_live.LiveFilings(sec_fetch) if sec_fetch else None
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
        if os.environ.get('PUBLIC_MARKET_WIDGETS')=='1' and request.url.path in ('/market-charts.html','/market-watchlist.html'):
            response.headers['X-Research-Data']='embedded-market'
            response.headers['Content-Security-Policy']="default-src 'none'; script-src 'self' https://s3.tradingview.com; style-src 'self'; frame-src https://www.tradingview.com https://s.tradingview.com https://tradingview-widget.com https://*.tradingview-widget.com; img-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        if os.environ.get('PUBLIC_SEC_RESEARCH')=='1' and (request.url.path=='/filings-research.html' or request.url.path.startswith('/v1/sec/')):
            response.headers['X-Research-Data']='sec-public'
            if request.url.path.startswith('/v1/sec/') and response.status_code==200:
                fresh=request.url.path in ('/v1/sec/company','/v1/sec/filings','/v1/sec/lookup')
                response.headers['Cache-Control']='public, max-age=300' if fresh else 'public, max-age=3600'
        if os.environ.get('PUBLIC_SEC_RESEARCH')=='1' and request.url.path=='/':
            response.headers['X-Research-Data']='sec-public'
        if os.environ.get('PUBLIC_SEC_RESEARCH')=='1' and request.url.path=='/price-lab.html':
            response.headers['X-Research-Data']='visitor-supplied'
        if origin.startswith('https:'):response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.exception_handler(StockDataError)
    async def stock_error(request,error):
        return JSONResponse(status_code=404 if error.code=='stock_not_found' else 429 if error.code=='stock_budget' else 503,
            content={'error':{'code':error.code,'message':'Synthetic demo data is unavailable for this request. No live fallback was attempted.'}},
            headers={'Retry-After':str(error.retry_after_seconds)} if error.retry_after_seconds else None)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,error):
        if request.url.path.startswith('/v1/sec/'):
            return JSONResponse(status_code=422,content={'error':{'code':'invalid_request','message':'Use an uppercase ticker from the covered list, such as AAPL or SPY.'}})
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

    def sec_data():
        if os.environ.get('PUBLIC_SEC_RESEARCH')!='1':raise SecUnavailable(404,'not_found','Not part of the synthetic demo.')
        return sec_snapshot()

    def sec_symbol(records,symbol,kind):
        record=records.get(symbol)
        if record is None:raise SecUnavailable(404,'symbol_not_covered',f'{symbol} is not in the {kind} list.')
        return record

    @app.exception_handler(SecUnavailable)
    async def sec_error(request,error):
        return JSONResponse(status_code=error.status,content={'error':{'code':error.code,'message':error.message}})

    @app.get('/v1/sec/coverage')
    def sec_coverage():
        data=sec_data()
        return dict(generated_at_utc=data['generated_at_utc'],source=data['source'],notice=SEC_NOTICE,
                    companies=[dict(symbol=c['symbol'],name=c['name']) for c in data['companies'].values()],
                    funds=[dict(symbol=f['symbol'],name=f['name'],period_end=f['period_end']) for f in data['funds'].values()])

    def company_filings(data,company):
        live=live_filings.filings(company['cik']) if live_filings else None
        if live is None:
            return dict(filings=company['filings'],filings_source='snapshot',filings_fetched_at_utc=data['generated_at_utc'])
        rows,fetched=live
        return dict(filings=sec_live.merge_filings(rows,company['filings']),filings_source='live',
                    filings_fetched_at_utc=datetime.fromtimestamp(fetched,timezone.utc).replace(microsecond=0).isoformat())

    @app.get('/v1/sec/company')
    def sec_company(symbol:str=Query(pattern=r'^[A-Z]{1,5}$')):
        data=sec_data();company=sec_symbol(data['companies'],symbol,'company')
        return dict(company,**company_filings(data,company),generated_at_utc=data['generated_at_utc'])

    @app.get('/v1/sec/lookup')
    def sec_lookup_company(symbol:str=Query(min_length=1,max_length=8,pattern=r'^[A-Za-z]{1,5}([.-][A-Za-z]{1,2})?$')):
        data=sec_data();key=symbol.upper().replace('.','-')
        if key in data['companies']:return sec_company(key)
        if sec_lookup is None:raise SecUnavailable(503,'lookup_unavailable','Looking up other companies needs live SEC access, which is not configured here.')
        try:record=sec_lookup.company(key)
        except sec_live.LookupError_ as error:raise SecUnavailable(error.status,error.code,error.message)
        fetched=datetime.fromtimestamp(record['fetched_at_epoch'],timezone.utc).replace(microsecond=0).isoformat()
        return dict({k:v for k,v in record.items() if k!='fetched_at_epoch'},filings_source='live',filings_fetched_at_utc=fetched,generated_at_utc=fetched)

    @app.get('/v1/sec/insiders')
    def sec_insider_activity(symbol:str=Query(min_length=1,max_length=8,pattern=r'^[A-Za-z]{1,5}([.-][A-Za-z]{1,2})?$')):
        data=sec_data();key=symbol.upper().replace('.','-')
        if sec_insiders is None:raise SecUnavailable(503,'insiders_unavailable','Insider activity needs live SEC access, which is not configured here.')
        company=data['companies'].get(key)
        try:
            if company is None:
                if sec_lookup is None:raise SecUnavailable(404,'symbol_not_covered',f'{key} is not in the company list.')
                company=sec_lookup.company(key)
            summary=sec_insiders.activity(company['cik'])
        except sec_live.LookupError_ as error:raise SecUnavailable(error.status,error.code,error.message)
        fetched=datetime.fromtimestamp(summary['fetched_at_epoch'],timezone.utc).replace(microsecond=0).isoformat()
        return dict({k:v for k,v in summary.items() if k!='fetched_at_epoch'},symbol=key,name=company['name'],fetched_at_utc=fetched)

    @app.get('/v1/sec/filings')
    def sec_filings(symbols:str=Query(pattern=r'^[A-Z]{1,5}(,[A-Z]{1,5}){0,19}$')):
        data=sec_data();out=[]
        for symbol in dict.fromkeys(symbols.split(',')):
            company=data['companies'].get(symbol)
            if company:out.append(dict(symbol=symbol,name=company['name'],**company_filings(data,company)))
        return dict(companies=out,uncovered=[s for s in symbols.split(',') if s not in data['companies']])

    @app.get('/v1/sec/fund')
    def sec_fund(symbol:str=Query(pattern=r'^[A-Z]{1,5}$')):
        data=sec_data();fund=sec_symbol(data['funds'],symbol,'ETF')
        return dict({k:v for k,v in fund.items() if k!='holdings'},summary=sec_edgar.fund_summary(fund),generated_at_utc=data['generated_at_utc'])

    @app.get('/v1/sec/overlap')
    def sec_overlap(a:str=Query(pattern=r'^[A-Z]{1,5}$'),b:str=Query(pattern=r'^[A-Z]{1,5}$')):
        data=sec_data();left,right=sec_symbol(data['funds'],a,'ETF'),sec_symbol(data['funds'],b,'ETF')
        if a==b:raise SecUnavailable(422,'same_fund','Choose two different ETFs.')
        return dict(sec_edgar.overlap(left,right),a=dict(symbol=a,period_end=left['period_end']),b=dict(symbol=b,period_end=right['period_end']))

    app.mount('/assets',StaticFiles(directory=ROOT/'assets'),name='assets')

    @app.get('/{page:path}')
    def page(page:str):
        if os.environ.get('PUBLIC_SEC_RESEARCH')=='1' and page=='':
            return HTMLResponse((ROOT/'home.html').read_text(encoding='utf-8'))
        if os.environ.get('PUBLIC_SEC_RESEARCH')=='1' and page in ('filings-research.html','price-lab.html'):
            return HTMLResponse((ROOT/page).read_text(encoding='utf-8'))
        if os.environ.get('PUBLIC_MARKET_WIDGETS')=='1' and page in ('market-charts.html','market-watchlist.html'):
            content=(ROOT/'public-market.html').read_text(encoding='utf-8')
            if os.environ.get('PUBLIC_SEC_RESEARCH')=='1':
                content=content.replace('<a href="/">Original chart · practice</a><a href="/market-charts.html">TradingView chart</a><a href="/market-watchlist.html">Market watchlist</a>',
                    '<a href="/">Home</a><a href="/filings-research.html">Filings research</a><a href="/price-lab.html">Your price data</a><a href="/market-charts.html">TradingView chart</a><a href="/market-watchlist.html">Market watchlist</a><a href="/index.html">Practice mode</a>',1)
            return HTMLResponse(content)
        name=PAGES.get('/'+page)
        if not name:return JSONResponse(status_code=404,content={'error':{'code':'not_found','message':'Not part of the synthetic demo.'}})
        content=(ROOT/name).read_text(encoding='utf-8')
        if os.environ.get('PUBLIC_MARKET_WIDGETS')=='1':
            content=content.replace('<header>','<div class="chart-choice"><a class="chart-choice-link" href="/market-charts.html">Open TradingView chart · real market data</a><p>Original chart below: synthetic practice data. TradingView opens separately with real market charts.</p></div><header>',1)
        content=content.replace('<body ', '<body data-demo="true" ',1)
        if os.environ.get('PUBLIC_SEC_RESEARCH')=='1':
            # "/" is the Research Desk home page, so the practice workspace lives at /index.html.
            content=content.replace('<body ','<body data-practice-home="/index.html" ',1).replace('href="/"','href="/index.html"').replace('href="/?view=','href="/index.html?view=')
            content=content.replace('<header>','<p class="practice-home-link"><a href="/">← Research Desk home</a></p><header>',1)
        content=content.replace('<header>',f'<aside class="synthetic-demo-banner" role="note"><strong>{NOTICE}</strong><p>Try the interface with fictional data. Saved demo items stay in this browser and are separate from your private workspace.</p></aside><header>',1)
        content=content.replace('uses provider quota','uses demo request budget').replace('Research only · no trade execution · historical closing prices · split-adjusted · excludes dividends.','Synthetic demonstration only · generated prices · no trades or predictions.')
        content=content.replace('Research Desk</title>','Synthetic Demo</title>')
        # Remove live-research disclosures rather than implying that model tests apply to this example.
        import re
        content=re.sub(r'<details class="research-disclosure">.*?</details>','',content,flags=re.S)
        content=content.replace('Ten years are requested by default. Returned history depends on the listing and provider access; missing years are never filled.','Ten years of generated demo prices are available. They do not represent actual market history.')
        return HTMLResponse(content)
    return app

"""Optional free company metadata. Never used for quotes, forecasts or ETF holdings."""
from collections import OrderedDict,deque
from copy import deepcopy
from datetime import date
from math import ceil,isfinite
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit
import os
import requests
from stock_provider import StockDataError

SOURCE='Finnhub Company Profile 2'
FIELDS=('name','finnhub_industry','headquarters_country','reporting_currency','website_url','ipo_date')


def normalize_profile(payload,asset,now):
    if not isinstance(payload,dict):raise ValueError('Invalid profile')
    ticker=payload.get('ticker');exchange=payload.get('exchange')
    if ticker!=asset.symbol or not isinstance(exchange,str):raise ValueError('Unverified identity')
    venue=exchange.strip().upper()
    if asset.exchange in ('XNAS','XNGS','XNMS','XNCM'):
        matched=venue in {'NASDAQ','NASDAQ/NMS (GLOBAL MARKET)','NASDAQ/NGS (GLOBAL SELECT MARKET)','NASDAQ/SCM (CAPITAL MARKET)','NASDAQ NMS - GLOBAL MARKET','NASDAQ GLOBAL SELECT','NASDAQ GLOBAL MARKET','NASDAQ CAPITAL MARKET'}
    else:
        matched=venue in {'XNYS':{'NYSE','NEW YORK STOCK EXCHANGE, INC.','NEW YORK STOCK EXCHANGE'},'ARCX':{'NYSE ARCA','NYSE ARCA, INC.'},'XASE':{'NYSE AMERICAN','NYSE AMERICAN LLC','NYSE MKT','NYSE MKT LLC'},'BATS':{'BATS','BATS BZX','CBOE BZX','CBOE BZX EXCHANGE'}}.get(asset.exchange,set())
    if not matched:raise ValueError('Unverified exchange')
    def text(key,limit=300):
        value=payload.get(key)
        if value is None or value=='':return None
        if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 for c in value):raise ValueError('Invalid text')
        return value.strip() or None
    profile=dict(name=text('name'),finnhub_industry=text('finnhubIndustry'),headquarters_country=text('country',100),reporting_currency=text('currency',3),website_url=text('weburl',2048),ipo_date=text('ipo',10))
    currency=profile['reporting_currency']
    if currency and (len(currency)!=3 or not currency.isascii() or not currency.isupper() or not currency.isalpha()):raise ValueError('Invalid reporting currency')
    if profile['ipo_date']:
        parsed=date.fromisoformat(profile['ipo_date'])
        if parsed.isoformat()!=profile['ipo_date'] or parsed>now.date():raise ValueError('Invalid IPO date')
    website=profile['website_url']
    if website:
        parsed=urlsplit(website)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in website):raise ValueError('Invalid website')
    return profile


class CompanyProfiles:
    def __init__(self,*,key=None,get=None,clock=monotonic,ttl=86400,capacity=128,request_limit=4):
        if not isfinite(ttl) or ttl<=0 or type(capacity) is not int or capacity<1 or type(request_limit) is not int or request_limit<1:raise ValueError('Positive bounded profile configuration required')
        self.key=key;self.get=get or requests.get;self.clock=clock;self.ttl=ttl;self.capacity=capacity;self.request_limit=request_limit
        self._items=OrderedDict();self._attempts=deque();self._retry=0;self._lock=Lock()

    @staticmethod
    def unavailable(asset,status,message):
        return dict(asset_id=asset.id,source=SOURCE,status=status,message=message,profile=None,fetched_at_utc=None,provider_updated_at_utc=None,cache_hit=False,identity_scope=None,missing_fields=list(FIELDS))

    def load(self,asset,now):
        if asset.asset_class!='stock':return self.unavailable(asset,'not_supported','ETF objectives, holdings and fees are not available through this free company-profile integration.')
        key=self.key if self.key is not None else os.environ.get('FINNHUB_API_KEY','')
        if not isinstance(key,str) or not key.strip():return self.unavailable(asset,'setup_required','Add FINNHUB_API_KEY to the server local .env and restart. Never paste the key into chat.')
        with self._lock:
            current=self.clock();entry=self._items.get(asset.id)
            if entry and current-entry[0]<self.ttl:
                self._items.move_to_end(asset.id);result=deepcopy(entry[1]);result['cache_hit']=True;return result
            if current<self._retry:raise StockDataError('profile_rate_limited','Company profiles are paused after a provider error. Retry manually later.',retry_after_seconds=max(1,ceil(self._retry-current)))
            while self._attempts and current-self._attempts[0]>=60:self._attempts.popleft()
            if len(self._attempts)>=self.request_limit:raise StockDataError('profile_rate_limited','Company profile request budget reached.',retry_after_seconds=max(1,ceil(60-current+self._attempts[0])))
            self._attempts.append(current)
            try:
                response=self.get('https://finnhub.io/api/v1/stock/profile2',params={'symbol':asset.symbol},headers={'X-Finnhub-Token':key.strip()},timeout=(5,15),allow_redirects=False)
                if response.status_code==429:raise StockDataError('profile_rate_limited','Company profile provider quota reached. Retry manually later.',retry_after_seconds=60)
                if response.status_code in (401,403):raise StockDataError('profile_access','Company profile access was rejected. Check the Finnhub key and free endpoint access.')
                if not 200<=response.status_code<300:raise StockDataError('profile_unavailable','Company profile provider is temporarily unavailable.')
                payload=response.json()
                if not isinstance(payload,dict) or payload.get('error'):raise StockDataError('profile_unavailable','Company profile provider did not return usable data.')
                if not payload:result=self.unavailable(asset,'not_found','No free company profile was returned for this listing.')
                else:
                    try:profile=normalize_profile(payload,asset,now)
                    except (ValueError,TypeError,OverflowError):raise StockDataError('profile_invalid','Profile identity or fields could not be verified; no company data was displayed.') from None
                    result=dict(asset_id=asset.id,source=SOURCE,status='available',message='Company metadata only. The provider does not supply a profile update timestamp. Business descriptions and ETF data are not included.',profile=profile,fetched_at_utc=now.isoformat(),provider_updated_at_utc=None,cache_hit=False,identity_scope='symbol_operating_exchange',missing_fields=[field for field in FIELDS if profile[field] is None])
            except StockDataError:
                self._retry=self.clock()+60;raise
            except (requests.RequestException,ValueError,TypeError):
                self._retry=self.clock()+60
                raise StockDataError('profile_unavailable','Company profile provider could not be reached or returned invalid data.') from None
            self._items[asset.id]=(self.clock(),deepcopy(result));self._items.move_to_end(asset.id)
            while len(self._items)>self.capacity:self._items.popitem(last=False)
            return deepcopy(result)

"""Fresh SEC data for the public demo, fetched and cached on the server.

Only the server talks to EDGAR, so visitor traffic never reaches the SEC.
Filing lists refresh at most every 30 minutes per company; on-demand company
lookups are cached for 12 hours and limited per time window. When live access
is not configured or fails, callers fall back to the committed snapshot.
"""
from __future__ import annotations

from collections import OrderedDict
from threading import Lock
import re
import time

import requests

import sec_edgar

TTL_SECONDS=1800
FAILURE_BACKOFF_SECONDS=300
MIN_INTERVAL=0.15  # stay well under the SEC's 10 requests/second


class SecHttp:
    """Spaced JSON GETs with the identifying User-Agent the SEC asks for."""
    def __init__(self,user_agent,session=None,clock=time.monotonic,sleep=time.sleep):
        self.session=session or requests.Session();self.session.headers.update({'User-Agent':user_agent,'Accept-Encoding':'gzip, deflate'})
        self.clock=clock;self.sleep=sleep;self.last=-1e18;self.lock=Lock()

    def get(self,url):
        with self.lock:
            wait=MIN_INTERVAL-(self.clock()-self.last)
            if wait>0:self.sleep(wait)
            try:response=self.session.get(url,timeout=10)
            finally:self.last=self.clock()
        response.raise_for_status();return response

    def json(self,url):return self.get(url).json()
    def text(self,url):return self.get(url).text

    def submissions(self,cik):return self.json(f'https://data.sec.gov/submissions/CIK{cik:010d}.json')


def requests_fetch(user_agent):
    return SecHttp(user_agent).submissions


class LiveFilings:
    def __init__(self,fetch,ttl=TTL_SECONDS,backoff=FAILURE_BACKOFF_SECONDS,clock=time.monotonic,wall=time.time):
        self.fetch=fetch;self.ttl=ttl;self.backoff=backoff;self.clock=clock;self.wall=wall
        self.cache={};self.failed_at={};self.lock=Lock()

    def filings(self,cik):
        """(rows, fetched_at_epoch) or None when no live data is available for this company."""
        now=self.clock()
        with self.lock:
            cached=self.cache.get(cik)
            if cached and now-cached[0]<self.ttl:return cached[1],cached[2]
            if now-self.failed_at.get(cik,-1e18)<self.backoff:return (cached[1],cached[2]) if cached else None
            try:rows=sec_edgar.recent_filings(self.fetch(cik))
            except Exception:
                self.failed_at[cik]=now
                return (cached[1],cached[2]) if cached else None
            self.cache[cik]=(now,rows,self.wall())
            return rows,self.cache[cik][2]


def merge_filings(live,snapshot,limit=20):
    """Live rows first, then snapshot rows not already present (e.g. a predecessor registrant's)."""
    seen={row['accession'] for row in live}
    rows=live+[row for row in snapshot if row['accession'] not in seen]
    return sorted(rows,key=lambda row:row['filed'],reverse=True)[:limit]


class LookupError_(Exception):
    def __init__(self,status,code,message):
        super().__init__(message);self.status=status;self.code=code;self.message=message


class CompanyLookup:
    """Fundamentals and filings for any SEC-registered ticker, built on first request."""
    TICKERS_URL='https://www.sec.gov/files/company_tickers.json'

    def __init__(self,get_json,ttl=43200,max_entries=60,window=600,window_limit=30,clock=time.monotonic,wall=time.time):
        self.get_json=get_json;self.ttl=ttl;self.max_entries=max_entries;self.window=window;self.window_limit=window_limit
        self.clock=clock;self.wall=wall;self.cache=OrderedDict();self.tickers=None;self.tickers_at=-1e18
        self.window_started=-1e18;self.window_used=0;self.lock=Lock()

    def _ticker_map(self,now):
        if self.tickers is None or now-self.tickers_at>86400:
            rows=self.get_json(self.TICKERS_URL).values()
            self.tickers={str(r['ticker']).upper():(int(r['cik_str']),r.get('title')) for r in rows};self.tickers_at=now
        return self.tickers

    def company(self,symbol):
        symbol=symbol.upper().replace('.','-')
        if not re.fullmatch(r'[A-Z]{1,5}(-[A-Z]{1,2})?',symbol):raise LookupError_(422,'invalid_symbol','Use a US ticker such as TSLA or BRK-B.')
        now=self.clock()
        with self.lock:
            hit=self.cache.get(symbol)
            if hit and now-hit[0]<self.ttl:self.cache.move_to_end(symbol);return hit[1]
            if now-self.window_started>=self.window:self.window_started=now;self.window_used=0
            if self.window_used>=self.window_limit:raise LookupError_(429,'lookup_budget','Too many new lookups right now. Try again in a few minutes, or pick a starter company.')
            self.window_used+=1
            try:
                found=self._ticker_map(now).get(symbol)
                if not found:raise LookupError_(404,'symbol_not_found',f'{symbol} is not in the SEC ticker list. Funds and foreign listings may not file these reports.')
                cik,title=found
                facts=self.get_json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json')
                submissions=self.get_json(f'https://data.sec.gov/submissions/CIK{cik:010d}.json')
            except LookupError_:raise
            except requests.HTTPError as error:
                if error.response is not None and error.response.status_code==404:
                    raise LookupError_(404,'no_financial_data',f'{symbol} has no XBRL financial data at the SEC.')
                raise LookupError_(503,'sec_unavailable','The SEC could not be reached. Try again later.')
            except Exception:raise LookupError_(503,'sec_unavailable','The SEC could not be reached. Try again later.')
            fundamentals=sec_edgar.annual_fundamentals(facts)
            record=dict(symbol=symbol,name=title or submissions.get('name'),registrant=submissions.get('name') or fundamentals['entity_name'],cik=cik,
                        sic_description=submissions.get('sicDescription'),fiscal_year_end=submissions.get('fiscalYearEnd'),
                        metrics=fundamentals['metrics'],filings=sec_edgar.recent_filings(submissions),note=None,on_demand=True,
                        fetched_at_epoch=self.wall(),source_url=f'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik:010d}')
            self.cache[symbol]=(now,record);self.cache.move_to_end(symbol)
            while len(self.cache)>self.max_entries:self.cache.popitem(last=False)
            return record


class InsiderActivity:
    """Twelve months of Form 4 insider transactions, parsed on first request and cached."""
    def __init__(self,get_json,get_text,max_forms=40,ttl=43200,max_entries=60,clock=time.monotonic,wall=time.time,today=None):
        self.get_json=get_json;self.get_text=get_text;self.max_forms=max_forms;self.ttl=ttl;self.max_entries=max_entries
        self.clock=clock;self.wall=wall;self.today=today or (lambda:time.strftime('%Y-%m-%d',time.gmtime()));self.cache=OrderedDict();self.lock=Lock()

    def activity(self,cik):
        now=self.clock()
        with self.lock:
            hit=self.cache.get(cik)
            if hit and now-hit[0]<self.ttl:return hit[1]
            today=self.today();since=f'{int(today[:4])-1}{today[4:]}'
            try:
                recent=self.get_json(f'https://data.sec.gov/submissions/CIK{cik:010d}.json').get('filings',{}).get('recent',{})
                forms=[]
                for form,accession,filed,document in zip(recent.get('form',[]),recent.get('accessionNumber',[]),recent.get('filingDate',[]),recent.get('primaryDocument',[])):
                    if form!='4' or filed<since:continue
                    folder=f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace("-","")}/'
                    try:parsed=sec_edgar.parse_form4(self.get_text(folder+document.rsplit('/',1)[-1]))
                    except Exception:continue  # skip a malformed filing rather than failing the summary
                    forms.append(dict(parsed,filed=filed,url=folder+document))
                    if len(forms)>=self.max_forms:break
            except Exception:raise LookupError_(503,'sec_unavailable','The SEC could not be reached. Try again later.')
            summary=dict(sec_edgar.insider_summary(forms,since),truncated=len(forms)>=self.max_forms,fetched_at_epoch=self.wall())
            self.cache[cik]=(now,summary)
            while len(self.cache)>self.max_entries:self.cache.popitem(last=False)
            return summary

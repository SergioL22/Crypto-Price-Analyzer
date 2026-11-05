"""Build the public SEC research snapshot served by the public demo.

Usage (identify yourself as SEC fair-access rules ask: app name plus a contact):
    set SEC_USER_AGENT=ResearchDesk/1.0 (your-contact@example.com)
    python sec_refresh.py

Writes sec_data/research_snapshot.json. The web app only reads that file, so the
hosted demo makes no SEC requests and visitors' traffic never reaches EDGAR.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import sys
import time

import requests

import sec_edgar

SNAPSHOT=sec_edgar.SNAPSHOT
# Display names match the public market page's starter listings; SEC names are often upper case.
STOCKS={'AAPL':'Apple','MSFT':'Microsoft','AMZN':'Amazon','GOOGL':'Alphabet','NVDA':'NVIDIA','IBM':'IBM',
        'JNJ':'Johnson & Johnson','JPM':'JPMorgan Chase','XOM':'Exxon Mobil'}
# Single-series trusts are found by CIK; multi-series trusts need the fund's series ID.
ETFS=(('SPY','SPDR S&P 500 ETF Trust',884394,None),('QQQ','Invesco QQQ Trust',1067839,None),
      ('IWM','iShares Russell 2000 ETF',1100663,'S000004344'),('DIA','SPDR Dow Jones Industrial Average ETF Trust',1041130,None),
      ('VTI','Vanguard Total Stock Market ETF',36405,'S000002848'))
# Listings whose current registrant succeeded an older one (holding-company reorganizations).
PREDECESSORS={'XOM':(34088,'Exxon Mobil Corporation')}
MIN_INTERVAL=0.15  # well under the SEC's 10 requests/second ceiling


class Sec:
    def __init__(self,user_agent,session=None):
        self.session=session or requests.Session();self.session.headers.update({'User-Agent':user_agent,'Accept-Encoding':'gzip, deflate'})
        self.last=0.0

    def get(self,url):
        wait=MIN_INTERVAL-(time.monotonic()-self.last)
        if wait>0:time.sleep(wait)
        response=self.session.get(url,timeout=60);self.last=time.monotonic()
        response.raise_for_status();return response

    def json(self,url):return self.get(url).json()


def series_nport(sec,series_id):
    feed=sec.get(f'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={series_id}&type=NPORT-P&dateb=&owner=include&count=5&output=atom').text
    match=re.search(r'<accession-number>([\d-]+)</accession-number>',feed)  # newest first
    filed=re.search(r'<filing-date>([\d-]+)</filing-date>',feed)
    if not match:raise RuntimeError(f'No NPORT-P filing found for series {series_id}.')
    return dict(accession=match.group(1),filed=filed.group(1) if filed else None)


def build(sec):
    tickers={row['ticker']:row['cik_str'] for row in sec.json('https://www.sec.gov/files/company_tickers.json').values()}
    companies={}
    for symbol in STOCKS:
        cik=tickers[symbol];padded=f'{cik:010d}'
        facts=sec.json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json')
        submissions=sec.json(f'https://data.sec.gov/submissions/CIK{padded}.json')
        fundamentals=sec_edgar.annual_fundamentals(facts);filings=sec_edgar.recent_filings(submissions);note=None
        if symbol in PREDECESSORS:
            old,old_name=PREDECESSORS[symbol];old_padded=f'{old:010d}'
            earlier=sec_edgar.annual_fundamentals(sec.json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{old_padded}.json'))
            fundamentals['metrics']=sec_edgar.merge_metrics(fundamentals['metrics'],earlier['metrics'])
            filings=sorted(filings+sec_edgar.recent_filings(sec.json(f'https://data.sec.gov/submissions/CIK{old_padded}.json')),key=lambda f:f['filed'],reverse=True)[:20]
            note=f'Includes annual reports and filings of predecessor registrant {old_name} (CIK {old}).'
        companies[symbol]=dict(symbol=symbol,name=STOCKS[symbol],registrant=submissions.get('name') or fundamentals['entity_name'],cik=cik,
                               sic_description=submissions.get('sicDescription'),fiscal_year_end=submissions.get('fiscalYearEnd'),
                               metrics=fundamentals['metrics'],filings=filings,note=note,
                               source_url=f'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={padded}')
        print(f'{symbol}: {sum(len(m["values"]) for m in fundamentals["metrics"].values())} annual values, {len(companies[symbol]["filings"])} filings',file=sys.stderr)
    funds={}
    for symbol,name,cik,series_id in ETFS:
        filing=series_nport(sec,series_id) if series_id else sec_edgar.latest_nport(sec.json(f'https://data.sec.gov/submissions/CIK{cik:010d}.json'))
        if not filing:raise RuntimeError(f'No NPORT-P filing found for {symbol}.')
        folder=filing['accession'].replace('-','')
        xml=sec.get(f'https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/primary_doc.xml').text
        if series_id and series_id not in xml:raise RuntimeError(f'{symbol} filing {filing["accession"]} does not cover series {series_id}.')
        fund=sec_edgar.parse_nport(xml)
        funds[symbol]=dict(symbol=symbol,name=name,cik=cik,series_id=series_id,accession=filing['accession'],filed=filing['filed'],
                           period_end=fund['period_end'],net_assets_usd=fund['net_assets_usd'],
                           filing_url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/',
                           holdings=[{k:h[k] for k in ('name','cusip','isin','weight','asset_category','payoff')} for h in fund['holdings']])
        print(f'{symbol}: {len(fund["holdings"])} holdings as of {fund["period_end"]}',file=sys.stderr)
    return dict(schema=1,generated_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                source='U.S. Securities and Exchange Commission, EDGAR (XBRL companyfacts, submissions and Form N-PORT)',
                companies=companies,funds=funds)


def unchanged(path,snapshot):
    """True when only the build time differs, so scheduled refreshes don't commit no-op changes."""
    try:previous=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return False
    strip=lambda data:{k:v for k,v in data.items() if k!='generated_at_utc'}
    return strip(previous)==strip(json.loads(json.dumps(snapshot)))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output',type=Path,default=SNAPSHOT)
    parser.add_argument('--user-agent',default=os.environ.get('SEC_USER_AGENT'))
    args=parser.parse_args(argv)
    if not args.user_agent:parser.error('Set SEC_USER_AGENT (app name and contact) or pass --user-agent.')
    snapshot=build(Sec(args.user_agent))
    if unchanged(args.output,snapshot):
        print(f'{args.output} already matches EDGAR; left as is.',file=sys.stderr);return
    args.output.parent.mkdir(parents=True,exist_ok=True)
    temporary=args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(snapshot,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
    temporary.replace(args.output)
    print(f'Wrote {args.output} ({args.output.stat().st_size//1024} KB).',file=sys.stderr)


if __name__=='__main__':main()

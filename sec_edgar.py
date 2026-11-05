"""Public SEC EDGAR research data: annual fundamentals, recent filings and ETF holdings.

SEC EDGAR content is public information that may be copied and redistributed
(https://www.sec.gov/about/privacy-information). This module only parses SEC
responses; it never touches licensed price providers. Network access happens in
the refresh CLI (sec_refresh.py), never inside the web app or tests.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import xml.etree.ElementTree as ET

SNAPSHOT=Path(__file__).resolve().parent/'sec_data'/'research_snapshot.json'
ANNUAL_FRAME=re.compile(r'^CY(\d{4})$')
YEARS=10
# Ordered fallbacks: the first concept that reports a given calendar year wins.
METRICS=(
 ('revenue','Revenue','USD',('RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet','RevenueFromContractWithCustomerIncludingAssessedTax')),
 ('operating_income','Operating income','USD',('OperatingIncomeLoss',)),
 ('net_income','Net income','USD',('NetIncomeLoss','ProfitLoss')),
 ('operating_cash_flow','Operating cash flow','USD',('NetCashProvidedByUsedInOperatingActivities',)),
 ('capital_expenditure','Capital expenditure','USD',('PaymentsToAcquirePropertyPlantAndEquipment','PaymentsToAcquireProductiveAssets')),
 ('eps_diluted','Diluted EPS','USD/shares',('EarningsPerShareDiluted','EarningsPerShareBasicAndDiluted')),
 ('diluted_shares','Diluted share count','shares',('WeightedAverageNumberOfDilutedSharesOutstanding','WeightedAverageNumberOfShareOutstandingBasicAndDiluted')),
)
FILING_FORMS=('10-K','10-Q','8-K','4','DEF 14A','SC 13D','SC 13G','SC 13D/A','SC 13G/A','S-1','20-F','6-K')
NPORT_NS={'n':'http://www.sec.gov/edgar/nport'}


def _days(start,end):
    return (date.fromisoformat(end)-date.fromisoformat(start)).days


def annual_fundamentals(facts:dict,years:int=YEARS)->dict:
    """Calendarized annual values from XBRL companyfacts, using SEC's de-duplicated CY frames."""
    gaap=facts.get('facts',{}).get('us-gaap',{})
    metrics={}
    for key,label,unit,concepts in METRICS:
        by_year={}
        for concept in concepts:
            for fact in gaap.get(concept,{}).get('units',{}).get(unit,[]):
                match=ANNUAL_FRAME.match(str(fact.get('frame','')))
                if not match or 'start' not in fact or not 330<=_days(fact['start'],fact['end'])<=380:continue
                year=int(match.group(1))
                by_year.setdefault(year,dict(year=year,value=float(fact['val']),period_end=fact['end'],
                                             form=fact.get('form'),accession=fact.get('accn'),concept=concept))
        metrics[key]=dict(label=label,unit=unit,values=[by_year[y] for y in sorted(by_year)[-years:]])
    _derive(metrics)
    return dict(entity_name=facts.get('entityName'),cik=int(facts.get('cik') or 0),metrics=metrics)


def merge_metrics(current:dict,predecessor:dict,years:int=YEARS)->dict:
    """Combine a successor registrant's annual values with its predecessor's; the successor wins per year."""
    merged={}
    for key,metric in current.items():
        rows={r['year']:r for r in predecessor.get(key,{}).get('values',[])}
        rows.update({r['year']:r for r in metric['values']})
        merged[key]=dict(metric,values=[rows[y] for y in sorted(rows)[-years:]])
    return merged


def _derive(metrics):
    def series(key):return {row['year']:row for row in metrics[key]['values']}
    cash,capex,revenue,operating,net=(series(k) for k in ('operating_cash_flow','capital_expenditure','revenue','operating_income','net_income'))
    fcf=[dict(year=y,value=cash[y]['value']-capex[y]['value'],period_end=cash[y]['period_end'],concept='operating_cash_flow - capital_expenditure')
         for y in sorted(cash) if y in capex]
    metrics['free_cash_flow']=dict(label='Free cash flow',unit='USD',values=fcf,derived=True)
    for key,label,top in (('operating_margin','Operating margin',operating),('net_margin','Net margin',net)):
        rows=[dict(year=y,value=top[y]['value']/revenue[y]['value'],period_end=top[y]['period_end'],concept=f'{key.split("_")[0]}_income / revenue')
              for y in sorted(top) if y in revenue and revenue[y]['value']]
        metrics[key]=dict(label=label,unit='ratio',values=rows,derived=True)


def recent_filings(submissions:dict,limit:int=20,forms=FILING_FORMS)->list[dict]:
    recent=submissions.get('filings',{}).get('recent',{})
    cik=int(submissions.get('cik') or 0);rows=[]
    for form,accession,filed,report,document,description in zip(recent.get('form',[]),recent.get('accessionNumber',[]),
            recent.get('filingDate',[]),recent.get('reportDate',[]),recent.get('primaryDocument',[]),recent.get('primaryDocDescription',[])):
        if form not in forms:continue
        folder=accession.replace('-','')
        rows.append(dict(form=form,filed=filed,report_date=report or None,description=description or None,accession=accession,
                         url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{document}' if document else
                             f'https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/'))
        if len(rows)>=limit:break
    return rows


def latest_nport(submissions:dict)->dict|None:
    """Most recent NPORT-P in a single-series trust's submissions feed."""
    recent=submissions.get('filings',{}).get('recent',{})
    for form,accession,filed in zip(recent.get('form',[]),recent.get('accessionNumber',[]),recent.get('filingDate',[])):
        if form=='NPORT-P':return dict(accession=accession,filed=filed)
    return None


def parse_nport(xml_text:str)->dict:
    root=ET.fromstring(xml_text)
    def text(node,path):
        found=node.find(path,NPORT_NS)
        return found.text.strip() if found is not None and found.text else None
    info=root.find('.//n:genInfo',NPORT_NS);fund=root.find('.//n:fundInfo',NPORT_NS)
    if info is None or fund is None:raise ValueError('Not an N-PORT submission.')
    holdings=[]
    for item in root.iterfind('.//n:invstOrSec',NPORT_NS):
        pct=text(item,'n:pctVal')
        if pct is None:continue
        isin=item.find('n:identifiers/n:isin',NPORT_NS);cusip=text(item,'n:cusip')
        cusip=None if not cusip or set(cusip)<={'0'} or cusip.upper()=='N/A' else cusip
        name=text(item,'n:name') or text(item,'n:title') or 'Unnamed holding'
        holdings.append(dict(name=name,title=text(item,'n:title'),cusip=cusip,
                             isin=isin.get('value') if isin is not None else None,
                             weight=float(pct)/100,value_usd=float(text(item,'n:valUSD') or 0),
                             asset_category=text(item,'n:assetCat'),issuer_category=text(item,'n:issuerCat'),
                             country=text(item,'n:invCountry'),payoff=text(item,'n:payoffProfile')))
    holdings.sort(key=lambda h:-h['weight'])
    return dict(registrant=text(info,'n:regName'),series_name=text(info,'n:seriesName'),
                period_end=text(info,'n:repPdDate'),fiscal_year_end=text(info,'n:repPdEnd'),
                net_assets_usd=float(text(fund,'n:netAssets') or 0),holdings=holdings)


def holding_key(holding:dict)->str:
    """Identity used to match the same security across funds."""
    if holding.get('isin'):return 'isin:'+holding['isin']
    if holding.get('cusip'):return 'cusip:'+holding['cusip']
    return 'name:'+re.sub(r'[^a-z0-9]','',holding['name'].lower())


SHORT_TERM='STIV'  # short-term investment vehicles, e.g. reinvested securities-lending collateral


def positions(fund:dict)->list[dict]:
    """Long investment positions, excluding short-term cash vehicles that are not part of the strategy."""
    return [h for h in fund['holdings'] if h['payoff']!='Short' and h['weight']>0 and h['asset_category']!=SHORT_TERM]


def fund_summary(fund:dict,top:int=25)->dict:
    holdings=positions(fund);weights=[h['weight'] for h in holdings]
    hhi=sum(w*w for w in weights)
    categories={}
    for h in holdings:categories[h['asset_category'] or 'Other']=categories.get(h['asset_category'] or 'Other',0)+h['weight']
    return dict(holding_count=len(holdings),top10_weight=sum(weights[:10]),
                effective_holdings=round(1/hhi,1) if hhi else None,
                short_term_vehicles_weight=sum(h['weight'] for h in fund['holdings'] if h['asset_category']==SHORT_TERM),
                asset_categories=sorted(([k,v] for k,v in categories.items()),key=lambda kv:-kv[1]),
                top_holdings=[dict(name=h['name'],weight=h['weight'],cusip=h['cusip'],isin=h['isin'],asset_category=h['asset_category']) for h in holdings[:top]])


def overlap(a:dict,b:dict,top:int=15)->dict:
    """Weight overlap: the sum over shared securities of the smaller of the two portfolio weights."""
    def weights(fund):
        out={}
        for h in positions(fund):
            row=out.setdefault(holding_key(h),dict(name=h['name'],cusip=h['cusip'],isin=h['isin'],weight=0.0));row['weight']+=h['weight']
        return out
    left,right=weights(a),weights(b)
    shared=[dict(name=left[k]['name'],cusip=left[k]['cusip'],isin=left[k]['isin'],weight_a=left[k]['weight'],weight_b=right[k]['weight'],
                 overlap=min(left[k]['weight'],right[k]['weight'])) for k in left.keys()&right.keys()]
    shared.sort(key=lambda r:-r['overlap'])
    return dict(weight_overlap=sum(r['overlap'] for r in shared),shared_count=len(shared),count_a=len(left),count_b=len(right),
                a_weight_in_b=sum(r['weight_a'] for r in shared),b_weight_in_a=sum(r['weight_b'] for r in shared),top_shared=shared[:top])

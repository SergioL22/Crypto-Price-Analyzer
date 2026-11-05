"""Public SEC research layer: parsers, overlap maths and the opt-in public routes."""
import json

import pytest
from fastapi.testclient import TestClient

import public_demo
import sec_edgar
import sec_refresh


def fact(val,start,end,frame=None,form='10-K',accn='0000000001-26-000001'):
    row=dict(val=val,start=start,end=end,form=form,accn=accn)
    if frame:row['frame']=frame
    return row


FACTS={'cik':123,'entityName':'Example Corp','facts':{'us-gaap':{
 'Revenues':{'units':{'USD':[fact(80,'2021-01-01','2021-12-31','CY2021')]}},
 'RevenueFromContractWithCustomerExcludingAssessedTax':{'units':{'USD':[
   fact(100,'2022-01-01','2022-12-31','CY2022'),fact(120,'2023-01-01','2023-12-31','CY2023'),
   fact(30,'2023-07-01','2023-09-30','CY2023Q3',form='10-Q'),   # quarter: ignored
   fact(118,'2023-01-01','2023-12-31')]}},                       # undeduplicated restatement: ignored
 'OperatingIncomeLoss':{'units':{'USD':[fact(20,'2022-01-01','2022-12-31','CY2022'),fact(30,'2023-01-01','2023-12-31','CY2023')]}},
 'NetCashProvidedByUsedInOperatingActivities':{'units':{'USD':[fact(25,'2023-01-01','2023-12-31','CY2023')]}},
 'PaymentsToAcquirePropertyPlantAndEquipment':{'units':{'USD':[fact(5,'2023-01-01','2023-12-31','CY2023')]}},
}}}


def test_annual_fundamentals_use_calendar_frames_with_concept_fallback():
    metrics=sec_edgar.annual_fundamentals(FACTS)['metrics']
    assert [(r['year'],r['value'],r['concept']) for r in metrics['revenue']['values']]==[
        (2021,80.0,'Revenues'),(2022,100.0,'RevenueFromContractWithCustomerExcludingAssessedTax'),
        (2023,120.0,'RevenueFromContractWithCustomerExcludingAssessedTax')]
    assert [(r['year'],r['value']) for r in metrics['free_cash_flow']['values']]==[(2023,20.0)]
    assert [round(r['value'],4) for r in metrics['operating_margin']['values']]==[0.2,0.25]
    assert metrics['net_income']['values']==[]  # missing concepts stay empty, never invented


def test_merge_metrics_prefers_successor_registrant():
    old=sec_edgar.annual_fundamentals(FACTS)['metrics']
    new={k:dict(v,values=[]) for k,v in old.items()}
    new['revenue']['values']=[dict(year=2023,value=999.0,period_end='2023-12-31')]
    merged=sec_edgar.merge_metrics(new,old)
    assert [(r['year'],r['value']) for r in merged['revenue']['values']]==[(2021,80.0),(2022,100.0),(2023,999.0)]


SUBMISSIONS={'cik':'123','filings':{'recent':{
 'form':['4','NPORT-P','10-Q','424B2'],'accessionNumber':['0001-26-000004','0001-26-000003','0001-26-000002','0001-26-000001'],
 'filingDate':['2026-10-02','2026-08-28','2026-08-01','2026-07-01'],'reportDate':['2026-09-30','2026-06-30','2026-06-30',''],
 'primaryDocument':['form4.xml','primary_doc.xml','q2.htm','b2.htm'],'primaryDocDescription':['FORM 4','','10-Q','']}}}


def test_recent_filings_and_latest_nport():
    rows=sec_edgar.recent_filings(SUBMISSIONS)
    assert [r['form'] for r in rows]==['4','10-Q']
    assert rows[1]['url']=='https://www.sec.gov/Archives/edgar/data/123/000126000002/q2.htm'
    assert sec_edgar.latest_nport(SUBMISSIONS)==dict(accession='0001-26-000003',filed='2026-08-28')


def nport(*holdings,series='S000000001'):
    items=''.join(f'<invstOrSec><name>{n}</name><title>{n}</title><cusip>{c}</cusip>'
                  +(f'<identifiers><isin value="{i}"/></identifiers>' if i else '<identifiers/>')
                  +f'<balance>1</balance><units>NS</units><curCd>USD</curCd><valUSD>{p*10}</valUSD><pctVal>{p}</pctVal>'
                  f'<payoffProfile>{pay}</payoffProfile><assetCat>{cat}</assetCat><issuerCat>CORP</issuerCat><invCountry>US</invCountry></invstOrSec>'
                  for n,c,i,p,cat,pay in holdings)
    return (f'<?xml version="1.0"?><edgarSubmission xmlns="http://www.sec.gov/edgar/nport"><headerData><seriesId>{series}</seriesId></headerData>'
            '<formData><genInfo><regName>Example Trust</regName><seriesName>Example Fund</seriesName><repPdEnd>2026-12-31</repPdEnd>'
            f'<repPdDate>2026-06-30</repPdDate></genInfo><fundInfo><netAssets>1000</netAssets></fundInfo><invstOrSecs>{items}</invstOrSecs></formData></edgarSubmission>')


A=sec_edgar.parse_nport(nport(('Alpha Inc','111111111','US1111111111',60,'EC','Long'),('Beta Inc','222222222','US2222222222',30,'EC','Long'),
                             ('Cash Fund','N/A',None,15,'STIV','Long'),('Gamma Short','333333333',None,5,'EC','Short')))
B=sec_edgar.parse_nport(nport(('Alpha Inc.','111111111','US1111111111',20,'EC','Long'),('Delta Inc','444444444','US4444444444',80,'EC','Long')))


def test_parse_nport_reads_weights_as_fractions():
    assert A['period_end']=='2026-06-30' and A['net_assets_usd']==1000
    assert [h['name'] for h in A['holdings']]==['Alpha Inc','Beta Inc','Cash Fund','Gamma Short']
    assert A['holdings'][0]['weight']==pytest.approx(.6)
    assert A['holdings'][2]['cusip'] is None
    with pytest.raises(ValueError):sec_edgar.parse_nport('<edgarSubmission xmlns="http://www.sec.gov/edgar/nport"/>')


def test_fund_summary_excludes_cash_vehicles_and_shorts():
    summary=sec_edgar.fund_summary(A)
    assert summary['holding_count']==2
    assert summary['short_term_vehicles_weight']==pytest.approx(.15)
    assert summary['top10_weight']==pytest.approx(.9)
    assert summary['effective_holdings']==pytest.approx(round(1/(.36+.09),1))


def test_overlap_matches_by_isin_and_uses_smaller_weight():
    result=sec_edgar.overlap(A,B)
    assert result['shared_count']==1 and result['top_shared'][0]['name']=='Alpha Inc'
    assert result['weight_overlap']==pytest.approx(.2)
    assert result['a_weight_in_b']==pytest.approx(.6) and result['b_weight_in_a']==pytest.approx(.2)
    assert sec_edgar.overlap(A,A)['weight_overlap']==pytest.approx(.9)


def test_refresh_requires_identifying_user_agent(monkeypatch):
    monkeypatch.delenv('SEC_USER_AGENT',raising=False)
    with pytest.raises(SystemExit):sec_refresh.main([])


SNAPSHOT=dict(schema=1,generated_at_utc='2026-11-04T00:00:00+00:00',source='SEC EDGAR test fixture',
    companies={'EXM':dict(symbol='EXM',name='Example',registrant='Example Corp',cik=123,metrics=sec_edgar.annual_fundamentals(FACTS)['metrics'],
                          filings=sec_edgar.recent_filings(SUBMISSIONS),note=None,source_url='https://www.sec.gov/')},
    funds={'AAA':dict(symbol='AAA',name='Fund A',cik=1,period_end='2026-06-30',filed='2026-08-28',net_assets_usd=1000,filing_url='https://www.sec.gov/',holdings=A['holdings']),
           'BBB':dict(symbol='BBB',name='Fund B',cik=2,period_end='2026-06-30',filed='2026-08-28',net_assets_usd=1000,filing_url='https://www.sec.gov/',holdings=B['holdings'])})


@pytest.fixture
def client(monkeypatch,tmp_path):
    path=tmp_path/'snapshot.json';path.write_text(json.dumps(SNAPSHOT),encoding='utf-8')
    monkeypatch.setattr(public_demo,'SEC_SNAPSHOT',path);monkeypatch.setattr(public_demo,'_sec_cache',{})
    monkeypatch.setenv('PUBLIC_DEMO_ORIGIN','https://testserver')
    return TestClient(public_demo.create_app(),base_url='https://testserver')


def test_sec_routes_are_opt_in(client,monkeypatch):
    monkeypatch.delenv('PUBLIC_SEC_RESEARCH',raising=False)
    for path in ('/v1/sec/coverage','/v1/sec/company?symbol=EXM','/filings-research.html'):
        assert client.get(path).status_code==404


def test_sec_routes_serve_snapshot_with_public_headers(client,monkeypatch):
    monkeypatch.setenv('PUBLIC_SEC_RESEARCH','1')
    coverage=client.get('/v1/sec/coverage')
    assert coverage.status_code==200 and coverage.headers['x-research-data']=='sec-public'
    assert coverage.headers['cache-control']=='public, max-age=3600'
    assert [c['symbol'] for c in coverage.json()['companies']]==['EXM']
    company=client.get('/v1/sec/company?symbol=EXM').json()
    assert company['metrics']['revenue']['values'][-1]['value']==120
    fund=client.get('/v1/sec/fund?symbol=AAA').json()
    assert 'holdings' not in fund and fund['summary']['holding_count']==2
    assert client.get('/v1/sec/overlap?a=AAA&b=BBB').json()['weight_overlap']==pytest.approx(.2)
    assert client.get('/v1/sec/overlap?a=AAA&b=AAA').status_code==422
    missing=client.get('/v1/sec/company?symbol=ZZZ')
    assert missing.status_code==404 and missing.headers['cache-control']=='no-store'
    assert client.get('/v1/sec/fund?symbol=spy;').status_code==422
    page=client.get('/filings-research.html')
    assert page.status_code==200 and '/assets/filings-research.js' in page.text
    assert 'SYNTHETIC DEMO' not in page.text and "script-src 'self';" in page.headers['content-security-policy']
    assert client.post('/v1/sec/coverage').status_code==405
    assert client.get('/v1/sec/coverage',headers={'Origin':'https://foreign.example'}).status_code==403


def test_market_nav_links_filings_only_when_enabled(client,monkeypatch):
    monkeypatch.setenv('PUBLIC_MARKET_WIDGETS','1')
    monkeypatch.delenv('PUBLIC_SEC_RESEARCH',raising=False)
    assert '/filings-research.html' not in client.get('/market-charts.html').text
    monkeypatch.setenv('PUBLIC_SEC_RESEARCH','1')
    assert '/filings-research.html' in client.get('/market-charts.html').text


def test_missing_snapshot_is_reported(monkeypatch,tmp_path):
    monkeypatch.setattr(public_demo,'SEC_SNAPSHOT',tmp_path/'absent.json');monkeypatch.setattr(public_demo,'_sec_cache',{})
    monkeypatch.setenv('PUBLIC_DEMO_ORIGIN','https://testserver');monkeypatch.setenv('PUBLIC_SEC_RESEARCH','1')
    response=TestClient(public_demo.create_app(),base_url='https://testserver').get('/v1/sec/coverage')
    assert response.status_code==503 and response.json()['error']['code']=='sec_snapshot_missing'


def test_committed_snapshot_is_well_formed():
    data=json.loads(sec_edgar.SNAPSHOT.read_text(encoding='utf-8'))
    assert set(data['companies'])==set(sec_refresh.STOCKS)
    assert set(data['funds'])=={symbol for symbol,*_ in sec_refresh.ETFS}
    for fund in data['funds'].values():
        assert fund['holdings'] and 0.5<sum(h['weight'] for h in sec_edgar.positions(fund))<1.1


import sec_live


class Clock:
    def __init__(self):self.now=1000.0
    def __call__(self):return self.now


LIVE_SUBMISSIONS={'cik':'123','filings':{'recent':{'form':['8-K'],'accessionNumber':['0001-26-000009'],'filingDate':['2026-11-04'],
    'reportDate':['2026-11-03'],'primaryDocument':['event.htm'],'primaryDocDescription':['8-K']}}}


def test_live_filings_cache_and_backoff():
    clock=Clock();calls=[]
    def fetch(cik):
        calls.append(cik)
        if len(calls)==2:raise OSError('SEC unavailable')
        return LIVE_SUBMISSIONS
    live=sec_live.LiveFilings(fetch,ttl=60,backoff=30,clock=clock,wall=lambda:1_790_000_000)
    rows,_=live.filings(123);assert rows[0]['form']=='8-K' and len(calls)==1
    live.filings(123);assert len(calls)==1          # cached
    clock.now+=61;assert live.filings(123)[0]==rows   # refresh fails: previous rows kept
    clock.now+=10;live.filings(123);assert len(calls)==2  # backing off after the failure
    assert sec_live.LiveFilings(lambda cik:1/0).filings(1) is None


def test_merge_filings_keeps_predecessor_rows_once():
    merged=sec_live.merge_filings(sec_edgar.recent_filings(LIVE_SUBMISSIONS),sec_edgar.recent_filings(SUBMISSIONS))
    assert [r['accession'] for r in merged]==['0001-26-000009','0001-26-000004','0001-26-000002']
    assert len(sec_live.merge_filings(merged,merged))==3


def live_client(monkeypatch,tmp_path,fetch):
    path=tmp_path/'snapshot.json';path.write_text(json.dumps(SNAPSHOT),encoding='utf-8')
    monkeypatch.setattr(public_demo,'SEC_SNAPSHOT',path);monkeypatch.setattr(public_demo,'_sec_cache',{})
    monkeypatch.setenv('PUBLIC_DEMO_ORIGIN','https://testserver');monkeypatch.setenv('PUBLIC_SEC_RESEARCH','1')
    return TestClient(public_demo.create_app(sec_fetch=fetch),base_url='https://testserver')


def test_filings_endpoint_uses_live_data_with_snapshot_fallback(monkeypatch,tmp_path):
    client=live_client(monkeypatch,tmp_path,lambda cik:LIVE_SUBMISSIONS)
    response=client.get('/v1/sec/filings?symbols=EXM,ZZZ,EXM')
    assert response.status_code==200 and response.headers['cache-control']=='public, max-age=300'
    body=response.json();company=body['companies'][0]
    assert len(body['companies'])==1 and body['uncovered']==['ZZZ']
    assert company['filings_source']=='live' and company['filings'][0]['accession']=='0001-26-000009'
    assert client.get('/v1/sec/company?symbol=EXM').json()['filings_source']=='live'
    failing=live_client(monkeypatch,tmp_path,lambda cik:1/0)
    company=failing.get('/v1/sec/filings?symbols=EXM').json()['companies'][0]
    assert company['filings_source']=='snapshot' and [f['form'] for f in company['filings']]==['4','10-Q']
    assert failing.get('/v1/sec/filings?symbols=exm').status_code==422
    assert failing.get('/v1/sec/filings?symbols='+','.join(['AAA']*21)).status_code==422


def test_without_user_agent_filings_come_from_snapshot(client,monkeypatch):
    monkeypatch.setenv('PUBLIC_SEC_RESEARCH','1')
    company=client.get('/v1/sec/filings?symbols=EXM').json()['companies'][0]
    assert company['filings_source']=='snapshot' and company['filings_fetched_at_utc']==SNAPSHOT['generated_at_utc']


def test_refresh_skips_rewrite_when_only_build_time_changed(tmp_path):
    path=tmp_path/'snapshot.json';path.write_text(json.dumps(SNAPSHOT),encoding='utf-8')
    assert sec_refresh.unchanged(path,dict(SNAPSHOT,generated_at_utc='2027-01-01T00:00:00+00:00'))
    assert not sec_refresh.unchanged(path,dict(SNAPSHOT,source='changed'))
    assert not sec_refresh.unchanged(tmp_path/'absent.json',SNAPSHOT)


def test_price_lab_page_is_opt_in_and_self_contained(client,monkeypatch):
    monkeypatch.delenv('PUBLIC_SEC_RESEARCH',raising=False)
    assert client.get('/price-lab.html').status_code==404
    monkeypatch.setenv('PUBLIC_SEC_RESEARCH','1')
    page=client.get('/price-lab.html')
    assert page.status_code==200 and page.headers['x-research-data']=='visitor-supplied'
    assert "connect-src 'self'" in page.headers['content-security-policy'] and 'SYNTHETIC DEMO' not in page.text
    assert '/assets/price-lab-core.js' in page.text and 'never leaves this browser' in page.text


TICKERS={'0':{'cik_str':555,'ticker':'NEWC','title':'New Co'},'1':{'cik_str':556,'ticker':'BRK-B','title':'Berkshire'}}


def fake_sec(calls):
    def get(url):
        calls.append(url)
        if url.endswith('company_tickers.json'):return TICKERS
        if 'companyfacts' in url:return dict(FACTS,cik=555,entityName='NEW CO INC')
        return dict(SUBMISSIONS,cik='555',name='NEW CO INC')
    return get


def test_company_lookup_caches_and_limits_new_lookups():
    clock=Clock();calls=[]
    lookup=sec_live.CompanyLookup(fake_sec(calls),window=60,window_limit=2,clock=clock)
    record=lookup.company('newc')
    assert record['name']=='New Co' and record['cik']==555 and record['metrics']['revenue']['values'][-1]['value']==120
    assert len(calls)==3;lookup.company('NEWC');assert len(calls)==3   # cached
    assert lookup.company('BRK.B')['symbol']=='BRK-B'
    with pytest.raises(sec_live.LookupError_) as error:lookup.company('ZZZZ')
    assert error.value.status==429                                    # window budget used up
    clock.now+=61
    with pytest.raises(sec_live.LookupError_) as error:lookup.company('ZZZZ')
    assert error.value.status==404
    with pytest.raises(sec_live.LookupError_) as error:lookup.company('NOT-VALID1')
    assert error.value.status==422


def test_lookup_endpoint(monkeypatch,tmp_path):
    path=tmp_path/'snapshot.json';path.write_text(json.dumps(SNAPSHOT),encoding='utf-8')
    monkeypatch.setattr(public_demo,'SEC_SNAPSHOT',path);monkeypatch.setattr(public_demo,'_sec_cache',{})
    monkeypatch.setenv('PUBLIC_DEMO_ORIGIN','https://testserver');monkeypatch.setenv('PUBLIC_SEC_RESEARCH','1')
    calls=[];app=public_demo.create_app(sec_fetch=lambda cik:LIVE_SUBMISSIONS,sec_lookup=sec_live.CompanyLookup(fake_sec(calls)))
    client=TestClient(app,base_url='https://testserver')
    found=client.get('/v1/sec/lookup?symbol=newc')
    assert found.status_code==200 and found.json()['symbol']=='NEWC' and found.json()['filings_source']=='live'
    assert 'fetched_at_epoch' not in found.json() and found.headers['cache-control']=='public, max-age=300'
    assert client.get('/v1/sec/lookup?symbol=EXM').json()['registrant']=='Example Corp'   # covered list served from snapshot
    assert client.get('/v1/sec/lookup?symbol=QQQQ').status_code==404
    assert client.get('/v1/sec/lookup?symbol=a;b').status_code==422
    offline=TestClient(public_demo.create_app(),base_url='https://testserver')
    assert offline.get('/v1/sec/lookup?symbol=NEWC').json()['error']['code']=='lookup_unavailable'


def form4(code,shares,price,date='2026-10-27',planned=True,title='SVP',director=False):
    return (f'<ownershipDocument><reportingOwner><reportingOwnerId><rptOwnerName>Pat Insider</rptOwnerName></reportingOwnerId>'
            f'<reportingOwnerRelationship><isDirector>{str(director).lower()}</isDirector><isOfficer>true</isOfficer><officerTitle>{title}</officerTitle></reportingOwnerRelationship></reportingOwner>'
            f'<aff10b5One>{str(planned).lower()}</aff10b5One><nonDerivativeTable><nonDerivativeTransaction><transactionDate><value>{date}</value></transactionDate>'
            f'<transactionCoding><transactionCode>{code}</transactionCode></transactionCoding><transactionAmounts><transactionShares><value>{shares}</value></transactionShares>'
            + (f'<transactionPricePerShare><value>{price}</value></transactionPricePerShare>' if price is not None else '')
            + '<transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts></nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>')


def test_parse_form4_and_summary_separate_open_market_trades():
    sale=sec_edgar.parse_form4(form4('S',100,50.0))
    assert sale['owners']==[dict(name='Pat Insider',roles=['SVP'])]
    assert sale['transactions'][0]==dict(date='2026-10-27',code='S',label='Open-market sale',shares=100.0,price=50.0,value=5000.0,direction='D',planned=True)
    grant=sec_edgar.parse_form4(form4('A',10,None,planned=False))
    buy=sec_edgar.parse_form4(form4('P',20,10.0,planned=False,director=True))
    old=sec_edgar.parse_form4(form4('P',1,1.0,date='2024-01-01'))
    summary=sec_edgar.insider_summary([sale,grant,buy,old],since='2025-11-05')
    assert summary['buys']==dict(count=1,shares=20.0,value=200.0)
    assert summary['sales']==dict(count=1,shares=100.0,value=5000.0,planned=1)
    assert summary['other_transactions']==1 and len(summary['recent'])==3
    assert summary['insiders'][0]['sold']==5000.0 and summary['insiders'][0]['bought']==200.0


def test_insider_activity_reads_recent_form4s_once():
    calls=[]
    subs={'filings':{'recent':{'form':['4','10-Q','4','4'],'accessionNumber':['0001-26-000001','0001-26-000002','0001-26-000003','0001-25-000004'],
          'filingDate':['2026-10-29','2026-10-01','2026-09-01','2025-01-01'],'primaryDocument':['xslF345X06/form4.xml','q.htm','xslF345X06/f.xml','xslF345X06/old.xml']}}}
    def text(url):
        calls.append(url)
        if url.endswith('f.xml'):return '<not-xml'
        return form4('S',100,50.0)
    insiders=sec_live.InsiderActivity(lambda url:subs,text,clock=Clock(),today=lambda:'2026-11-05')
    summary=insiders.activity(123)
    assert calls==['https://www.sec.gov/Archives/edgar/data/123/000126000001/form4.xml','https://www.sec.gov/Archives/edgar/data/123/000126000003/f.xml']
    assert summary['forms']==1 and summary['sales']['count']==1 and summary['since']=='2025-11-05'
    assert summary['recent'][0]['url'].endswith('/xslF345X06/form4.xml')
    insiders.activity(123);assert len(calls)==2


def test_insiders_endpoint(monkeypatch,tmp_path):
    path=tmp_path/'snapshot.json';path.write_text(json.dumps(SNAPSHOT),encoding='utf-8')
    monkeypatch.setattr(public_demo,'SEC_SNAPSHOT',path);monkeypatch.setattr(public_demo,'_sec_cache',{})
    monkeypatch.setenv('PUBLIC_DEMO_ORIGIN','https://testserver');monkeypatch.setenv('PUBLIC_SEC_RESEARCH','1')
    class Fake:
        def activity(self,cik):
            assert cik==123
            return dict(sec_edgar.insider_summary([],since='2025-11-05'),truncated=False,fetched_at_epoch=1_790_000_000)
    client=TestClient(public_demo.create_app(sec_fetch=lambda cik:LIVE_SUBMISSIONS,sec_insiders=Fake()),base_url='https://testserver')
    body=client.get('/v1/sec/insiders?symbol=EXM').json()
    assert body['symbol']=='EXM' and body['buys']['count']==0 and 'fetched_at_epoch' not in body
    assert client.get('/v1/sec/insiders?symbol=ZZZ').status_code==404
    assert TestClient(public_demo.create_app(),base_url='https://testserver').get('/v1/sec/insiders?symbol=EXM').status_code==503

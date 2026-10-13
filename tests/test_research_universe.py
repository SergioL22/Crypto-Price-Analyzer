from datetime import datetime, timezone
import pytest
from assets import Asset
from datasets import DatasetStore, snapshot
from research_universe import resolve, run, audit, UNIVERSE
from stock_provider import StockDataError
import pandas as pd


def test_resolver_never_guesses_a_venue():
    a=Asset('stock','twelvedata','MSFT','Microsoft','XNGS','USD','America/New_York').public()
    assert resolve([a],'stock','MSFT') == a['id']
    with pytest.raises(ValueError): resolve([a,a],'stock','MSFT')
    with pytest.raises(ValueError): resolve([a],'etf','MSFT')


def test_missing_universe_is_reported_without_provider_requests(tmp_path):
    result=run(DatasetStore(tmp_path/'empty.db'))
    assert len(result['assets']) == 10
    assert not result['all_assets_audited']
    assert all(a['status']=='missing_snapshot' for a in result['assets'])


def test_quota_stops_remaining_captures_and_does_not_retry(tmp_path):
    class Service:
        calls=0
        def catalog(self,now):
            return dict(stale=False,assets=[Asset(k,'twelvedata',s,s,'XNYS','USD','America/New_York').public() for k,s in UNIVERSE])
        def research(self,*args):
            self.calls+=1
            raise StockDataError('stock_quota','DO NOT ECHO PROVIDER SECRET')
    service=Service()
    report=run(DatasetStore(tmp_path/'empty.db'),collect=True,service=service,pause=lambda _:None)
    assert service.calls == 1
    assert report['assets'][0]['status']=='capture_failed'
    assert all(a['status']=='not_attempted' for a in report['assets'][1:])
    assert 'SECRET' not in str(report)


def test_audit_purges_targets_at_year_boundary_and_pins_artifacts(tmp_path):
    dates=pd.bdate_range('2017-01-01','2026-10-01').strftime('%Y-%m-%d').tolist()
    asset=Asset('stock','twelvedata','MSFT','Microsoft','XNGS','USD','America/New_York')
    source=snapshot(asset,[dict(date=d,price=100+i*.01,volume=None) for i,d in enumerate(dates)],dates,
                    datetime(2026,10,2,tzinfo=timezone.utc),adjustment='splits',price_definition='Synthetic test')
    store=DatasetStore(tmp_path/'research.db'); key=store.save(source)
    report=audit(store,key)
    features=store.load(report['feature_id'])
    eligible=[r for r in features['rows'] if r['supervised_ready']]
    block=report['blocks'][0]
    assert block['year']==2021 and block['eligible']
    assert block['training_rows']==sum(r['session']<'2021-01-01' and r['label']['end_session']<block['first_test_session'] for r in eligible)
    assert block['last_target_session'] <= '2021-12-31'
    assert report['snapshot_id']==key
    assert report['unknown_volume']==len(dates)
    assert report['blocks'][-1]['partial']


def test_stale_catalog_is_not_used(tmp_path):
    class Service:
        def catalog(self,now): return dict(stale=True,assets=[])
    report=run(DatasetStore(tmp_path/'empty.db'),collect=True,service=Service(),pause=lambda _:None)
    assert report['catalog_error']=='catalog_invalid'
    assert all(a['status']=='not_attempted' for a in report['assets'])

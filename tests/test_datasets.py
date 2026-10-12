from datetime import datetime, timezone
import hashlib
import sqlite3
import pandas as pd
import pytest
from assets import crypto_asset
from datasets import DatasetStore, snapshot, canonical
from dataset_features import build_features, FEATURE_COLUMNS
from dataset_cli import capture, main


def sample(count=100, missing=()):
    days = pd.date_range('2025-01-01', periods=count).strftime('%Y-%m-%d').tolist()
    rows = [dict(date=d, price=100+i+(i%4), volume=None) for i,d in enumerate(days) if i not in missing]
    return snapshot(crypto_asset(dict(id='bitcoin',name='Bitcoin')), rows, days,
                    datetime(2026,1,1,tzinfo=timezone.utc), adjustment='provider_daily_sample', price_definition='Test sample')


def identity(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def test_store_deduplicates_and_retains_revisions(tmp_path):
    store = DatasetStore(tmp_path/'research.db')
    source = sample(); first = store.save(source)
    assert store.save(source) == first
    revised = sample(); revised['observations'][0]['price'] += 1
    second = store.save(revised)
    assert second != first and len(store.listing()) == 2
    assert store.load(first) == source
    assert store.load(second) == revised


def test_tampering_is_detected(tmp_path):
    store=DatasetStore(tmp_path/'research.db'); key=store.save(sample())
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE artifacts SET payload=? WHERE id=?', ('{}',key))
    with pytest.raises(ValueError,match='integrity'): store.load(key)


def test_causal_prefix_is_unchanged_by_future_prices():
    full=sample(); altered=sample()
    for row in altered['observations'][60:]: row['price'] *= 10
    left=build_features(full,identity(full)); right=build_features(altered,identity(altered))
    assert [r['features'] for r in left['rows'][:60]] == [r['features'] for r in right['rows'][:60]]
    prefix=sample(60); short=build_features(prefix,identity(prefix))
    assert [r['features'] for r in short['rows']] == [r['features'] for r in left['rows'][:60]]


def test_targets_are_separate_and_final_horizon_is_unlabeled():
    source=sample(); data=build_features(source,identity(source),horizon=5)
    assert data['quality']['supervised_ready'] == 61
    assert all(r['label'] is None for r in data['rows'][-5:])
    assert all(set(r['features']) == set(FEATURE_COLUMNS) for r in data['rows'])
    first=data['rows'][34]
    assert first['label']['forward_return'] == pytest.approx(source['observations'][39]['price']/source['observations'][34]['price']-1)
    assert first['label']['end_session'] == source['observations'][39]['date']


def test_gap_breaks_labels_and_restarts_feature_warmup():
    source=sample(100,missing=(50,)); data=build_features(source,identity(source))
    assert len(data['rows'])==99
    assert all(r['label'] is None for r in data['rows'][45:50])
    assert all(not r['feature_ready'] for r in data['rows'][50:84])
    assert data['rows'][84]['feature_ready']
    assert data['quality']['missing_sessions']==['2025-02-20']


@pytest.mark.parametrize('price',[0,-1,float('inf'),float('nan'),True])
def test_invalid_prices_never_enter_snapshot(price):
    data=sample(); rows=data['observations']; rows[0]['price']=price
    with pytest.raises(ValueError):
        snapshot(crypto_asset(dict(id='bitcoin',name='Bitcoin')),rows,data['expected_sessions'],datetime.now(timezone.utc),adjustment='provider_daily_sample',price_definition='test')


def test_crypto_capture_excludes_current_day_and_does_not_persist():
    calls=[]
    def history(coin,days,*,persist):
        calls.append((coin,days,persist))
        return pd.DataFrame(dict(date=pd.date_range('2026-01-01',periods=91,tz='UTC'),price=100.,volume=None))
    result=capture('crypto','bitcoin',90,now=datetime(2026,4,1,12,tzinfo=timezone.utc),history=history)
    assert calls==[('bitcoin',91,False)]
    assert result['expected_sessions'][-1]=='2026-03-31'
    assert result['observations'][-1]['date']=='2026-03-31'
    assert result['historical_vintage_available'] is False


def test_offline_cli_builds_reproducible_artifact(tmp_path,capsys):
    path=tmp_path/'research.db'; store=DatasetStore(path); key=store.save(sample())
    assert main(['--store',str(path),'features',key,'--horizon','5'])==0
    first=capsys.readouterr().out
    assert main(['--store',str(path),'features',key,'--horizon','5'])==0
    assert capsys.readouterr().out==first
    assert len(store.listing())==2
    assert main(['--store',str(path),'show',key])==0


def test_wrong_parent_and_invalid_horizon_fail():
    source=sample()
    with pytest.raises(ValueError): build_features(source,'a'*64)
    for horizon in (True,0,31,1.5):
        with pytest.raises(ValueError): build_features(source,identity(source),horizon=horizon)


def test_benchmark_context_is_causal_and_missing_sessions_are_not_filled():
    source=sample(); benchmark=sample(missing=(70,)); altered=sample(missing=(70,))
    for row in altered['observations'][80:]: row['price'] *= 2
    first=build_features(source,identity(source),benchmark=benchmark,benchmark_id=identity(benchmark))
    second=build_features(source,identity(source),benchmark=altered,benchmark_id=identity(altered))
    assert [r['features'] for r in first['rows'][:80]] == [r['features'] for r in second['rows'][:80]]
    assert first['rows'][60]['features']['relative_return_5']==0
    assert first['rows'][70]['features']['benchmark_return_5'] is None
    assert not first['rows'][70]['supervised_ready']
    assert first['benchmark_id']==identity(benchmark)


def test_stock_capture_preserves_ohlcv_and_trading_calendar():
    from assets import Asset
    from stock_service import session_window
    now=datetime(2026,9,8,18,tzinfo=timezone.utc)
    asset=Asset('stock','twelvedata','ABC','Example','XNYS','USD','America/New_York')
    _,_,sessions=session_window(90,now)
    class Stocks:
        def research(self, identity, days, current):
            assert identity==asset.id and current==now
            return dict(asset=asset.public(),bars=[dict(date=d,close=100,volume=50,open=99,high=101,low=98) for d in sessions])
    data=capture('stock',asset.id,90,now=now,stocks=Stocks())
    assert data['expected_sessions'][-1]=='2026-09-04'
    assert data['observations'][-1]['open']==99
    assert not data['quality']['missing_sessions']
    assert data['collection']['calendar_version']
    with pytest.raises(ValueError,match='class'): capture('etf',asset.id,90,now=now,stocks=Stocks())

def test_decade_stock_capture_retains_full_requested_calendar():
    from assets import Asset
    from stock_service import session_window
    now=datetime(2026,10,12,12,tzinfo=timezone.utc)
    asset=Asset('etf','twelvedata','SPY','Example ETF','ARCX','USD','America/New_York')
    _,_,sessions=session_window(3653,now)
    class Stocks:
        def research(self,identity,days,current):
            assert days==3653 and identity==asset.id
            return dict(asset=asset.public(),bars=[dict(date=d,close=100,volume=50,open=99,high=101,low=98) for d in sessions])
    data=capture('etf',asset.id,3653,now=now,stocks=Stocks())
    assert len(data['observations'])>2500
    assert data['expected_sessions']==sessions
    assert data['collection']['requested_calendar_days']==3653
    with pytest.raises(ValueError):capture('crypto','bitcoin',3653,now=now)
    with pytest.raises(ValueError):capture('stock',asset.id,3661,now=now,stocks=Stocks())

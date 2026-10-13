from copy import deepcopy
from datetime import datetime,timezone,timedelta
import sqlite3
import numpy as np
import pytest
from assets import Asset
from datasets import DatasetStore,snapshot
from dataset_features import build_features
from modeling import digest
from stock_service import session_window
from phase4_evaluation import evaluate_asset,evaluate_universe
from prediction_journal import Journal,issue,settle,summary


def sample(now):
    dates=session_window(3653,now)[2]
    # Date-dependent prices keep the origin unchanged across later snapshots.
    first=datetime(2010,1,1).date()
    rows=[dict(date=d,price=100+((datetime.fromisoformat(d).date()-first).days)*.01+3*np.sin((datetime.fromisoformat(d).date()-first).days/5),volume=1000) for d in dates]
    return snapshot(Asset('stock','twelvedata','MSFT','Microsoft','XNGS','USD','America/New_York'),rows,dates,now,adjustment='splits',price_definition='Synthetic test only')


def test_expanding_fit_is_unchanged_by_future_labels_and_features():
    source=sample(datetime(2026,1,2,22,tzinfo=timezone.utc)); features=build_features(source,digest(source))
    first=evaluate_asset(features,source)
    altered=deepcopy(features)
    for r in altered['rows']:
        if r['session']>='2021-01-01':
            if r['label']: r['label']['up']=1-r['label']['up']
            r['features']={k:None if v is None else v*100 for k,v in r['features'].items()}
    second=evaluate_asset(altered,source)
    left,right=first['blocks'][0],second['blocks'][0]
    assert left['status']=='evaluated' and left['model']==right['model']
    assert max(left['train_target_end_sessions'])<left['evaluations']['logistic']['predictions'][0]['session']
    counts=[v['metrics']['count'] for v in left['evaluations'].values()]
    assert len(set(counts))==1
    for method in left['evaluations'].values():
        assert all(t['exit_session']<='2021-12-31' for t in method['illustrative_execution']['trades'])


def test_short_blocks_are_unavailable_and_fixed_universe_required(tmp_path):
    source=sample(datetime(2020,1,2,22,tzinfo=timezone.utc))
    result=evaluate_asset(build_features(source,digest(source)),source)
    assert all(b['status']=='unavailable' for b in result['blocks'])
    with pytest.raises(ValueError,match='universe'): evaluate_universe(DatasetStore(tmp_path/'x.db'),dict(assets=[]))


def test_issue_is_fresh_unique_and_settlement_is_later_append_only(tmp_path):
    now=datetime(2025,1,6,22,tzinfo=timezone.utc)
    store=DatasetStore(tmp_path/'research.db'); journal=Journal(tmp_path/'journal.db')
    source=sample(now); key=store.save(source)
    prediction=issue(store,journal,key,now=now)
    assert prediction['event']['target_sessions']==['2025-01-07','2025-01-08','2025-01-10','2025-01-13','2025-01-14']
    assert 0<prediction['event']['probability_up']<1
    assert prediction['event']['model_sha256']==digest(prediction['event']['model'])
    with pytest.raises(ValueError,match='already'): issue(store,journal,key,now=now)
    with pytest.raises(ValueError): settle(store,journal,prediction['id'],key,now=now+timedelta(days=1))
    later=datetime(2025,1,14,22,tzinfo=timezone.utc)
    outcome_key=store.save(sample(later))
    settle(store,journal,prediction['id'],outcome_key,now=later)
    assert journal.events()[0]==prediction
    result=summary(journal)
    assert result['completed_outcomes']==1 and result['pending']==0 and not result['promoted']
    assert set(result['baseline_metrics'])=={'always_up','training_prior','momentum'}
    assert sum(b['count'] for b in result['calibration_bins'])==1
    assert result['by_asset'][0]['completed_outcomes']==1
    with pytest.raises(ValueError,match='already'): settle(store,journal,prediction['id'],outcome_key,now=later)
    with sqlite3.connect(journal.path) as db:
        with pytest.raises(sqlite3.IntegrityError): db.execute('DELETE FROM events')
        with pytest.raises(sqlite3.IntegrityError): db.execute("UPDATE events SET payload='{}'")


def test_stale_missing_and_revised_origin_are_rejected(tmp_path):
    now=datetime(2025,1,6,22,tzinfo=timezone.utc); store=DatasetStore(tmp_path/'r.db'); journal=Journal(tmp_path/'j.db')
    source=sample(now); key=store.save(source)
    with pytest.raises(ValueError): issue(store,journal,key,now=now+timedelta(days=2))
    missing=deepcopy(source); missing['observations'].pop(); missing['quality']['missing_sessions']=[source['observations'][-1]['date']]
    with pytest.raises(ValueError): issue(store,journal,store.save(missing),now=now)
    assert journal.events()==[]
    prediction=issue(store,journal,key,now=now)
    later=datetime(2025,1,14,22,tzinfo=timezone.utc); revised=sample(later)
    next(r for r in revised['observations'] if r['date']=='2025-01-06')['price']+=1
    with pytest.raises(ValueError,match='revised'): settle(store,journal,prediction['id'],store.save(revised),now=later)
    assert summary(journal)['completed_outcomes']==0


def test_journal_hash_chain_detects_external_tampering(tmp_path):
    now=datetime(2025,1,6,22,tzinfo=timezone.utc)
    store=DatasetStore(tmp_path/'r.db'); journal=Journal(tmp_path/'j.db')
    issue(store,journal,store.save(sample(now)),now=now)
    with sqlite3.connect(journal.path) as db:
        db.execute('DROP TRIGGER no_update')
        db.execute("UPDATE events SET payload='{}'")
    with pytest.raises(ValueError,match='integrity'): journal.events()


def test_issuance_has_no_retrospective_timestamp_cli_option():
    from phase4_cli import main
    with pytest.raises(SystemExit): main(['issue','--snapshot','a'*64,'--now','2020-01-01'])

from copy import deepcopy
import pytest
from prediction_validation import report
from prediction_journal import Journal


class SampleJournal:
    def __init__(self,events):self._events=events
    def events(self):return deepcopy(self._events)


def entries(count=2,*,parallel=False,completed=True):
    result=[]
    for i in range(count):
        start='2026-01-05' if parallel else f'2026-{i+1:02d}-05'
        end='2026-01-09' if parallel else f'2026-{i+1:02d}-09'
        result.append(dict(id=str(i),event=dict(kind='prediction',asset=dict(id=f'asset{i}'),protocol_sha256='protocol',implementation_sha256='impl',target_sessions=[start,end],probability_up=.8 if i%2==0 else .2,baseline_probabilities=dict(always_up=1.,training_prior=.5,momentum=0.))))
        if completed:result.append(dict(id='outcome'+str(i),event=dict(kind='outcome',prediction_id=str(i),up=1 if i%2==0 else 0)))
    return result


def test_pending_and_empty_reports_never_invent_accuracy_or_promote(tmp_path):
    empty=report(Journal(tmp_path/'absent.db'));assert empty['predictions']==0 and empty['cohorts']==[]
    result=report(SampleJournal(entries(completed=False)))
    assert result['completed']==0 and result['pending']==2 and result['status']=='collecting'
    assert result['cohorts'][0]['model'] is None and not result['promoted'] and not result['calibrated']


def test_metrics_and_baselines_use_identical_completed_targets():
    result=report(SampleJournal(entries()))['cohorts'][0]
    assert result['model']['accuracy']==1 and result['model']['brier']==pytest.approx(.04)
    assert result['baselines']['always_up']['accuracy']==.5
    assert result['baselines']['training_prior']['brier']==.25
    assert result['comparisons']['training_prior']['brier_difference']==pytest.approx(-.21)
    assert all(v['count']==2 for v in result['baselines'].values())


def test_parallel_assets_do_not_multiply_independent_windows():
    result=report(SampleJournal(entries(10,parallel=True)))['cohorts'][0]
    assert result['completed']==10 and result['nonoverlapping_start_dates']==1
    assert all(v['exploratory_date_bootstrap_95'] is None for v in result['comparisons'].values())


def test_asset_filter_and_protocol_cohorts_are_not_pooled():
    events=entries();events[2]['event']['implementation_sha256']='other'
    result=report(SampleJournal(events));assert len(result['cohorts'])==2
    selected=report(SampleJournal(events),'asset1');assert selected['completed']==1 and selected['predictions']==1


def test_calibration_boundary_belongs_to_exactly_one_bin():
    events=entries(5)
    for i,e in enumerate(events[::2]):e['event']['probability_up']=[0,.2,.4,.6,1][i]
    bins=report(SampleJournal(events))['cohorts'][0]['calibration_bins']
    assert [b['count'] for b in bins]==[1,1,1,1,1]


def test_validation_uses_verified_journal_chain(tmp_path):
    journal=Journal(tmp_path/'j.db');journal.append(entries(1,completed=False)[0]['event'])
    assert report(journal)['pending']==1
    import sqlite3
    with sqlite3.connect(journal.path) as db:
        db.execute('DROP TRIGGER no_update');db.execute("UPDATE events SET payload='{}'")
    with pytest.raises(ValueError,match='integrity'):report(journal)


def test_intervals_require_twenty_nonoverlapping_dates_and_do_not_promote():
    from datetime import date,timedelta
    events=[]
    for i in range(20):
        pair=entries(1);start=date(2025,1,6)+timedelta(days=7*i)
        pair[0]['id']=str(i);pair[0]['event']['target_sessions']=[start.isoformat(),(start+timedelta(days=4)).isoformat()]
        pair[1]['event']['prediction_id']=str(i);events.extend(pair)
    result=report(SampleJournal(events));cohort=result['cohorts'][0]
    assert cohort['nonoverlapping_start_dates']==20
    assert cohort['comparisons']['training_prior']['exploratory_date_bootstrap_95']==pytest.approx([-.21,-.21])
    assert len(cohort['by_quarter'])==2 and not result['promoted']

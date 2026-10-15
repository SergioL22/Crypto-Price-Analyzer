"""Read-only prospective validation; never promotes a model or rewrites events."""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import json
import sqlite3
from pathlib import Path
import numpy as np
from prediction_journal import Journal

BASELINES=('always_up','training_prior','momentum')


def scores(rows,key):
    if not rows:return None
    y=np.asarray([r['up'] for r in rows]);p=np.asarray([r[key] for r in rows]);decision=p>=.5
    clipped=np.clip(p,1e-12,1-1e-12)
    return dict(count=len(rows),accuracy=float(np.mean(decision==y)),
                balanced_accuracy=float(np.mean([np.mean(decision[y==c]==c) for c in (0,1)])) if len(set(y))==2 else None,
                brier=float(np.mean((p-y)**2)),log_loss=float(-np.mean(y*np.log(clipped)+(1-y)*np.log(1-clipped))),
                confusion={f'actual_{a}_predicted_{b}':int(np.sum((y==a)&(decision==b))) for a in (0,1) for b in (0,1)})


def nonoverlapping_dates(rows):
    windows=sorted({(r['start'],r['end']) for r in rows})
    accepted=[];end=''
    for first,last in windows:
        if first>end:accepted.append(first);end=last
    return accepted


def comparison(rows,name):
    if not rows:return None
    groups=defaultdict(list)
    for r in rows:
        groups[r['start']].append((r['model']-r['up'])**2-(r[name]-r['up'])**2)
    # Equal weight per start date keeps a batch of ten assets from counting as ten independent periods.
    dates=nonoverlapping_dates(rows)
    losses=np.asarray([np.mean(groups[d]) for d in dates])
    interval=None
    if len(dates)>=20:
        rng=np.random.default_rng(42)
        estimates=losses[rng.integers(0,len(losses),size=(2000,len(losses)))].mean(axis=1)
        interval=np.quantile(estimates,[.025,.975]).tolist()
    return dict(brier_difference=float(losses.mean()),nonoverlapping_start_dates=len(dates),
                exploratory_date_bootstrap_95=interval,lower_is_better=True)


def report(journal,asset_id=None):
    events=journal.events()  # verifies the append-only hash chain
    predictions={e['id']:e['event'] for e in events if e['event']['kind']=='prediction' and
                 (asset_id is None or e['event']['asset']['id']==asset_id)}
    outcomes={e['event']['prediction_id']:e['event'] for e in events if e['event']['kind']=='outcome'}
    cohorts=defaultdict(list)
    for identity,p in predictions.items():cohorts[(p['protocol_sha256'],p['implementation_sha256'])].append((identity,p))
    results=[]
    for (protocol,implementation),items in sorted(cohorts.items()):
        rows=[]
        for identity,p in items:
            if identity in outcomes:
                o=outcomes[identity]
                rows.append(dict(asset_id=p['asset']['id'],start=p['target_sessions'][0],end=p['target_sessions'][-1],
                                 up=o['up'],model=p['probability_up'],**p['baseline_probabilities']))
        rows.sort(key=lambda r:(r['start'],r['asset_id']))
        bins=[]
        for index,lower in enumerate((0,.2,.4,.6,.8)):
            selected=[r for r in rows if min(4,int(r['model']*5))==index]
            bins.append(dict(lower=lower,upper=round(lower+.2,1),count=len(selected),
                             mean_probability=float(np.mean([r['model'] for r in selected])) if selected else None,
                             observed_up_rate=float(np.mean([r['up'] for r in selected])) if selected else None))
        by_asset=[]
        for asset in sorted({p['asset']['id'] for _,p in items}):
            matched=[r for r in rows if r['asset_id']==asset]
            by_asset.append(dict(asset_id=asset,completed=len(matched),metrics=scores(matched,'model'),
                                 nonoverlapping_start_dates=len(nonoverlapping_dates(matched))))
        quarters=defaultdict(list)
        for row in rows:quarters[row['start'][:4]+f"-Q{(int(row['start'][5:7])-1)//3+1}"].append(row)
        by_quarter=[dict(quarter=q,completed=len(selected),model=scores(selected,'model'),
                         baselines={name:scores(selected,name) for name in BASELINES}) for q,selected in sorted(quarters.items())]
        results.append(dict(protocol_sha256=protocol,implementation_sha256=implementation,
                            predictions=len(items),completed=len(rows),pending=len(items)-len(rows),
                            period=dict(start=min((r['start'] for r in rows),default=None),end=max((r['end'] for r in rows),default=None)),
                            model=scores(rows,'model'),baselines={name:scores(rows,name) for name in BASELINES},
                            comparisons={name:comparison(rows,name) for name in BASELINES},by_asset=by_asset,by_quarter=by_quarter,calibration_bins=bins,
                            nonoverlapping_start_dates=len(nonoverlapping_dates(rows))))
    complete=sum(r['completed'] for r in results)
    return dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),asset_id=asset_id,
                predictions=len(predictions),completed=complete,pending=len(predictions)-complete,
                target='Five completed exchange sessions, close-to-close direction; excludes dividends and costs.',
                next_target_end=min((p['target_sessions'][-1] for identity,p in predictions.items() if identity not in outcomes),default=None),
                status='collecting' if complete==0 else 'preliminary',cohorts=results,promoted=False,calibrated=False,
                limitations=['Observed direction accuracy is not a probability of profit or an AI confidence score.',
                             'Parallel assets and overlapping targets are dependent. Dates are not independent market regimes.',
                             'Different implementation/protocol cohorts are never pooled.',
                             'Pooled metrics weight completed outcomes, not assets equally. Inspect asset and quarterly breakdowns.',
                             'Intervals require 20 nonoverlapping start dates and remain exploratory; serial dependence may persist.',
                             'Calibration bins describe observations; no calibration model has been fitted.',
                             'Selected current listings have survivorship bias. More outcomes and a separate review are required before promotion.'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--journal',type=Path);parser.add_argument('--asset');parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        result=report(Journal(args.journal) if args.journal else Journal(),args.asset)
        text=json.dumps(result,indent=2,allow_nan=False)
        if args.output:args.output.write_text(text+'\n',encoding='utf-8')
        else:print(text)
        return 0
    except (ValueError,KeyError,TypeError,OSError,sqlite3.Error):print('Validation unavailable: verify journal integrity. No results accepted.');return 1


if __name__=='__main__':raise SystemExit(main())

"""Fixed yearly expanding-window evaluation, using frozen audit artifact IDs."""
import hashlib
from pathlib import Path
import platform
import numpy as np
from dataset_features import FEATURE_COLUMNS
from modeling import digest, fit, predict, metrics, simulate
from research_universe import UNIVERSE


def evaluate_asset(features, source):
    if (digest(source) != features['source_id'] or features['feature_columns'] != list(FEATURE_COLUMNS)
            or features['horizon_sessions'] != 5 or features['feature_version'] != 'daily-v1'):
        raise ValueError('Incompatible frozen inputs')
    eligible = [r for r in features['rows'] if r['supervised_ready']]
    blocks = []
    for year in range(2021, 2027):
        start, end = f'{year}-01-01', f'{year}-12-31'
        test = [r for r in eligible if start <= r['session'] <= end and r['label']['end_session'] <= end]
        boundary = test[0]['session'] if test else start
        train = [r for r in eligible if r['session'] < start and r['label']['end_session'] < boundary]
        block = dict(year=year, partial=year == 2026, training_count=len(train), test_count=len(test))
        blocks.append(block)
        if len(train) < 500 or len(test) < (1 if year == 2026 else 100):
            block.update(status='unavailable', reason='Insufficient purged sample counts')
            continue
        try:
            model = fit(train)
        except ValueError:
            block.update(status='unavailable', reason='Training failed; no substituted model')
            continue
        probabilities = dict(logistic=predict(model, test), always_up=np.ones(len(test)),
                             training_prior=np.full(len(test), model['training_positive_rate']),
                             momentum=np.asarray([float(r['features']['return_5'] > 0) for r in test]))
        # Execution may not cross the evaluated calendar block.
        execution_source = dict(source, expected_sessions=[d for d in source['expected_sessions'] if d <= end])
        y = [r['label']['up'] for r in test]
        block.update(status='evaluated', model=model, model_sha256=digest(model),
                     train_sessions=[r['session'] for r in train],
                     train_target_end_sessions=[r['label']['end_session'] for r in train],
                     positive_rate=float(np.mean(y)), evaluations={})
        for name, p in probabilities.items():
            block['evaluations'][name] = dict(metrics=metrics(y, p),
                predictions=[dict(session=r['session'], label=r['label'], probability_up=float(v)) for r, v in zip(test, p)],
                illustrative_execution=simulate(execution_source, test, p))
    return dict(asset=source['asset'], source_id=digest(source), feature_id=digest(features),
                missing_sessions=source['quality']['missing_sessions'], blocks=blocks,
                limitations=features['limitations'])


def evaluate_universe(store, audit):
    entries = audit['assets']
    if [(a['asset_class'], a['symbol']) for a in entries] != list(UNIVERSE):
        raise ValueError('Audit does not match fixed universe')
    results = []
    for entry in entries:
        item = dict(symbol=entry['symbol'], asset_class=entry['asset_class'])
        if entry['status'] != 'audited':
            item.update(status='unavailable', reason=entry['status'])
        else:
            source, features = store.load(entry['snapshot_id']), store.load(entry['feature_id'])
            if source['asset'] != entry['asset']:
                raise ValueError('Audit identity mismatch')
            item.update(evaluate_asset(features, source), status='evaluated')
        results.append(item)
    summaries = []
    for year in range(2021, 2027):
        blocks = [b for a in results for b in a.get('blocks', []) if b['year'] == year and b['status'] == 'evaluated']
        summary = dict(year=year, partial=year == 2026, assets_evaluated=len(blocks), assets_expected=len(UNIVERSE), methods={})
        for name in ('logistic', 'always_up', 'training_prior', 'momentum'):
            if blocks:
                summary['methods'][name] = {metric: float(np.mean([b['evaluations'][name]['metrics'][metric] for b in blocks]))
                    if all(b['evaluations'][name]['metrics'][metric] is not None for b in blocks) else None
                    for metric in ('accuracy', 'balanced_accuracy', 'brier', 'log_loss')}
        summaries.append(summary)
    files = ('phase4_evaluation.py', 'modeling.py', 'dataset_features.py', 'analysis.py')
    root = Path(__file__).parent
    return dict(kind='yearly_universe_evaluation', schema_version=1, audit_sha256=digest(audit),
                protocol_sha256=hashlib.sha256((root/'PHASE4_NEXT_PROTOCOL.md').read_bytes()).hexdigest(),
                implementation_sha256=hashlib.sha256(b''.join((root/f).read_bytes() for f in files)).hexdigest(),
                environment=dict(python=platform.python_version(), numpy=np.__version__),
                assets=results, equal_weight_asset_summaries=summaries, promoted=False,
                limitations=['Exploratory retrospective blocks, not untouched prospective evaluation.',
                             'Known controls and current surviving universe create selection bias.',
                             'Probabilities uncalibrated; dividends excluded; execution only illustrative.',
                             'Equal-weight summaries are descriptive; assets and overlapping targets are dependent.',
                             'No threshold tuning, favorable-block selection or recommendation integration.'])

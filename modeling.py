"""Offline, fixed-protocol exploratory modeling; no provider or LLM calls."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np

from dataset_features import FEATURE_COLUMNS
from datasets import DatasetStore, canonical, valid_dates


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def split_rows(artifact):
    if (artifact.get('kind') != 'features' or artifact.get('horizon_sessions') != 5
            or artifact.get('feature_columns') != list(FEATURE_COLUMNS)):
        raise ValueError('Protocol requires eight daily features and a five-session target')
    rows = [r for r in artifact['rows'] if r['supervised_ready']]
    valid_dates([r['session'] for r in rows])
    for row in rows:
        values = [row['features'][c] for c in FEATURE_COLUMNS]
        if not np.isfinite(np.asarray(values, dtype=float)).all():
            raise ValueError('Nonfinite features')
        if row['label']['up'] not in (0, 1) or row['label']['end_session'] <= row['session']:
            raise ValueError('Invalid target')
    a, b = int(len(rows)*0.7), int(len(rows)*0.85)
    if not 0 < a < b < len(rows):
        raise ValueError('Insufficient history')
    parts = [rows[:a], rows[a:b], rows[b:]]
    for i in (0, 1):
        boundary = parts[i+1][0]['session']
        parts[i] = [r for r in parts[i] if r['label']['end_session'] < boundary]
    if any(len(p) < minimum for p, minimum in zip(parts, (100, 20, 20))):
        raise ValueError('Insufficient history after purging')
    return parts


def matrix(rows):
    return np.asarray([[r['features'][c] for c in FEATURE_COLUMNS] for r in rows], dtype=float)


def sigmoid(z):
    return np.exp(-np.logaddexp(0, -z))


def fit(rows):
    x = matrix(rows)
    y = np.asarray([r['label']['up'] for r in rows], dtype=float)
    if len(set(y)) != 2:
        raise ValueError('Training requires both outcome classes')
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1
    design = np.column_stack((np.ones(len(x)), (x-mean)/scale))
    weights = np.zeros(design.shape[1])
    penalty = np.eye(len(weights)); penalty[0, 0] = 0
    def loss(w):
        z = design @ w
        return np.sum(np.logaddexp(0, z)-y*z) + 0.5*w @ penalty @ w
    for iteration in range(100):
        p = sigmoid(design @ weights)
        gradient = design.T @ (p-y) + penalty @ weights
        if np.max(np.abs(gradient)) < 1e-8:
            break
        hessian = design.T @ ((p*(1-p))[:, None]*design) + penalty
        step = np.linalg.solve(hessian, gradient)
        rate = 1.0
        while loss(weights-rate*step) > loss(weights)-1e-4*rate*(gradient @ step):
            rate *= 0.5
            if rate < 1e-12:
                raise ValueError('Model optimization failed')
        weights -= rate*step
    else:
        raise ValueError('Model did not converge')
    return dict(mean=mean.tolist(), scale=scale.tolist(), weights=weights.tolist(),
                iterations=iteration, training_positive_rate=float(y.mean()))


def predict(model, rows):
    x = (matrix(rows)-np.asarray(model['mean']))/np.asarray(model['scale'])
    return sigmoid(np.column_stack((np.ones(len(x)), x)) @ np.asarray(model['weights']))


def metrics(y, probabilities):
    y, p = np.asarray(y), np.asarray(probabilities)
    correct = (p >= 0.5) == y
    recalls = [float(np.mean((p[y == c] >= 0.5) == c)) for c in (0, 1) if np.any(y == c)]
    rng = np.random.default_rng(42)
    starts = rng.integers(0, len(y), size=(2000, (len(y)+9)//10))
    indices = ((starts[:, :, None]+np.arange(10)) % len(y)).reshape(2000, -1)[:, :len(y)]
    interval = np.quantile(correct[indices].mean(axis=1), [0.025, 0.975]).tolist()
    clipped = np.clip(p, 1e-12, 1-1e-12)
    return dict(count=len(y), accuracy=float(correct.mean()),
        balanced_accuracy=float(np.mean(recalls)) if len(recalls) == 2 else None,
        brier=float(np.mean((p-y)**2)),
        log_loss=float(-np.mean(y*np.log(clipped)+(1-y)*np.log(1-clipped))),
        accuracy_block_bootstrap_95=interval,
        confusion={f'actual_{a}_predicted_{b}': int(np.sum((y == a) & ((p >= 0.5) == b)))
                   for a in (0, 1) for b in (0, 1)})


def simulate(source, rows, probabilities):
    sessions = source['expected_sessions']
    positions = {day: i for i, day in enumerate(sessions)}
    prices = {r['date']: r['price'] for r in source['observations']}
    trades, busy_until = [], -1
    for row, p in zip(rows, probabilities):
        signal = positions[row['session']]
        entry, end = signal+1, signal+6
        if p < 0.5 or entry <= busy_until or end >= len(sessions):
            continue
        if any(s not in prices for s in sessions[signal:end+1]):
            continue
        trades.append(dict(signal_session=row['session'], entry_session=sessions[entry],
            exit_session=sessions[end], gross_return=prices[sessions[end]]/prices[sessions[entry]]-1))
        busy_until = end
    return dict(trades=trades, trade_count=len(trades),
        compounded_return_by_round_trip_bps={str(bps): float(np.prod([
            1+t['gross_return']-bps/10000 for t in trades])-1) for bps in (0, 10, 25)})


def experiment(features, source):
    if digest(source) != features['source_id']:
        raise ValueError('Source identity mismatch')
    train, validation, test = split_rows(features)
    model = fit(train)
    result = dict(kind='baseline_evaluation', schema_version=1, feature_id=digest(features),
        source_id=digest(source), asset=source['asset'], model=model,
        protocol_sha256=hashlib.sha256(Path(__file__).with_name('PHASE4_PROTOCOL.md' if source['asset']['asset_class']=='crypto' else 'PHASE4_STOCK_PROTOCOL.md').read_bytes()).hexdigest(),
        implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        environment=dict(python=platform.python_version(), numpy=np.__version__),
        splits={name: [r['session'] for r in rows] for name, rows in
                zip(('train', 'validation', 'test'), (train, validation, test))}, evaluations={})
    for name, rows in (('validation', validation), ('test', test)):
        probabilities = dict(logistic=predict(model, rows), always_up=np.ones(len(rows)),
            training_prior=np.full(len(rows), model['training_positive_rate']),
            momentum=np.asarray([float(r['features']['return_5'] > 0) for r in rows]))
        y = [r['label']['up'] for r in rows]
        result['evaluations'][name] = {key: dict(metrics=metrics(y, p),
            predictions=[dict(session=r['session'], label=r['label'], probability_up=float(v))
                         for r, v in zip(rows, p)]) for key, p in probabilities.items()}
        if name == 'test':
            result['illustrative_execution'] = {key: simulate(source, rows, probabilities[key])
                                                for key in ('logistic', 'always_up')}
    result['limitations'] = features['limitations'] + [
        'Exploratory retrospective evaluation; overlapping targets and the available stored history only.',
        'Probabilities are uncalibrated; test results must not guide tuning.',
        'Daily-sample execution is illustrative, not a tradable-price or profit guarantee.']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feature_id')
    parser.add_argument('--store', type=Path)
    parser.add_argument('--output', type=Path, default=Path('model_reports'))
    args = parser.parse_args()
    store = DatasetStore(args.store) if args.store else DatasetStore()
    features = store.load(args.feature_id)
    report = experiment(features, store.load(features['source_id']))
    payload = canonical(report)
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / (digest(report)+'.json')
    if path.exists():
        if path.read_text(encoding='utf-8') != payload:
            raise ValueError('Existing report failed integrity verification')
    else:
        with path.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(payload)
    print(json.dumps(dict(report=str(path), test={k: v['metrics'] for k, v in
          report['evaluations']['test'].items()}), indent=2))


if __name__ == '__main__':
    main()

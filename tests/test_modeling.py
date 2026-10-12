from copy import deepcopy
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from assets import crypto_asset
from datasets import snapshot
from dataset_features import build_features
from modeling import digest, experiment, fit, metrics, predict, simulate, split_rows


def sample():
    sessions = pd.date_range('2025-01-01', periods=364).strftime('%Y-%m-%d').tolist()
    prices = 100*np.exp(np.cumsum(np.random.default_rng(12).normal(0.001, 0.02, 364)))
    source = snapshot(crypto_asset(dict(id='bitcoin', name='Bitcoin')),
        [dict(date=d, price=float(p), volume=None) for d, p in zip(sessions, prices)],
        sessions, datetime(2026, 1, 1, tzinfo=timezone.utc),
        adjustment='provider_daily_sample', price_definition='Synthetic')
    return source, build_features(source, digest(source))


def test_purge_and_counts():
    _, features = sample()
    parts = split_rows(features)
    assert list(map(len, parts)) == [222, 44, 49]
    for left, right in zip(parts, parts[1:]):
        assert max(r['label']['end_session'] for r in left) < right[0]['session']


def test_future_features_and_labels_cannot_change_fit():
    source, features = sample()
    first = experiment(features, source)
    altered = deepcopy(features)
    boundary = first['splits']['validation'][0]
    for row in altered['rows']:
        if row['session'] >= boundary and row['supervised_ready']:
            row['label']['up'] = 1-row['label']['up']
            row['features'] = {k: v*100 for k, v in row['features'].items()}
    assert experiment(altered, source)['model'] == first['model']
    assert experiment(features, source) == first


def test_fit_stationarity_and_train_only_scaling():
    _, features = sample()
    train, _, test = split_rows(features)
    model = fit(train)
    x = np.array([list(r['features'][c] for c in features['feature_columns']) for r in train])
    assert np.allclose(model['mean'], x.mean(axis=0))
    design = np.column_stack((np.ones(len(x)), (x-model['mean'])/model['scale']))
    y = np.array([r['label']['up'] for r in train])
    gradient = design.T @ (predict(model, train)-y)+np.r_[0, model['weights'][1:]]
    assert np.max(np.abs(gradient)) < 1e-7
    assert np.all((predict(model, test) > 0) & (predict(model, test) < 1))


def test_invalid_history_and_single_class():
    _, features = sample()
    short = deepcopy(features); short['rows'] = short['rows'][:100]
    with pytest.raises(ValueError, match='Insufficient'): split_rows(short)
    train, _, _ = split_rows(features)
    for r in train: r['label']['up'] = 1
    with pytest.raises(ValueError, match='both'): fit(train)


def test_known_metrics():
    result = metrics([0, 1, 1, 0], [0.1, 0.8, 0.4, 0.2])
    assert result['accuracy'] == 0.75
    assert result['balanced_accuracy'] == 0.75
    assert result['brier'] == pytest.approx(0.1125)
    assert result['confusion']['actual_1_predicted_0'] == 1
    assert metrics([1, 1], [1, 1])['balanced_accuracy'] is None


def test_execution_is_delayed_nonoverlapping_and_costed():
    source, features = sample()
    test = split_rows(features)[2]
    report = simulate(source, test, np.ones(len(test)))
    trades = report['trades']
    assert trades and all(t['entry_session'] > t['signal_session'] for t in trades)
    assert all(a['exit_session'] < b['entry_session'] for a, b in zip(trades, trades[1:]))
    returns = report['compounded_return_by_round_trip_bps']
    assert returns['0'] > returns['10'] > returns['25']
    source['observations'] = []
    assert simulate(source, test, np.ones(len(test)))['trade_count'] == 0


def test_parent_identity_is_verified():
    source, features = sample()
    source['price_definition'] = 'Changed'
    with pytest.raises(ValueError, match='identity'): experiment(features, source)

"""Causal features and separately named future labels, with gap-aware warmup."""
import math
import hashlib
from pathlib import Path
import pandas as pd
from analysis import compute_rsi_series, compute_macd
from datasets import SCHEMA_VERSION, canonical

FEATURE_VERSION = 'daily-v1'
FEATURE_COLUMNS = ('return_1', 'return_5', 'price_to_ma_7', 'price_to_ma_25',
                   'volatility_20', 'rsi_14', 'macd_to_price', 'macd_histogram_to_price')


def build_features(source, source_id, *, horizon=5, benchmark=None, benchmark_id=None):
    if source.get('kind') != 'snapshot' or source.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('A supported snapshot is required')
    if hashlib.sha256(canonical(source).encode('utf-8')).hexdigest() != source_id:
        raise ValueError('Snapshot ID does not match source content')
    if type(horizon) is not int or not 1 <= horizon <= 30:
        raise ValueError('Horizon must be 1 to 30 sessions')
    # Reindex to the expected calendar: missing bars break BOTH features and labels.
    sessions = source['expected_sessions']
    observed = {r['date']: r['price'] for r in source['observations']}
    rows, segment = [], []

    def finish_segment():
        if not segment:
            return
        prices = pd.Series([observed[d] for d in segment], dtype=float)
        returns = prices.pct_change(fill_method=None)
        macd, _, hist = compute_macd(prices)
        values = dict(return_1=returns, return_5=prices.pct_change(5, fill_method=None),
            price_to_ma_7=prices / prices.rolling(7).mean() - 1,
            price_to_ma_25=prices / prices.rolling(25).mean() - 1,
            volatility_20=returns.rolling(20).std(ddof=1), rsi_14=compute_rsi_series(prices),
            macd_to_price=macd / prices, macd_histogram_to_price=hist / prices)
        for i, day in enumerate(segment):
            features = {name: float(series.iloc[i]) if math.isfinite(series.iloc[i]) else None for name, series in values.items()}
            ready = i >= 34 and all(v is not None for v in features.values())
            end = i + horizon
            label = None
            if end < len(segment):
                future_return = float(prices.iloc[end] / prices.iloc[i] - 1)
                if math.isfinite(future_return):
                    label = dict(end_session=segment[end], forward_return=future_return, up=int(future_return > 0))
            rows.append(dict(session=day, features=features, feature_ready=ready, label=label,
                             supervised_ready=ready and label is not None))
        segment.clear()

    for day in sessions:
        if day not in observed:
            finish_segment()
        else:
            segment.append(day)
    finish_segment()
    columns = list(FEATURE_COLUMNS)
    if benchmark is not None:
        if benchmark['asset']['currency'] != source['asset']['currency'] or benchmark['asset']['timezone'] != source['asset']['timezone'] or benchmark['adjustment'] != source['adjustment']:
            raise ValueError('Benchmark currency, session timezone and adjustment must match')
        context = build_features(benchmark, benchmark_id, horizon=horizon)
        lookup = {r['session']: r for r in context['rows']}
        columns += ['benchmark_return_5', 'relative_return_5']
        for row in rows:
            other = lookup.get(row['session'])
            value = other['features']['return_5'] if other and other['feature_ready'] else None
            own = row['features']['return_5']
            row['features']['benchmark_return_5'] = value
            relative = None if value is None or own is None else own - value
            row['features']['relative_return_5'] = relative if relative is None or math.isfinite(relative) else None
            row['feature_ready'] = row['feature_ready'] and value is not None and row['features']['relative_return_5'] is not None
            row['supervised_ready'] = row['feature_ready'] and row['label'] is not None
    # Changes to indicator implementation produce a new derived artifact identity.
    implementation = hashlib.sha256(Path(__file__).read_bytes() + Path(__file__).with_name('analysis.py').read_bytes()).hexdigest()
    return dict(kind='features', schema_version=SCHEMA_VERSION, source_id=source_id,
        benchmark_id=benchmark_id if benchmark is not None else None, implementation_sha256=implementation,
        feature_version=FEATURE_VERSION, pandas_version=pd.__version__, horizon_sessions=horizon,
        feature_columns=columns, rows=rows,
        feature_timing='Uses the current completed observation and previous observations only; decisions must occur afterward.',
        label_definition='Price at session t+h divided by price at t, minus one; up means strictly positive. Research target, not executable strategy return.',
        quality=dict(observations=len(rows), feature_ready=sum(r['feature_ready'] for r in rows),
                     supervised_ready=sum(r['supervised_ready'] for r in rows), missing_sessions=source['quality']['missing_sessions']),
        limitations=source['limitations'] + ['No scaler is fitted. Train-only preprocessing, chronological splits and label-boundary purging belong to Phase 4.',
            '35 consecutive observations required after each gap; no filling or future-confirmed swing features.',
            'Benchmark context is optional and matched by session date without forward filling; no news, fundamentals or historical publication-time data.'])

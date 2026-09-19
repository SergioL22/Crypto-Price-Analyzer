"""Offline coverage for evidence integrity, model failures, and CLI integration."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest
import requests
from typer.testing import CliRunner

import analysis
import api
import data
import llm
import recommendations as rec
import ui


@pytest.fixture
def history():
    return pd.DataFrame({'date': pd.date_range(end=pd.Timestamp.now(tz='UTC').normalize(), periods=91),
                         'price': [100 + i for i in range(91)], 'volume': [1000] * 91})


@pytest.fixture
def evidence(history):
    return rec.build_evidence('bitcoin', history, days=90)


@pytest.fixture
def decision():
    return {'action': 'HOLD', 'confidence': 'low', 'confidence_explanation': 'Few closed trades.',
            'summary': 'Wait for stronger evidence.',
            'reasons': [{'evidence_keys': ['indicators.rsi_14'], 'explanation': 'RSI is elevated.'}],
            'risks': [{'evidence_keys': ['limitations'], 'explanation': 'Momentum can reverse.'}]}


def test_evidence_uses_requested_window_and_is_json_safe(history, monkeypatch):
    original = history.copy(deep=True)
    called = []
    backtest = analysis.backtest_dataframe
    def capture(frame, coin_id, **kwargs):
        called.append(frame.copy())
        return backtest(frame, coin_id, **kwargs)
    monkeypatch.setattr(analysis, 'backtest_dataframe', capture)
    result = rec.build_evidence('bitcoin', history, days=40)
    assert result['window']['observations'] == 40
    assert len(called[0]) == 40
    assert result['indicators']['rsi_14'] == analysis.compute_rsi(called[0]['price'])
    assert result['backtest']['win_rate_pct'] is None
    assert result['backtest']['average_closed_trade_return_pct'] is None
    json.dumps(result, allow_nan=False)
    pd.testing.assert_frame_equal(history, original)


def test_portfolio_only_includes_selected_coin(history):
    portfolio = {'bitcoin': {'amount': 2, 'avg_buy_price': 100},
                 'private-other-coin': {'amount': 98765, 'avg_buy_price': 1}}
    result = rec.build_evidence('bitcoin', history, portfolio=portfolio, live_price=200)
    assert result['portfolio']['unrealized_pnl_usd'] == 200
    assert result['portfolio']['value_usd'] == 400
    assert 'private-other-coin' not in json.dumps(result)
    assert rec.build_evidence('bitcoin', history)['portfolio'] == {'included': False}


@pytest.mark.parametrize('bad', [0, -10, float('nan'), float('inf'), 'invalid', True])
def test_invalid_prices_are_rejected(history, bad):
    history['price'] = history['price'].astype(object)
    history.loc[90, 'price'] = bad
    with pytest.raises(rec.RecommendationError, match='price'):
        rec.build_evidence('bitcoin', history)


@pytest.mark.parametrize('case', ['short', 'stale', 'duplicate', 'no_dates'])
def test_unusable_history_is_rejected(history, case):
    if case == 'short': history = history.tail(10)
    if case == 'stale': history['date'] -= pd.Timedelta(days=5)
    if case == 'duplicate': history.loc[90, 'date'] = history.loc[89, 'date']
    if case == 'no_dates': history = history.drop(columns=['date'])
    with pytest.raises(rec.RecommendationError):
        rec.build_evidence('bitcoin', history)


def test_missing_dates_and_volume_are_disclosed(history):
    result = rec.build_evidence('bitcoin', history.drop(index=[20, 21]).drop(columns='volume'))
    assert result['window']['missing_days'] == 2
    assert result['indicators']['average_volume_20'] is None
    assert any('missing' in text for text in result['limitations'])


class Response:
    def __init__(self, body, status=200):
        self.body, self.status_code, self.closed = body, status, False
    def json(self):
        if isinstance(self.body, Exception): raise self.body
        return self.body
    def close(self): self.closed = True


def envelope(decision):
    return {'status': 'completed', 'output': [
        {'type': 'reasoning', 'summary': []},
        {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(decision)}]}]}


def test_openai_contract_and_result_validation(evidence, decision):
    response = Response(envelope(decision))
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return response
    provider = llm.OpenAIRecommender('test-secret', 'configured-model', post=post)
    assert provider.recommend(evidence) == decision
    url, kwargs = calls[0]
    assert url == 'https://api.openai.com/v1/responses'
    payload = kwargs['json']
    assert payload['model'] == 'configured-model'
    assert payload['store'] is False
    assert payload['text']['format']['strict'] is True
    assert json.loads(payload['input'][0]['content']) == evidence
    assert kwargs['timeout'] == (10, 60)
    assert kwargs['allow_redirects'] is False
    assert response.closed


@pytest.mark.parametrize('status', [400, 401, 403, 404, 429, 500, 302])
def test_http_errors_are_safe_and_not_retried(evidence, status):
    response = Response({'error': 'test-secret'}, status)
    calls = []
    def post(*args, **kwargs):
        calls.append(1)
        return response
    with pytest.raises(rec.RecommendationError) as error:
        llm.OpenAIRecommender('test-secret', 'model', post=post).recommend(evidence)
    assert 'test-secret' not in str(error.value)
    assert len(calls) == 1
    assert response.closed


@pytest.mark.parametrize('exception', [requests.Timeout('test-secret'), requests.ConnectionError('test-secret')])
def test_network_errors_do_not_expose_credentials(evidence, exception):
    def fail(*args, **kwargs): raise exception
    with pytest.raises(rec.RecommendationError) as error:
        llm.OpenAIRecommender('test-secret', 'model', post=fail).recommend(evidence)
    assert 'test-secret' not in str(error.value)


@pytest.mark.parametrize('body', [
    {'status': 'incomplete', 'output': []},
    {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]},
    {'status': 'completed', 'output': []},
    {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'not json'}]}]},
    {'status': 'completed', 'output': [None]},
    {'status': 'completed', 'output': [{'type': 'message', 'content': None}]},
    ValueError('invalid json'),
])
def test_incomplete_refused_and_malformed_outputs_are_rejected(evidence, body):
    with pytest.raises(rec.RecommendationError):
        llm.OpenAIRecommender('key', 'model', post=lambda *a, **k: Response(body)).recommend(evidence)


@pytest.mark.parametrize('change', [
    {'action': 'STRONG BUY'}, {'confidence': 0.9}, {'risks': []}, {'summary': '\x1b[2J'},
    {'reasons': [{'evidence_keys': ['invented.metric'], 'explanation': 'invented'}]},
])
def test_invalid_decisions_are_rejected(evidence, decision, change):
    decision.update(change)
    with pytest.raises(rec.RecommendationError): rec.validate_recommendation(decision, evidence)


def test_missing_configuration(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(rec.RecommendationError, match='OPENAI_API_KEY'):
        llm.OpenAIRecommender.from_environment()
    monkeypatch.setenv('OPENAI_API_KEY', 'test-secret')
    monkeypatch.delenv('OPENAI_MODEL', raising=False)
    with pytest.raises(rec.RecommendationError, match='OPENAI_MODEL'):
        llm.OpenAIRecommender.from_environment()


@pytest.fixture
def cli(history, tmp_path, monkeypatch):
    monkeypatch.setattr(data, 'DB_FILE', str(tmp_path / 'test.db'))
    monkeypatch.setattr(data, 'PORTFOLIO_FILE', str(tmp_path / 'portfolio.json'))
    monkeypatch.setattr(api, 'fetch_history', lambda *args: history)
    return CliRunner()


def test_evidence_only_does_not_call_openai_or_read_excluded_portfolio(cli, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('Unexpected IO')
    monkeypatch.setattr(llm.requests, 'post', forbidden)
    monkeypatch.setattr(data, 'load_portfolio', forbidden)
    result = cli.invoke(ui.app, ['recommend', 'bitcoin', '--evidence-only', '--no-portfolio'])
    assert result.exit_code == 0, result.output
    assert 'indicators.rsi_14' in result.output
    assert 'no request sent to OpenAI' in result.output


def test_cli_keeps_evidence_on_ai_failure(cli, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    result = cli.invoke(ui.app, ['recommend', 'bitcoin'])
    assert result.exit_code == 1
    assert 'indicators.rsi_14' in result.output
    assert 'AI recommendation unavailable' in result.output
    assert 'AI assessment:' not in result.output


def test_cli_displays_validated_recommendation(cli, monkeypatch, decision):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-secret')
    monkeypatch.setenv('OPENAI_MODEL', 'test-model')
    monkeypatch.setattr(llm.requests, 'post', lambda *a, **k: Response(envelope(decision)))
    result = cli.invoke(ui.app, ['recommend', 'bitcoin'])
    assert result.exit_code == 0, result.output
    assert 'AI assessment: HOLD' in result.output
    assert 'not a probability of profit' in result.output
    assert 'test-secret' not in result.output

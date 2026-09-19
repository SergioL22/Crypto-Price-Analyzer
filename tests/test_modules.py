"""Integration checks for reusable modules and the preserved CLI entry point."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pandas as pd
import pytest
from typer.testing import CliRunner

import analysis
import api
import data
import ui
from main import app


def test_core_imports_without_terminal_or_chart_libraries(tmp_path):
    root = str(Path(__file__).resolve().parents[1])
    script = """
import sys
class NoPresentationImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'ui', 'typer', 'colorama', 'matplotlib', 'mplfinance', 'plotly'}:
            raise AssertionError('Presentation dependency: ' + fullname)
sys.meta_path.insert(0, NoPresentationImports())
import api, data, analysis
"""
    result = subprocess.run([sys.executable, '-c', script], cwd=tmp_path,
                            env={**os.environ, 'PYTHONPATH': root, 'PYTHONDONTWRITEBYTECODE': '1'},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


def test_fetch_history_normalizes_and_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(data, 'DB_FILE', str(tmp_path / 'history.db'))
    data.init_database()
    timestamp = int(pd.Timestamp.now(tz='UTC').normalize().timestamp() * 1000)
    calls = []
    def fake_get(endpoint, params):
        calls.append((endpoint, params))
        return {'prices': [[timestamp, 100], [timestamp + 3600000, 105]],
                'total_volumes': [[timestamp, 200], [timestamp + 3600000, 250]]}
    monkeypatch.setattr(api, '_get', fake_get)
    frame = api.fetch_history('bitcoin', 90)
    assert calls[0][1]['days'] == 90
    assert frame['price'].tolist() == [105]
    stored = data.load_price_data('bitcoin', 90)
    assert stored['price'].tolist() == [105]
    assert stored['volume'].tolist() == [250]


def test_backtest_calculation_is_independent_of_storage_and_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Backtest calculation performed IO')
    monkeypatch.setattr(api, 'fetch_history', forbidden)
    monkeypatch.setattr(data, 'load_price_data', forbidden)
    monkeypatch.setattr(data, 'save_backtest_result', forbidden)
    prices = list(range(100, 60, -1)) + list(range(65, 120))
    frame = pd.DataFrame({'price': prices}, index=pd.date_range('2026-01-01', periods=len(prices)))
    original = frame.copy(deep=True)
    result = analysis.backtest_dataframe(frame, 'bitcoin', days=95)
    assert result['total_trades'] == 1
    assert result['trades'][0]['type'] == 'BUY'
    assert result['trades'][1]['type'] == 'SELL'
    assert result['period_days'] == 95
    assert result['win_rate'] == 100
    pd.testing.assert_frame_equal(frame, original)


def test_backtest_service_saves_the_calculated_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(data, 'DB_FILE', str(tmp_path / 'backtest.db'))
    data.init_database()
    frame = pd.DataFrame({'price': range(100, 140)}, index=pd.date_range(end=pd.Timestamp.now(tz='UTC').normalize(), periods=40))
    monkeypatch.setattr(api, 'fetch_history', lambda *args: frame)
    monkeypatch.setattr(data, 'load_price_data', lambda *args: frame)
    result = analysis.backtest_strategy('bitcoin', 'rsi_ma', 40)
    assert result.pop('window')['complete'] is True
    assert result == analysis.backtest_dataframe(frame, 'bitcoin', days=40)
    with sqlite3.connect(data.DB_FILE) as conn:
        row = conn.execute('SELECT coin_id, period_days, total_trades FROM backtest_results').fetchone()
    assert row == ('bitcoin', 40, 0)


def test_cli_help_has_no_market_or_storage_side_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('CLI help performed IO')
    monkeypatch.setattr(data, 'init_database', forbidden)
    monkeypatch.setattr(api, 'fetch_top10', forbidden)
    result = CliRunner().invoke(app, ['--help'])
    assert result.exit_code == 0, result.output
    for command in ('prices', 'history', 'signals', 'technical', 'portfolio', 'edit-portfolio',
                    'setup-alert', 'alerts', 'backtest', 'charts'):
        assert command in result.output


def test_interactive_startup_recovers_from_api_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(data, 'DB_FILE', str(tmp_path / 'cli.db'))
    def unavailable():
        raise RuntimeError('offline')
    monkeypatch.setattr(api, 'fetch_top10', unavailable)
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 0
    assert 'Could not load market data: offline' in result.output


@pytest.mark.parametrize('command', ['prices', 'history', 'signals', 'technical', 'portfolio'])
def test_cli_analysis_commands_use_the_extracted_modules(command, tmp_path, monkeypatch):
    monkeypatch.setattr(data, 'DB_FILE', str(tmp_path / 'cli.db'))
    monkeypatch.setattr(data, 'PORTFOLIO_FILE', str(tmp_path / 'portfolio.json'))
    monkeypatch.setattr(ui.time, 'sleep', lambda _: None)
    coin = {'id': 'bitcoin', 'symbol': 'btc', 'name': 'Bitcoin', 'current_price': 100,
            'market_cap_rank': 1, 'market_cap': 100000, 'total_volume': 1000,
            'price_change_percentage_1h_in_currency': 1,
            'price_change_percentage_24h_in_currency': 2,
            'price_change_percentage_7d_in_currency': 3}
    monkeypatch.setattr(api, 'fetch_top10', lambda: [coin])
    monkeypatch.setattr(api, 'fetch_history', lambda coin_id, days: pd.DataFrame({
        'date': pd.date_range('2026-01-01', periods=days),
        'price': range(100, 100 + days), 'volume': [1000] * days}))
    result = CliRunner().invoke(app, [command], input='1\n')
    assert result.exit_code == 0, (result.output, result.exception)
    assert 'Traceback' not in result.output

import os
import pytest
from local_config import load_local_config


def test_loads_literals_without_expansion_or_environment_override(tmp_path, monkeypatch):
    path = tmp_path / '.env'
    path.write_text('# comment\nTWELVE_DATA_API_KEY="local-placeholder"\nOPENAI_API_KEY=literal-${HOME}\nOPENAI_MODEL=chosen-model\nPATH=do-not-load\n', encoding='utf-8-sig')
    monkeypatch.setenv('TWELVE_DATA_API_KEY', 'terminal-placeholder')
    before = os.environ.get('PATH')
    load_local_config(path)
    assert os.environ['TWELVE_DATA_API_KEY'] == 'terminal-placeholder'
    assert os.environ['OPENAI_API_KEY'] == 'literal-${HOME}'
    assert os.environ['OPENAI_MODEL'] == 'chosen-model'
    assert os.environ.get('PATH') == before


def test_missing_file_and_blank_keys_are_optional(tmp_path):
    load_local_config(tmp_path / 'absent')
    path = tmp_path / '.env'
    path.write_text('TWELVE_DATA_API_KEY=\n', encoding='utf-8')
    load_local_config(path)
    assert 'TWELVE_DATA_API_KEY' not in os.environ


def test_bad_config_does_not_echo_secret_or_partially_load(tmp_path):
    path = tmp_path / '.env'
    path.write_text('OPENAI_MODEL=test\nTWELVE_DATA_API_KEY="private-placeholder\n', encoding='utf-8')
    with pytest.raises(ValueError) as error:
        load_local_config(path)
    assert 'private-placeholder' not in str(error.value)
    assert 'OPENAI_MODEL' not in os.environ


def test_backend_loads_project_config_from_another_working_directory(tmp_path, monkeypatch):
    from backend import create_app
    (tmp_path / '.env').write_text('TWELVE_DATA_API_KEY=local-placeholder\n', encoding='utf-8')
    other = tmp_path / 'other'
    other.mkdir()
    monkeypatch.chdir(other)
    create_app()
    assert os.environ['TWELVE_DATA_API_KEY'] == 'local-placeholder'


def test_explicit_empty_environment_wins(tmp_path, monkeypatch):
    path = tmp_path / '.env'
    path.write_text('TWELVE_DATA_API_KEY=local-placeholder\n', encoding='utf-8')
    monkeypatch.setenv('TWELVE_DATA_API_KEY', '')
    load_local_config(path)
    assert os.environ['TWELVE_DATA_API_KEY'] == ''


def test_optional_finnhub_key_is_literal_and_existing_environment_wins(tmp_path,monkeypatch):
    monkeypatch.delenv('FINNHUB_API_KEY',raising=False)
    path=tmp_path/'.env';path.write_text('FINNHUB_API_KEY=profile-placeholder\n',encoding='utf-8')
    load_local_config(path);assert os.environ['FINNHUB_API_KEY']=='profile-placeholder'
    monkeypatch.setenv('FINNHUB_API_KEY','terminal-placeholder')
    load_local_config(path);assert os.environ['FINNHUB_API_KEY']=='terminal-placeholder'

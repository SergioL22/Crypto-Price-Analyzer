"""Suite-wide isolation from live HTTP providers."""
import pytest
import requests


@pytest.fixture(autouse=True)
def block_live_provider_requests(monkeypatch):
    """Mocks remain usable, but accidentally unmocked requests fail immediately."""
    def blocked(*args, **kwargs):
        raise AssertionError('Live HTTP is disabled in tests; inject a fake provider response.')
    monkeypatch.setattr(requests.sessions.Session, 'request', blocked)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_MODEL', raising=False)
    monkeypatch.delenv('CRYPTO_ORIGIN', raising=False)

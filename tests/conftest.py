"""Suite-wide isolation from live HTTP providers."""
import pytest
import requests
import httpx


@pytest.fixture(autouse=True)
def block_live_provider_requests(monkeypatch, tmp_path):
    """Mocks remain usable, but accidentally unmocked requests fail immediately."""
    def blocked(*args, **kwargs):
        raise AssertionError('Live HTTP is disabled in tests; inject a fake provider response.')
    monkeypatch.setattr(requests.sessions.Session, 'request', blocked)
    original_send=httpx.AsyncClient.send
    async def offline_async_send(client,*args,**kwargs):
        if not isinstance(client._transport,(httpx.MockTransport,httpx.ASGITransport)):
            raise AssertionError('Live identity HTTP is disabled in tests; inject a mock transport.')
        return await original_send(client,*args,**kwargs)
    monkeypatch.setattr(httpx.AsyncClient,'send',offline_async_send)
    import local_config
    monkeypatch.setattr(local_config, 'DEFAULT_ENV_PATH', tmp_path / '.env')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('TWELVE_DATA_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_MODEL', raising=False)
    monkeypatch.delenv('CRYPTO_ORIGIN', raising=False)

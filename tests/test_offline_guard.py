"""Ensure the shared provider guard fails before any real HTTP request."""
import pytest
import requests


def test_live_provider_requests_are_blocked():
    with pytest.raises(AssertionError, match='Live HTTP is disabled'):
        requests.get('https://example.invalid', timeout=1)

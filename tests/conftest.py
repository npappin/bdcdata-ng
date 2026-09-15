"""Shared fixtures.

Everything here runs offline. No test in this suite may touch the network or
require real credentials -- ``responses`` intercepts every request, and any
unmatched call fails loudly rather than escaping to the FCC.
"""

from __future__ import annotations

import pytest
import responses

import bdcdata
from bdcdata import catalog, credentials
from bdcdata._client import reset_session


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Give every test a clean, credentialed, network-free environment."""
    # Known-good credentials so tests exercise behavior, not the auth error.
    monkeypatch.setenv("BDC_USERNAME", "tester@example.com")
    monkeypatch.setenv("BDC_API_KEY", "test-token")
    monkeypatch.delenv("BDC_BASE_URL", raising=False)

    # Never let a stray .env in the working directory leak into a test.
    monkeypatch.chdir(tmp_path)

    credentials.clear_credentials()
    catalog.clear_release_cache()
    bdcdata.set_base_url(None)
    bdcdata.set_cache(False, path=tmp_path / "cache")
    reset_session()

    # Neutralize the 10-calls-per-minute pacing. It works (TestRateLimiter
    # builds its own _RateLimiter to prove it), but a test that downloads 60
    # files would otherwise sleep for six real minutes.
    monkeypatch.setattr("bdcdata._client._limiter.acquire", lambda: None)

    yield

    credentials.clear_credentials()
    catalog.clear_release_cache()
    reset_session()


@pytest.fixture
def no_credentials(monkeypatch):
    """Remove every source of credentials."""
    monkeypatch.delenv("BDC_USERNAME", raising=False)
    monkeypatch.delenv("BDC_API_KEY", raising=False)
    credentials.clear_credentials()


@pytest.fixture
def mock_api():
    """Intercept all HTTP. Unregistered URLs raise ConnectionError."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


@pytest.fixture
def no_backoff(monkeypatch):
    """Make retry backoff instant so retry tests stay fast."""
    monkeypatch.setattr("bdcdata._client.time.sleep", lambda _seconds: None)

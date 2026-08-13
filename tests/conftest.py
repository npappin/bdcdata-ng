"""Shared fixtures.

Everything here runs offline. No test in this suite may touch the network or
require real credentials -- ``responses`` intercepts every request, and any
unmatched call fails loudly rather than escaping to the FCC.
"""

from __future__ import annotations

import io
import zipfile

import pytest
import responses

import bdcdata
from bdcdata import catalog, credentials
from bdcdata._client import reset_session

BASE_URL = "https://bdc.fcc.gov"


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


def make_csv_zip(csv_text: str, name: str = "data.csv", extra: dict[str, str] | None = None) -> bytes:
    """Build a ZIP archive containing a CSV, the way the FCC ships them."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, csv_text)
        for extra_name, extra_text in (extra or {}).items():
            archive.writestr(extra_name, extra_text)
    return buffer.getvalue()


def api_payload(data: list[dict], **extra) -> dict:
    """Wrap rows the way every BDC list endpoint does."""
    return {
        "data": data,
        "result_count": len(data),
        "status_code": 200,
        "message": None,
        "status": "successful",
        **extra,
    }


# A realistic fixed-availability CSV: leading zeros in frn and block_geoid, a
# 13-digit location_id, and a null speed.
FIXED_AVAILABILITY_CSV = (
    "frn,provider_id,brand_name,location_id,technology,"
    "max_advertised_download_speed,max_advertised_upload_speed,low_latency,"
    "business_residential_code,state_usps,block_geoid,h3_res8_id\n"
    "0032176356,999100,Acme Telecom,1357135307,50,1000,1000,1,X,WA,"
    "530330001001000,882aa8458dfffff\n"
    "0000000123,999200,Beta Broadband,9999999999999,50,500,,0,R,WA,"
    "530330001001001,882aa8458dfffff\n"
)

SERVED_UNSERVED_CSV = (
    "location_id,block_geoid,h3_res8_id,any_dl100_ul20,wired_dl100_ul20,"
    "terrestrial_dl100_ul20\n"
    "1357135307,530330001001000,882aa8458dfffff,1,1,1\n"
    "9999999999999,530330001001001,882aa8458dfffff,0,0,1\n"
)

CHALLENGE_CSV = (
    "challenge_id,fabric_vintage,category_code,category_code_desc,location_id,location_state\n"
    "9998374,2022-06-30,1,Missing Broadband Serviceable Location,1357135307,WA\n"
)

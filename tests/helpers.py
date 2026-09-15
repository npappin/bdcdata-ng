"""Test fixtures data and builders, importable from any test module."""

from __future__ import annotations

import io
import zipfile

BASE_URL = "https://bdc.fcc.gov"

AS_OF_DATES_URL = f"{BASE_URL}/api/public/map/listAsOfDates"
AVAILABILITY_LIST_URL = f"{BASE_URL}/api/public/map/downloads/listAvailabilityData"
CHALLENGE_LIST_URL = f"{BASE_URL}/api/public/map/downloads/listChallengeData"
FUNDING_LIST_URL = f"{BASE_URL}/api/public/fundingmap/downloads/listFundingData"
MAP_DOWNLOAD_URL = f"{BASE_URL}/api/public/map/downloads/downloadFile"
FUNDING_DOWNLOAD_URL = f"{BASE_URL}/api/public/fundingmap/downloads/downloadFile"


def make_csv_zip(
    csv_text: str, name: str = "data.csv", extra: dict[str, str] | None = None
) -> bytes:
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


def as_of_dates(availability: list[str], challenge: list[str] | None = None) -> dict:
    rows = [{"data_type": "availability", "as_of_date": d} for d in availability]
    rows += [{"data_type": "challenge", "as_of_date": d} for d in (challenge or [])]
    return api_payload(rows)


# A realistic fixed-availability CSV: leading zeros in frn and block_geoid, a
# 13-digit location_id, and a missing upload speed.
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

UNSERVED_UNFUNDED_CSV = (
    "location_id,block_geoid,h3_res8_id,building_type_code\n"
    "1357135307,530330001001000,882aa8458dfffff,R\n"
)


def availability_file_row(
    file_id: int,
    state_fips: str,
    technology_code: str = "50",
    subcategory: str = "Location Coverage",
    category: str = "State",
    technology_type: str = "Fixed Broadband",
    record_count: str = "2",
) -> dict:
    """One row shaped like listAvailabilityData returns."""
    return {
        "file_id": file_id,
        "category": category,
        "subcategory": subcategory,
        "technology_type": technology_type,
        "technology_code": technology_code,
        "technology_code_desc": "Fiber to the Premises",
        "speed_tier": None,
        "state_fips": state_fips,
        "state_name": "Washington",
        "provider_id": None,
        "provider_name": None,
        "file_type": "csv",
        "file_name": f"bdc_{state_fips}_fiber_fixed_broadband_J24",
        "record_count": record_count,
    }


def challenge_file_row(file_id: int, state_fips: str, category: str) -> dict:
    """One row shaped like listChallengeData returns."""
    return {
        "file_id": file_id,
        "category": category,
        "state_fips": state_fips,
        "state_name": "Washington",
        "record_count": "1",
    }

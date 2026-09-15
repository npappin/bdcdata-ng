"""Challenge category mapping and downloads."""

from __future__ import annotations

import pytest
import responses

import bdcdata
from bdcdata.challenges import _resolve_category
from helpers import (
    AS_OF_DATES_URL,
    CHALLENGE_CSV,
    CHALLENGE_LIST_URL,
    MAP_DOWNLOAD_URL,
    api_payload,
    as_of_dates,
    challenge_file_row,
    make_csv_zip,
)


class TestCategoryResolution:
    @pytest.mark.parametrize(
        ("kind", "status", "expected"),
        [
            ("fabric", "in_progress", "Fabric Challenge - In Progress"),
            ("fabric", "resolved", "Fabric Challenge - Resolved"),
            ("fixed", "in_progress", "Fixed Challenge - In Progress"),
            ("fixed", "resolved", "Fixed Challenge - Resolved"),
            ("fixed", "cumulative", "Fixed Challenge - Cumulative"),
            ("mobile", "in_progress", "Mobile Challenge - In Progress"),
            ("mobile_audit", "resolved", "Mobile Audit - Resolved"),
            ("fixed_verification", "in_progress", "Fixed Verification - In Progress"),
            ("mobile_verification", "resolved", "Mobile Verification - Resolved"),
        ],
    )
    def test_maps_to_exact_api_strings(self, kind, status, expected):
        assert _resolve_category(kind, status) == expected

    @pytest.mark.parametrize(
        "spelling", ["in progress", "in-progress", "IN_PROGRESS", "open", "pending"]
    )
    def test_status_aliases(self, spelling):
        assert _resolve_category("fabric", spelling) == "Fabric Challenge - In Progress"

    def test_unavailable_status_lists_what_works(self):
        with pytest.raises(ValueError) as excinfo:
            _resolve_category("fabric", "cumulative")

        message = str(excinfo.value)
        assert "not available for fabric" in message
        assert "in_progress" in message

    def test_unknown_kind_lists_the_kinds(self):
        with pytest.raises(ValueError, match="is not a challenge kind"):
            _resolve_category("nonsense", "resolved")


class TestDownload:
    @pytest.fixture
    def fabric_wa(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates([], ["2025-02-28"]))
        mock_api.add(
            responses.GET,
            f"{CHALLENGE_LIST_URL}/2025-02-28",
            json=api_payload([challenge_file_row(5779, "53", "Fabric Challenge - In Progress")]),
        )
        mock_api.add(
            responses.GET,
            f"{MAP_DOWNLOAD_URL}/challenge/5779",
            body=make_csv_zip(CHALLENGE_CSV),
            status=200,
        )
        return mock_api

    def test_fabric_challenges_download(self, fabric_wa):
        df = bdcdata.challenges.fabric(state="WA")

        assert len(df) == 1
        assert df["challenge_id"].iloc[0] == 9998374

    def test_uses_the_challenge_data_type_in_the_path(self, fabric_wa):
        # v1 hardcoded "availability" here, so challenge files were unreachable.
        bdcdata.challenges.fabric(state="WA")

        assert fabric_wa.calls[-1].request.url.endswith("/downloadFile/challenge/5779")

    def test_stamps_category_and_state(self, fabric_wa):
        df = bdcdata.challenges.fabric(state="WA")

        assert df["category"].iloc[0] == "Fabric Challenge - In Progress"
        assert df["state_fips"].iloc[0] == "53"
        assert df["release"].iloc[0] == "2025-02-28"

    def test_location_id_stays_a_string_for_joining(self, fabric_wa):
        # The challenge spec calls this Integer and the availability spec calls
        # it String; it is a string in both here so the two can be joined.
        df = bdcdata.challenges.fabric(state="WA")

        assert df["location_id"].iloc[0] == "1357135307"

    def test_dates_are_parsed(self, fabric_wa):
        import pandas as pd

        df = bdcdata.challenges.fabric(state="WA")

        assert df["fabric_vintage"].iloc[0] == pd.Timestamp("2022-06-30")

    def test_latest_resolves_against_the_challenge_series(self, mock_api):
        # Challenge files are published monthly and run ahead of availability.
        mock_api.add(
            responses.GET,
            AS_OF_DATES_URL,
            json=as_of_dates(["2024-06-30"], ["2025-01-31", "2025-02-28"]),
        )
        mock_api.add(responses.GET, f"{CHALLENGE_LIST_URL}/2025-02-28", json=api_payload([]))

        bdcdata.challenges.fabric(state="WA")

        assert "/2025-02-28" in mock_api.calls[-1].request.url

    def test_get_accepts_an_arbitrary_category(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates([], ["2025-02-28"]))
        mock_api.add(responses.GET, f"{CHALLENGE_LIST_URL}/2025-02-28", json=api_payload([]))

        # The escape hatch for categories the FCC adds after this release.
        bdcdata.challenges.get("Some Future Category - In Progress", state="WA")

        assert "Some+Future+Category" in mock_api.calls[-1].request.url

    def test_empty_result_warns_and_returns_empty(self, mock_api, caplog):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates([], ["2025-02-28"]))
        mock_api.add(responses.GET, f"{CHALLENGE_LIST_URL}/2025-02-28", json=api_payload([]))

        with caplog.at_level("WARNING", logger="bdcdata"):
            df = bdcdata.challenges.mobile(state="WA")

        assert df.empty
        assert "No challenge files published" in caplog.text


class TestVerificationAndAudit:
    def test_verification_requires_a_valid_kind(self):
        with pytest.raises(ValueError, match="kind must be"):
            bdcdata.challenges.verification(kind="fabric")

    def test_audit_is_mobile_only(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates([], ["2025-02-28"]))
        mock_api.add(responses.GET, f"{CHALLENGE_LIST_URL}/2025-02-28", json=api_payload([]))

        bdcdata.challenges.audit(state="WA", status="resolved")

        assert "Mobile+Audit+-+Resolved" in mock_api.calls[-1].request.url

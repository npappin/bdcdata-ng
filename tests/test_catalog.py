"""Catalog wrappers and release resolution."""

from __future__ import annotations

import pytest
import responses

from bdcdata import catalog
from helpers import (
    AS_OF_DATES_URL,
    AVAILABILITY_LIST_URL,
    CHALLENGE_LIST_URL,
    FUNDING_LIST_URL,
    api_payload,
    as_of_dates,
    availability_file_row,
    challenge_file_row,
)


class TestReleases:
    def test_returns_rows(self, mock_api):
        mock_api.add(
            responses.GET,
            AS_OF_DATES_URL,
            json=as_of_dates(["2023-12-31", "2024-06-30"], ["2025-02-28"]),
        )

        df = catalog.releases()

        assert len(df) == 3
        assert set(df["data_type"]) == {"availability", "challenge"}

    def test_filters_by_data_type(self, mock_api):
        mock_api.add(
            responses.GET,
            AS_OF_DATES_URL,
            json=as_of_dates(["2023-12-31", "2024-06-30"], ["2025-02-28"]),
        )

        df = catalog.releases("availability")

        assert len(df) == 2
        assert set(df["data_type"]) == {"availability"}

    def test_response_is_memoized(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))

        catalog.releases()
        catalog.releases()
        catalog.releases("availability")

        # Resolving "latest" happens on nearly every call; one request is enough.
        assert len(mock_api.calls) == 1

    def test_refresh_forces_a_new_request(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-12-31"]))

        catalog.releases()
        df = catalog.releases(refresh=True)

        assert len(mock_api.calls) == 2
        assert df["as_of_date"].iloc[0] == "2024-12-31"


class TestResolveReleases:
    @pytest.fixture(autouse=True)
    def _dates(self, mock_api):
        mock_api.add(
            responses.GET,
            AS_OF_DATES_URL,
            json=as_of_dates(["2022-12-31", "2024-06-30", "2023-06-30"], ["2025-02-28"]),
        )

    def test_latest_picks_the_newest_published(self):
        assert catalog.resolve_releases("latest", "availability") == ["2024-06-30"]

    def test_latest_is_per_data_type(self):
        # The challenge series is published monthly and runs ahead of availability.
        assert catalog.resolve_releases("latest", "challenge") == ["2025-02-28"]

    def test_all_returns_everything_sorted(self):
        assert catalog.resolve_releases("all", "availability") == [
            "2022-12-31",
            "2023-06-30",
            "2024-06-30",
        ]

    def test_explicit_date_passes_through(self):
        assert catalog.resolve_releases("2023-06-30", "availability") == ["2023-06-30"]

    def test_unpublished_date_lists_what_exists(self):
        with pytest.raises(ValueError) as excinfo:
            catalog.resolve_releases("2021-01-01", "availability")

        message = str(excinfo.value)
        assert "Published releases" in message
        assert "2024-06-30" in message

    def test_unknown_data_type_is_explained(self):
        with pytest.raises(ValueError, match="no published releases"):
            catalog.resolve_releases("latest", "fabric")


class TestAvailabilityFiles:
    def test_passes_documented_query_parameters(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(
            responses.GET,
            f"{AVAILABILITY_LIST_URL}/2024-06-30",
            json=api_payload([availability_file_row(1, "53")]),
        )

        catalog.availability_files(
            release="2024-06-30",
            category="State",
            subcategory="Location Coverage",
            technology_type="Fixed Broadband",
        )

        request_url = mock_api.calls[-1].request.url
        assert "category=State" in request_url
        assert "subcategory=Location+Coverage" in request_url
        assert "technology_type=Fixed+Broadband" in request_url

    def test_omits_unset_parameters(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(
            responses.GET,
            f"{AVAILABILITY_LIST_URL}/2024-06-30",
            json=api_payload([availability_file_row(1, "53")]),
        )

        catalog.availability_files(release="2024-06-30", category="State")

        assert "speed_tier" not in mock_api.calls[-1].request.url

    def test_adds_a_release_column(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(
            responses.GET,
            f"{AVAILABILITY_LIST_URL}/2024-06-30",
            json=api_payload([availability_file_row(1, "53")]),
        )

        df = catalog.availability_files(release="2024-06-30")

        assert df["release"].iloc[0] == "2024-06-30"

    def test_state_fips_keeps_its_leading_zero(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(
            responses.GET,
            f"{AVAILABILITY_LIST_URL}/2024-06-30",
            json=api_payload([availability_file_row(1, "06")]),
        )

        df = catalog.availability_files(release="2024-06-30")

        assert df["state_fips"].iloc[0] == "06"

    def test_state_filter_accepts_friendly_names(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(
            responses.GET,
            f"{AVAILABILITY_LIST_URL}/2024-06-30",
            json=api_payload([availability_file_row(1, "53"), availability_file_row(2, "41")]),
        )

        df = catalog.availability_files(release="2024-06-30", state="Washington")

        assert list(df["state_fips"]) == ["53"]

    def test_multiple_releases_are_stacked(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2023-12-31", "2024-06-30"]))
        for date in ("2023-12-31", "2024-06-30"):
            mock_api.add(
                responses.GET,
                f"{AVAILABILITY_LIST_URL}/{date}",
                json=api_payload([availability_file_row(1, "53")]),
            )

        df = catalog.availability_files(release="all")

        assert sorted(df["release"]) == ["2023-12-31", "2024-06-30"]


class TestChallengeFiles:
    def test_passes_category(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates([], ["2025-02-28"]))
        mock_api.add(
            responses.GET,
            f"{CHALLENGE_LIST_URL}/2025-02-28",
            json=api_payload([challenge_file_row(5779, "53", "Fabric Challenge - In Progress")]),
        )

        catalog.challenge_files(release="latest", category="Fabric Challenge - In Progress")

        assert "category=Fabric+Challenge+-+In+Progress" in mock_api.calls[-1].request.url


class TestFundingFiles:
    def test_filters_data_type_client_side(self, mock_api):
        mock_api.add(
            responses.GET,
            FUNDING_LIST_URL,
            json=api_payload(
                [
                    {"file_id": 1, "category": "Funding Data", "data_type": "Program"},
                    {"file_id": 2, "category": "Funding Data", "data_type": "Project"},
                ]
            ),
        )

        df = catalog.funding_files(data_type="Program")

        assert list(df["file_id"]) == [1]

    def test_endpoint_takes_no_parameters(self, mock_api):
        mock_api.add(responses.GET, FUNDING_LIST_URL, json=api_payload([]))

        catalog.funding_files()

        assert "?" not in mock_api.calls[-1].request.url


class TestEmptyResponses:
    def test_empty_catalog_returns_an_empty_frame_not_an_error(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(responses.GET, f"{AVAILABILITY_LIST_URL}/2024-06-30", json=api_payload([]))

        df = catalog.availability_files(release="latest")

        assert df.empty

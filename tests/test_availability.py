"""End-to-end availability pulls, with HTTP mocked."""

from __future__ import annotations

import pandas as pd
import pytest
import responses

import bdcdata
from bdcdata.exceptions import BdcDataError
from helpers import (
    AS_OF_DATES_URL,
    AVAILABILITY_LIST_URL,
    FIXED_AVAILABILITY_CSV,
    MAP_DOWNLOAD_URL,
    SERVED_UNSERVED_CSV,
    api_payload,
    as_of_dates,
    availability_file_row,
    make_csv_zip,
)


@pytest.fixture
def wa_fiber(mock_api):
    """One release, one state, one technology, ready to download."""
    mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
    mock_api.add(
        responses.GET,
        f"{AVAILABILITY_LIST_URL}/2024-06-30",
        json=api_payload([availability_file_row(970177, "53", technology_code="50")]),
    )
    mock_api.add(
        responses.GET,
        f"{MAP_DOWNLOAD_URL}/availability/970177",
        body=make_csv_zip(FIXED_AVAILABILITY_CSV),
        status=200,
    )
    return mock_api


class TestFixed:
    def test_returns_the_rows(self, wa_fiber):
        df = bdcdata.availability.fixed(state="WA", technology="fiber")

        assert len(df) == 2
        assert df["brand_name"].iloc[0] == "Acme Telecom"

    def test_uses_the_documented_download_path(self, wa_fiber):
        bdcdata.availability.fixed(state="WA", technology="fiber")

        download = wa_fiber.calls[-1].request.url
        # downloadFile/{data_type}/{file_id} -- v1 hardcoded the data_type and
        # so could never fetch anything but availability.
        assert download.endswith("/downloadFile/availability/970177")

    def test_stamps_release_and_state(self, wa_fiber):
        df = bdcdata.availability.fixed(state="WA", technology="fiber")

        assert set(df["release"]) == {"2024-06-30"}
        assert set(df["state_fips"]) == {"53"}

    def test_identifier_columns_are_strings(self, wa_fiber):
        df = bdcdata.availability.fixed(state="WA", technology="fiber")

        assert df["location_id"].iloc[1] == "9999999999999"
        assert df["frn"].iloc[0] == "0032176356"
        assert df["block_geoid"].iloc[0] == "530330001001000"

    def test_accepts_every_state_spelling(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(
            responses.GET,
            f"{AVAILABILITY_LIST_URL}/2024-06-30",
            json=api_payload([availability_file_row(970177, "53")]),
        )
        for _ in range(3):
            mock_api.add(
                responses.GET,
                f"{MAP_DOWNLOAD_URL}/availability/970177",
                body=make_csv_zip(FIXED_AVAILABILITY_CSV),
                status=200,
            )

        for state in ("WA", "Washington", 53):
            assert len(bdcdata.availability.fixed(state=state, technology="fiber")) == 2

    def test_filters_to_the_requested_technology(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(
            responses.GET,
            f"{AVAILABILITY_LIST_URL}/2024-06-30",
            json=api_payload(
                [
                    availability_file_row(1, "53", technology_code="50"),
                    availability_file_row(2, "53", technology_code="10"),
                ]
            ),
        )
        mock_api.add(
            responses.GET,
            f"{MAP_DOWNLOAD_URL}/availability/1",
            body=make_csv_zip(FIXED_AVAILABILITY_CSV),
            status=200,
        )

        bdcdata.availability.fixed(state="WA", technology="fiber")

        downloads = [c.request.url for c in mock_api.calls if "downloadFile" in c.request.url]
        assert len(downloads) == 1
        assert downloads[0].endswith("/1")

    def test_multiple_states_are_concatenated(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(
            responses.GET,
            f"{AVAILABILITY_LIST_URL}/2024-06-30",
            json=api_payload([availability_file_row(1, "53"), availability_file_row(2, "41")]),
        )
        for file_id in (1, 2):
            mock_api.add(
                responses.GET,
                f"{MAP_DOWNLOAD_URL}/availability/{file_id}",
                body=make_csv_zip(FIXED_AVAILABILITY_CSV),
                status=200,
            )

        df = bdcdata.availability.fixed(state=["WA", "OR"], technology="fiber")

        assert len(df) == 4
        assert set(df["state_fips"]) == {"53", "41"}

    def test_index_is_clean_after_concatenation(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(
            responses.GET,
            f"{AVAILABILITY_LIST_URL}/2024-06-30",
            json=api_payload([availability_file_row(1, "53"), availability_file_row(2, "41")]),
        )
        for file_id in (1, 2):
            mock_api.add(
                responses.GET,
                f"{MAP_DOWNLOAD_URL}/availability/{file_id}",
                body=make_csv_zip(FIXED_AVAILABILITY_CSV),
                status=200,
            )

        df = bdcdata.availability.fixed(state=["WA", "OR"], technology="fiber")

        assert list(df.index) == [0, 1, 2, 3]

    def test_no_matching_files_gives_an_empty_frame(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(responses.GET, f"{AVAILABILITY_LIST_URL}/2024-06-30", json=api_payload([]))

        df = bdcdata.availability.fixed(state="WA", technology="fiber")

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_bad_technology_is_rejected_before_any_request(self, mock_api):
        with pytest.raises(ValueError, match="not a fixed technology"):
            bdcdata.availability.fixed(state="WA", technology="5g")

        assert len(mock_api.calls) == 0

    def test_bad_state_is_rejected_before_any_request(self, mock_api):
        with pytest.raises(ValueError, match="not a state"):
            bdcdata.availability.fixed(state="Atlantis", technology="fiber")

        assert len(mock_api.calls) == 0


class TestServedUnserved:
    def test_returns_boolean_flags(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(
            responses.GET,
            f"{AVAILABILITY_LIST_URL}/2024-06-30",
            json=api_payload([availability_file_row(555, "53", subcategory="Served-Unserved")]),
        )
        mock_api.add(
            responses.GET,
            f"{MAP_DOWNLOAD_URL}/availability/555",
            body=make_csv_zip(SERVED_UNSERVED_CSV),
            status=200,
        )

        df = bdcdata.availability.served_unserved(state="WA")

        assert df["any_dl100_ul20"].tolist() == [True, False]
        assert df["terrestrial_dl100_ul20"].tolist() == [True, True]

    def test_requests_the_right_subcategory(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(responses.GET, f"{AVAILABILITY_LIST_URL}/2024-06-30", json=api_payload([]))

        bdcdata.availability.served_unserved(state="WA")

        assert "subcategory=Served-Unserved" in mock_api.calls[-1].request.url

    def test_missing_export_warns_rather_than_crashing(self, mock_api, caplog):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2022-12-31"]))
        mock_api.add(responses.GET, f"{AVAILABILITY_LIST_URL}/2022-12-31", json=api_payload([]))

        with caplog.at_level("WARNING", logger="bdcdata"):
            df = bdcdata.availability.served_unserved(state="WA", release="2022-12-31")

        assert df.empty
        assert "August 2026" in caplog.text


class TestMobile:
    def test_requests_gis_shapefile_format(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(
            responses.GET,
            f"{AVAILABILITY_LIST_URL}/2024-06-30",
            json=api_payload(
                [
                    availability_file_row(
                        888,
                        "53",
                        technology_code="500",
                        subcategory="Hexagon Coverage",
                        technology_type="Mobile Broadband",
                    )
                ]
            ),
        )

        pyogrio = pytest.importorskip("pyogrio")  # noqa: F841
        mock_api.add(
            responses.GET,
            f"{MAP_DOWNLOAD_URL}/availability/888/1",
            body=b"not a real shapefile",
            status=200,
        )

        # The download path is what matters here; parsing is covered elsewhere.
        # The body is not a real archive, so the reader rejects it.
        with pytest.raises(BdcDataError):
            bdcdata.availability.mobile(state="WA", technology="5g")

        assert mock_api.calls[-1].request.url.endswith("/downloadFile/availability/888/1")

    def test_mobile_technology_filter_rejects_fixed_codes(self, mock_api):
        with pytest.raises(ValueError, match="not a mobile technology"):
            bdcdata.availability.mobile(state="WA", technology="fiber")

        assert len(mock_api.calls) == 0

    def test_queries_mobile_broadband_subcategory(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(responses.GET, f"{AVAILABILITY_LIST_URL}/2024-06-30", json=api_payload([]))

        bdcdata.availability.mobile(state="WA", technology="5g")

        url = mock_api.calls[-1].request.url
        assert "subcategory=Hexagon+Coverage" in url
        assert "technology_type=Mobile+Broadband" in url


class TestSummaries:
    def test_summary_by_geography_place(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(responses.GET, f"{AVAILABILITY_LIST_URL}/2024-06-30", json=api_payload([]))

        bdcdata.availability.summary_by_geography(kind="fixed", geography="place")

        url = mock_api.calls[-1].request.url
        assert "Summary+by+Geography+Type+-+Census+Place" in url

    def test_summary_by_geography_other(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES_URL, json=as_of_dates(["2024-06-30"]))
        mock_api.add(responses.GET, f"{AVAILABILITY_LIST_URL}/2024-06-30", json=api_payload([]))

        bdcdata.availability.summary_by_geography(kind="mobile", geography="other")

        url = mock_api.calls[-1].request.url
        assert "Summary+by+Geography+Type+-+Other+Geographies" in url
        assert "technology_type=Mobile+Broadband" in url

    def test_bad_geography_is_rejected(self):
        with pytest.raises(ValueError, match="geography must be"):
            bdcdata.availability.summary_by_geography(geography="county")

    def test_bad_kind_is_rejected(self):
        with pytest.raises(ValueError, match="kind must be"):
            bdcdata.availability.provider_summary(kind="satellite")

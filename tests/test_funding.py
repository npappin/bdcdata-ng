"""Funding map filtering and downloads."""

from __future__ import annotations

import pytest
import responses

import bdcdata
from helpers import (
    BASE_URL,
    FUNDING_DOWNLOAD_URL,
    FUNDING_LIST_URL,
    UNSERVED_UNFUNDED_CSV,
    api_payload,
    make_csv_zip,
)

GEOGRAPHY_URL = f"{BASE_URL}/api/public/fundingmap/downloads/downloadGeographyData"
README_LIST_URL = f"{BASE_URL}/api/public/fundingmap/downloads/listReadmeFiles"
README_DOWNLOAD_URL = f"{BASE_URL}/api/public/fundingmap/downloads/downloadReadmeFile"


def funding_row(file_id, category, data_type=None, state_fips=None, **extra):
    return {
        "file_id": file_id,
        "category": category,
        "data_type": data_type,
        "agency_name": extra.get("agency_name", "Federal Communications Commission"),
        "program_name": extra.get("program_name", "Bringing Puerto Rico Together"),
        "project_name": extra.get("project_name"),
        "state_fips": state_fips,
        "state_name": extra.get("state_name"),
        "file_name": f"fundingdata_{file_id}",
        "record_count": "1",
    }


class TestUnservedUnfunded:
    def test_downloads_the_state_file(self, mock_api):
        mock_api.add(
            responses.GET,
            FUNDING_LIST_URL,
            json=api_payload(
                [
                    funding_row(1, "Unserved-Unfunded", state_fips="53"),
                    funding_row(2, "Unserved-Unfunded", state_fips="41"),
                ]
            ),
        )
        mock_api.add(
            responses.GET,
            f"{FUNDING_DOWNLOAD_URL}/1",
            body=make_csv_zip(UNSERVED_UNFUNDED_CSV),
            status=200,
        )

        df = bdcdata.funding.unserved_unfunded(state="WA")

        assert len(df) == 1
        assert df["location_id"].iloc[0] == "1357135307"

    def test_uses_the_funding_download_endpoint(self, mock_api):
        mock_api.add(
            responses.GET,
            FUNDING_LIST_URL,
            json=api_payload([funding_row(1, "Unserved-Unfunded", state_fips="53")]),
        )
        mock_api.add(
            responses.GET,
            f"{FUNDING_DOWNLOAD_URL}/1",
            body=make_csv_zip(UNSERVED_UNFUNDED_CSV),
            status=200,
        )

        bdcdata.funding.unserved_unfunded(state="WA")

        # The funding map has its own endpoint with no data_type segment.
        assert "/fundingmap/downloads/downloadFile/1" in mock_api.calls[-1].request.url

    def test_state_filter_uses_friendly_names(self, mock_api):
        mock_api.add(
            responses.GET,
            FUNDING_LIST_URL,
            json=api_payload(
                [
                    funding_row(1, "Unserved-Unfunded", state_fips="53"),
                    funding_row(2, "Unserved-Unfunded", state_fips="41"),
                ]
            ),
        )
        mock_api.add(
            responses.GET,
            f"{FUNDING_DOWNLOAD_URL}/2",
            body=make_csv_zip(UNSERVED_UNFUNDED_CSV),
            status=200,
        )

        bdcdata.funding.unserved_unfunded(state="Oregon")

        assert mock_api.calls[-1].request.url.endswith("/2")


class TestProgramsAndProjects:
    def test_filters_by_data_type(self, mock_api):
        mock_api.add(
            responses.GET,
            FUNDING_LIST_URL,
            json=api_payload(
                [
                    funding_row(1, "Funding Data", data_type="Program"),
                    funding_row(2, "Funding Data", data_type="Project"),
                ]
            ),
        )
        mock_api.add(
            responses.GET,
            f"{FUNDING_DOWNLOAD_URL}/1",
            body=make_csv_zip("program_id,program_name\n29,ABC Program\n"),
            status=200,
        )

        df = bdcdata.funding.programs()

        assert mock_api.calls[-1].request.url.endswith("/1")
        assert df["program_id"].iloc[0] == 29

    def test_agency_filter_is_case_insensitive_substring(self, mock_api):
        mock_api.add(
            responses.GET,
            FUNDING_LIST_URL,
            json=api_payload(
                [
                    funding_row(1, "Funding Data", data_type="Program"),
                    funding_row(
                        2,
                        "Funding Data",
                        data_type="Program",
                        agency_name="Department of Agriculture",
                    ),
                ]
            ),
        )
        mock_api.add(
            responses.GET,
            f"{FUNDING_DOWNLOAD_URL}/2",
            body=make_csv_zip("program_id\n1\n"),
            status=200,
        )

        bdcdata.funding.programs(agency="agriculture")

        assert mock_api.calls[-1].request.url.endswith("/2")

    def test_stamps_agency_and_program_context(self, mock_api):
        mock_api.add(
            responses.GET,
            FUNDING_LIST_URL,
            json=api_payload([funding_row(1, "Funding Data", data_type="Program")]),
        )
        mock_api.add(
            responses.GET,
            f"{FUNDING_DOWNLOAD_URL}/1",
            body=make_csv_zip("program_id\n29\n"),
            status=200,
        )

        df = bdcdata.funding.programs()

        assert df["agency_name"].iloc[0] == "Federal Communications Commission"

    def test_unfiltered_bulk_download_warns(self, mock_api, caplog):
        rows = [funding_row(i, "Funding Data", data_type="Program") for i in range(60)]
        mock_api.add(responses.GET, FUNDING_LIST_URL, json=api_payload(rows))
        for i in range(60):
            mock_api.add(
                responses.GET,
                f"{FUNDING_DOWNLOAD_URL}/{i}",
                body=make_csv_zip("program_id\n1\n"),
                status=200,
            )

        with caplog.at_level("WARNING", logger="bdcdata"):
            bdcdata.funding.programs()

        assert "No agency or program filter" in caplog.text


class TestFundedLocations:
    def test_by_program_selects_the_other_category(self, mock_api):
        mock_api.add(
            responses.GET,
            FUNDING_LIST_URL,
            json=api_payload(
                [
                    funding_row(1, "Funded Locations State", state_fips="53"),
                    funding_row(2, "Funded Locations State Program", state_fips="53"),
                ]
            ),
        )
        mock_api.add(
            responses.GET,
            f"{FUNDING_DOWNLOAD_URL}/2",
            body=make_csv_zip("location_id\n1357135307\n"),
            status=200,
        )

        bdcdata.funding.funded_locations(state="WA", by_program=True)

        assert mock_api.calls[-1].request.url.endswith("/2")

    def test_missing_export_warns(self, mock_api, caplog):
        mock_api.add(responses.GET, FUNDING_LIST_URL, json=api_payload([]))

        with caplog.at_level("WARNING", logger="bdcdata"):
            df = bdcdata.funding.funded_locations(state="WA")

        assert df.empty
        assert "June 2026" in caplog.text


class TestProjectsInGeography:
    def test_reads_a_bare_csv_response(self, mock_api):
        # This endpoint returns CSV directly, not a ZIP.
        mock_api.add(
            responses.GET,
            GEOGRAPHY_URL,
            body="project_id,project_name\n42,Rural Fiber\n",
            status=200,
        )

        df = bdcdata.funding.projects_in_geography("county", "36001")

        assert df["project_name"].iloc[0] == "Rural Fiber"

    def test_passes_geography_parameters(self, mock_api):
        mock_api.add(responses.GET, GEOGRAPHY_URL, body="project_id\n1\n", status=200)

        bdcdata.funding.projects_in_geography("county", "36001")

        url = mock_api.calls[-1].request.url
        assert "geography_type=county" in url
        assert "geography_id=36001" in url


class TestReadmes:
    def test_lists_readmes(self, mock_api):
        mock_api.add(
            responses.GET,
            README_LIST_URL,
            json=api_payload(
                [
                    {
                        "program_id": "1",
                        "program_name": "BFM Program",
                        "ref_id": "f4a81134-6f4a-4c24-a9b6-7d31af0d0b4a",
                        "file_name": "Readme.pdf",
                    }
                ]
            ),
        )

        df = bdcdata.funding.readmes()

        assert df["ref_id"].iloc[0] == "f4a81134-6f4a-4c24-a9b6-7d31af0d0b4a"

    def test_downloads_a_readme_to_a_directory(self, mock_api, tmp_path):
        mock_api.add(
            responses.GET,
            f"{README_DOWNLOAD_URL}/abc-123",
            body=b"%PDF-1.4 fake",
            status=200,
        )

        path = bdcdata.funding.download_readme("abc-123", dest=tmp_path)

        assert path.exists()
        assert path.read_bytes() == b"%PDF-1.4 fake"
        assert path.parent == tmp_path

    def test_empty_ref_id_is_rejected(self):
        with pytest.raises(ValueError, match="ref_id is required"):
            bdcdata.funding.download_readme("")

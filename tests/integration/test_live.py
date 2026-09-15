"""Live tests against the real FCC API.

Skipped unless ``BDC_USERNAME`` and ``BDC_API_KEY`` are set. Run them with::

    pytest -m integration -v

These make real, rate-limited requests and download real files, so they are
slow by design. They exist to catch the things a mock cannot: the FCC changing
a column name, renaming a subcategory, or moving a host.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

import bdcdata

pytestmark = pytest.mark.integration

HAVE_CREDENTIALS = bool(os.environ.get("BDC_USERNAME") and os.environ.get("BDC_API_KEY"))

skip_without_credentials = pytest.mark.skipif(
    not HAVE_CREDENTIALS,
    reason="Set BDC_USERNAME and BDC_API_KEY to run live tests",
)


@pytest.fixture(scope="module", autouse=True)
def _live_setup(tmp_path_factory):
    """Cache downloads so re-running the suite does not refetch hundreds of MB."""
    bdcdata.set_cache(True, path=tmp_path_factory.mktemp("bdc_live_cache"))
    yield
    bdcdata.set_cache(False)


@skip_without_credentials
class TestCredentials:
    def test_credentials_are_accepted(self):
        assert bdcdata.check_credentials() is True


@skip_without_credentials
class TestCatalog:
    def test_releases_are_published(self):
        df = bdcdata.catalog.releases()

        assert not df.empty
        assert {"data_type", "as_of_date"} <= set(df.columns)

    def test_availability_and_challenge_series_both_exist(self):
        types = set(bdcdata.catalog.releases()["data_type"])

        assert "availability" in types
        assert "challenge" in types

    def test_latest_resolves_to_a_real_date(self):
        latest = bdcdata.catalog.resolve_releases("latest", "availability")

        assert len(latest) == 1
        assert pd.Timestamp(latest[0])

    def test_availability_catalog_has_the_documented_columns(self):
        df = bdcdata.catalog.availability_files(
            release="latest", category="State", technology_type="Fixed Broadband"
        )

        assert not df.empty
        expected = {"file_id", "category", "subcategory", "state_fips", "file_name"}
        assert expected <= set(df.columns)

    def test_state_fips_keeps_leading_zeros_live(self):
        df = bdcdata.catalog.availability_files(release="latest", category="State")
        fips = set(df["state_fips"].dropna())

        # Alabama is 01; if this comes back as "1" the type handling regressed.
        assert all(len(f) == 2 for f in fips)


@skip_without_credentials
class TestAvailability:
    @pytest.fixture(scope="class")
    def wa_fiber(self):
        return bdcdata.availability.fixed(state="WA", technology="fiber")

    def test_returns_rows(self, wa_fiber):
        assert len(wa_fiber) > 0

    def test_has_the_documented_columns(self, wa_fiber):
        expected = {
            "frn",
            "provider_id",
            "brand_name",
            "location_id",
            "technology",
            "max_advertised_download_speed",
            "max_advertised_upload_speed",
            "low_latency",
            "business_residential_code",
            "state_usps",
            "block_geoid",
            "h3_res8_id",
        }
        missing = expected - set(wa_fiber.columns)
        assert not missing, f"FCC file is missing expected columns: {missing}"

    def test_location_id_is_a_string_and_not_truncated(self, wa_fiber):
        assert pd.api.types.is_string_dtype(wa_fiber["location_id"])
        assert wa_fiber["location_id"].str.len().min() >= 8

    def test_block_geoid_is_fifteen_characters(self, wa_fiber):
        assert (wa_fiber["block_geoid"].dropna().str.len() == 15).all()

    def test_all_rows_are_the_requested_technology(self, wa_fiber):
        assert set(wa_fiber["technology"].unique()) == {50}

    def test_all_rows_are_the_requested_state(self, wa_fiber):
        assert set(wa_fiber["state_usps"].unique()) == {"WA"}

    def test_low_latency_is_boolean(self, wa_fiber):
        assert str(wa_fiber["low_latency"].dtype) == "bool[pyarrow]"

    def test_release_is_stamped(self, wa_fiber):
        assert wa_fiber["release"].nunique() == 1

    def test_cache_makes_the_second_call_free(self):
        import time

        start = time.monotonic()
        bdcdata.availability.fixed(state="DC", technology="fiber")
        first = time.monotonic() - start

        start = time.monotonic()
        bdcdata.availability.fixed(state="DC", technology="fiber")
        second = time.monotonic() - start

        # The cached call still re-parses the CSV, but it must not re-download.
        assert second < first


@skip_without_credentials
class TestServedUnserved:
    def test_flags_are_boolean(self):
        df = bdcdata.availability.served_unserved(state="DC")

        if df.empty:
            pytest.skip("No served/unserved export published for the latest release yet")

        for column in ("any_dl100_ul20", "wired_dl100_ul20", "terrestrial_dl100_ul20"):
            assert str(df[column].dtype) == "bool[pyarrow]"


@skip_without_credentials
class TestMobile:
    def test_returns_h3_cells_without_geometry(self):
        pytest.importorskip("pyogrio")

        df = bdcdata.availability.mobile(state="DC", technology="5g")

        if df.empty:
            pytest.skip("No mobile coverage file published for DC/5G")

        assert "h3_res9_id" in df.columns
        assert "geometry" not in df.columns


@skip_without_credentials
class TestChallenges:
    def test_fabric_challenges_download(self):
        df = bdcdata.challenges.fabric(state="DC", status="in_progress")

        if df.empty:
            pytest.skip("No in-progress fabric challenges published for DC")

        assert "challenge_id" in df.columns
        assert pd.api.types.is_string_dtype(df["location_id"])

    def test_catalog_categories_match_the_lookup_table(self):
        published = set(bdcdata.catalog.challenge_files(release="latest")["category"])
        known = set(bdcdata.lookups.challenge_categories()["category"])

        # A new category means the FCC added one; challenges.get() still
        # reaches it, but the lookup table should be updated.
        unknown = published - known
        assert not unknown, f"FCC publishes categories not in lookups: {unknown}"


@skip_without_credentials
class TestFunding:
    def test_funding_catalog_is_populated(self):
        df = bdcdata.catalog.funding_files()

        assert not df.empty
        assert "category" in df.columns

    def test_unserved_unfunded_downloads(self):
        df = bdcdata.funding.unserved_unfunded(state="DC")

        if df.empty:
            pytest.skip("No unserved/unfunded file published for DC")

        assert "location_id" in df.columns

    def test_geographies_are_listed(self):
        df = bdcdata.catalog.geographies()

        assert not df.empty
        assert {"geography_type", "geography_id"} <= set(df.columns)


@skip_without_credentials
class TestErrorHandling:
    def test_bad_token_raises_auth_error(self):
        with pytest.raises(bdcdata.BdcAuthError):
            bdcdata.check_credentials(
                username="nobody@example.com", token="definitely-not-a-real-token"
            )

"""Archive reading and the dtype rules that protect identifier columns."""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from bdcdata._readers import list_archive, read_csv_archive, read_csv_bytes
from bdcdata.exceptions import BdcDataError
from helpers import CHALLENGE_CSV, FIXED_AVAILABILITY_CSV, SERVED_UNSERVED_CSV, make_csv_zip


class TestReadCsvArchive:
    def test_reads_the_csv(self):
        df = read_csv_archive(make_csv_zip(FIXED_AVAILABILITY_CSV))
        assert len(df) == 2
        assert "location_id" in df.columns

    def test_leading_zeros_survive_in_frn(self):
        df = read_csv_archive(make_csv_zip(FIXED_AVAILABILITY_CSV))
        assert df["frn"].iloc[0] == "0032176356"
        assert df["frn"].iloc[1] == "0000000123"

    def test_leading_zeros_survive_in_block_geoid(self):
        csv = FIXED_AVAILABILITY_CSV.replace("530330001001000", "011010106033002")
        df = read_csv_archive(make_csv_zip(csv))
        assert df["block_geoid"].iloc[0] == "011010106033002"
        assert len(df["block_geoid"].iloc[0]) == 15

    def test_thirteen_digit_location_id_is_not_truncated(self):
        # The v1 package typed this UInt32, whose max is 4,294,967,295 --
        # a 13-digit location_id does not fit.
        df = read_csv_archive(make_csv_zip(FIXED_AVAILABILITY_CSV))
        assert df["location_id"].iloc[1] == "9999999999999"
        assert pd.api.types.is_string_dtype(df["location_id"])

    def test_business_residential_code_is_typed(self):
        # v1 misspelled this as business_residental_code, so the hint never applied.
        df = read_csv_archive(make_csv_zip(FIXED_AVAILABILITY_CSV))
        assert df["business_residential_code"].iloc[0] == "X"
        assert pd.api.types.is_string_dtype(df["business_residential_code"])

    def test_boolean_flags_become_booleans(self):
        df = read_csv_archive(make_csv_zip(FIXED_AVAILABILITY_CSV))
        assert df["low_latency"].tolist() == [True, False]
        assert str(df["low_latency"].dtype) == "bool[pyarrow]"

    def test_served_unserved_flags_all_convert(self):
        df = read_csv_archive(make_csv_zip(SERVED_UNSERVED_CSV))
        for column in ("any_dl100_ul20", "wired_dl100_ul20", "terrestrial_dl100_ul20"):
            assert str(df[column].dtype) == "bool[pyarrow]"
        assert df["any_dl100_ul20"].tolist() == [True, False]

    def test_missing_numbers_become_null_not_zero(self):
        df = read_csv_archive(make_csv_zip(FIXED_AVAILABILITY_CSV))
        assert pd.isna(df["max_advertised_upload_speed"].iloc[1])

    def test_speeds_are_integers(self):
        df = read_csv_archive(make_csv_zip(FIXED_AVAILABILITY_CSV))
        assert df["max_advertised_download_speed"].iloc[0] == 1000
        assert str(df["max_advertised_download_speed"].dtype) == "int64[pyarrow]"

    def test_date_columns_are_parsed(self):
        df = read_csv_archive(make_csv_zip(CHALLENGE_CSV))
        assert df["fabric_vintage"].iloc[0] == pd.Timestamp("2022-06-30")

    def test_uses_pyarrow_backend(self):
        df = read_csv_archive(make_csv_zip(FIXED_AVAILABILITY_CSV))
        assert all("pyarrow" in str(dtype) for dtype in df.dtypes)


class TestMemberSelection:
    def test_ignores_macosx_sidecar_files(self):
        # v1 read filelist[0] blindly, which a sidecar entry would break.
        payload = make_csv_zip(
            FIXED_AVAILABILITY_CSV,
            name="bdc_53_fiber.csv",
            extra={"__MACOSX/._bdc_53_fiber.csv": "junk", "readme.txt": "notes"},
        )
        df = read_csv_archive(payload)
        assert len(df) == 2
        assert "frn" in df.columns

    def test_lists_archive_contents(self):
        payload = make_csv_zip(FIXED_AVAILABILITY_CSV, name="a.csv", extra={"b.txt": "x"})
        assert set(list_archive(payload)) == {"a.csv", "b.txt"}

    def test_archive_with_no_csv_raises_a_useful_error(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("notes.pdf", "not a csv")

        with pytest.raises(BdcDataError, match="contained no"):
            read_csv_archive(buffer.getvalue())

    def test_selection_is_deterministic(self):
        payload = make_csv_zip(
            FIXED_AVAILABILITY_CSV, name="short.csv", extra={"a_much_longer_name.csv": "x,y\n1,2\n"}
        )
        # Shortest path wins, so the same archive always reads the same way.
        assert read_csv_archive(payload).equals(read_csv_archive(payload))


class TestBadInput:
    def test_non_zip_bytes_explain_themselves(self):
        with pytest.raises(BdcDataError, match="did not contain a ZIP"):
            read_csv_archive(b"<html>503 Service Unavailable</html>")

    def test_error_shows_the_first_bytes(self):
        with pytest.raises(BdcDataError, match="Service Unavailable"):
            read_csv_archive(b"<html>503 Service Unavailable</html>")


class TestReadCsvBytes:
    def test_reads_a_bare_csv(self):
        df = read_csv_bytes(b"a,b\n1,2\n")
        assert len(df) == 1

    def test_applies_the_same_type_rules(self):
        df = read_csv_bytes(b"location_id,block_geoid\n1357135307,011010106033002\n")
        assert df["block_geoid"].iloc[0] == "011010106033002"

    def test_transparently_handles_a_zip(self):
        # downloadGeographyData returns bare CSV, but be forgiving if that changes.
        df = read_csv_bytes(make_csv_zip(FIXED_AVAILABILITY_CSV))
        assert len(df) == 2

    def test_html_error_page_raises(self):
        with pytest.raises(BdcDataError):
            read_csv_bytes(b"\x00\x01\x02 not text at all \xff\xfe")

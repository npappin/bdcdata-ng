"""Column types, transcribed from the FCC data specifications.

Types are registered **by column name**, not per file. The FCC reuses the same
names across products (``location_id`` appears in availability, challenge, and
funding files), and registering names rather than files means a new or renamed
export still gets sensible types instead of whatever pandas infers.

Anything not registered here is inferred by pandas with the pyarrow backend.

Sources
-------
- Specifications for Data Downloads from the National Broadband Map,
  rev 2.4.3 (2026-08-11)
- Specifications for Data Downloads from the Broadband Funding Map,
  rev 6.0 (2026-03-16)
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["COLUMN_TYPES", "dtypes_for", "finalize"]

Kind = Literal["string", "int", "float", "bool", "date"]


# Identifiers and codes that must stay strings. Leading zeros, fixed widths,
# and cross-file joins all break if these become numbers.
_STRING_COLUMNS: tuple[str, ...] = (
    # 10-digit FCC Registration Number -- "0032176356" is not 32176356
    "frn",
    # Spec says String{13} in availability files and Integer in challenge
    # files. Forced to string in both so the two can be joined.
    "location_id",
    # 15-digit census block GEOID, leading zeros significant
    "block_geoid",
    "h3_res8_id",
    "h3_res9_id",
    "h3_cell_id",
    # 2-digit FIPS, leading zero included per spec
    "state_fips",
    "county_fips",
    "state_usps",
    "location_state",
    "geography_id",
    "geography_type",
    "geography_desc",
    "geography_desc_full",
    "business_residential_code",
    "brand_name",
    "holding_company",
    "entity_name",
    "provider_name",
    "agency_name",
    "program_name",
    "project_name",
    "technology_code_desc",
    "category_code_desc",
    "adjudication_code",
    "data_type",
    "category",
    "subcategory",
    "technology_type",
    "speed_tier",
    "file_name",
    "file_type",
    "address_primary",
    "city",
    "state",
    "zip",
    "zip_suffix",
    "unit_count",
    "building_type_code",
    "model_id",
    "tool_name",
    "tool_version",
    "tool_developer",
)

_INT_COLUMNS: tuple[str, ...] = (
    "provider_id",
    "technology",
    "technology_code",
    "max_advertised_download_speed",
    "max_advertised_upload_speed",
    "challenge_id",
    "category_code",
    "environmnt",
    "h3_resolution",
    "record_count",
    "file_id",
    "program_id",
    "project_id",
    "location_count_res",
    "unit_count_res",
    "location_count_bus",
    "unit_count_bus",
    "area_stationary",
    "area_invehicle",
    "locations_planned",
    "locations_supported",
    "buildout_requirement",
    "model_resolution",
)

# Boolean flags the FCC encodes as the integers 0 and 1.
_BOOL_COLUMNS: tuple[str, ...] = (
    "low_latency",
    "any_dl100_ul20",
    "wired_dl100_ul20",
    "terrestrial_dl100_ul20",
)

_FLOAT_COLUMNS: tuple[str, ...] = (
    "mindown",
    "minup",
    "funding_obligated",
    "funding_committed",
    "funding_revised",
    "funding_disbursed",
)

_DATE_COLUMNS: tuple[str, ...] = (
    "fabric_vintage",
    "data_vintage",
    "request_date",
    "date_received",
    "withdraw_date",
    "adjudication_date",
    "challenge_date",
    "resolution_date",
    "authorization_date",
    "program_start_date",
    "program_end_date",
)
# Deliberately NOT a date column: `as_of_date` identifies a release and is
# passed straight back in as `release="2024-06-30"`. Keeping it a string means
# what catalog.releases() shows is exactly what you can hand to a data
# function.

COLUMN_TYPES: dict[str, Kind] = {
    **{name: "string" for name in _STRING_COLUMNS},
    **{name: "int" for name in _INT_COLUMNS},
    **{name: "bool" for name in _BOOL_COLUMNS},
    **{name: "float" for name in _FLOAT_COLUMNS},
    **{name: "date" for name in _DATE_COLUMNS},
}

# Percentage columns are named consistently enough to match by suffix
# (res_st_pct, bus_iv_pct, and the many speed_*_pct columns in the summaries).
_FLOAT_SUFFIXES = ("_pct",)


def _kind_for(column: str) -> Kind | None:
    name = column.strip().lower()
    if name in COLUMN_TYPES:
        return COLUMN_TYPES[name]
    if name.endswith(_FLOAT_SUFFIXES):
        return "float"
    return None


def dtypes_for(columns: list[str]) -> dict[str, Any]:
    """Build a ``dtype`` mapping for :func:`pandas.read_csv`.

    Booleans are read as small integers and converted afterwards, because the
    files store them as ``0``/``1`` rather than ``True``/``False``. Dates are
    read as strings and parsed in :func:`finalize`.
    """
    import pandas as pd
    import pyarrow as pa

    # Values are pd.ArrowDtype instances. Typed as Any because pandas-stubs
    # enumerates accepted dtypes as literals and does not include ArrowDtype
    # in the read_csv/astype overloads.
    mapping: dict[str, Any] = {}
    for column in columns:
        kind = _kind_for(column)
        if kind == "string":
            mapping[column] = pd.ArrowDtype(pa.string())
        elif kind == "int":
            mapping[column] = pd.ArrowDtype(pa.int64())
        elif kind == "float":
            mapping[column] = pd.ArrowDtype(pa.float64())
        elif kind == "bool":
            mapping[column] = pd.ArrowDtype(pa.int8())
        elif kind == "date":
            mapping[column] = pd.ArrowDtype(pa.string())
    return mapping


def finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Convert 0/1 integer flags to booleans and date strings to timestamps."""
    import pandas as pd
    import pyarrow as pa

    for column in df.columns:
        kind = _kind_for(column)
        if kind == "bool":
            # On an unexpected encoding, leave the raw values alone rather
            # than lose them.
            with contextlib.suppress(TypeError, ValueError, pa.ArrowInvalid):
                df[column] = df[column].astype(pd.ArrowDtype(pa.bool_()))
        elif kind == "date":
            converted = pd.to_datetime(df[column], errors="coerce", format="ISO8601")
            df[column] = converted.astype(pd.ArrowDtype(pa.timestamp("ns")))
    return df

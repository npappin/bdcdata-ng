"""Broadband availability data.

Who reports service where, by state, technology, and release.

    >>> import bdcdata
    >>> df = bdcdata.availability.fixed(state="WA", technology="fiber")   # doctest: +SKIP

Every function takes ``state`` and ``release`` the same way, and returns a
pandas DataFrame with one row per record in the published files.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from . import catalog
from ._fetch import download_frames
from ._normalize import normalize_states, normalize_technologies

if TYPE_CHECKING:
    import pandas as pd

__all__ = [
    "fixed",
    "served_unserved",
    "mobile",
    "provider_list",
    "provider_summary",
    "summary_by_geography",
]

logger = logging.getLogger("bdcdata")

FIXED_BROADBAND = "Fixed Broadband"
MOBILE_BROADBAND = "Mobile Broadband"


def _select(
    files: pd.DataFrame,
    *,
    states: list[str] | None = None,
    technologies: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Filter catalog rows to the requested states and technologies."""
    if files.empty:
        return []

    df = files
    if states is not None and "state_fips" in df.columns:
        df = df[df["state_fips"].isin(states)]
    if technologies is not None and "technology_code" in df.columns:
        df = df[df["technology_code"].isin(technologies)]
    return df.to_dict("records")


def _describe(what: str, state: Any, technology: Any, releases: list[str]) -> str:
    parts = [what, f"state={state!r}"]
    if technology is not None:
        parts.append(f"technology={technology!r}")
    parts.append(f"release={','.join(releases)}")
    return " ".join(parts)


def _stamp(row: dict[str, Any]) -> dict[str, Any]:
    """Columns to add to each downloaded file.

    The files do not all carry their own vintage or technology, so the values
    from the catalog are stamped on. Without this, concatenating several
    releases produces a frame you cannot disaggregate again.
    """
    extra: dict[str, Any] = {}
    if row.get("release") is not None:
        extra["release"] = row["release"]
    if row.get("state_fips") is not None:
        extra["state_fips"] = row["state_fips"]
    return extra


def fixed(
    state: Any,
    technology: Any = "all",
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Fixed broadband availability by location.

    One row per location per provider per technology: what each provider
    reports offering at each Broadband Serviceable Location.

    Parameters
    ----------
    state:
        ``"WA"``, ``"Washington"``, ``53``, a list of any of those, or
        ``"all"``.
    technology:
        ``"fiber"``, ``50``, ``"wired"``, ``"all"``, or a list. See
        :func:`bdcdata.lookups.technologies`.
    release:
        ``"latest"`` (default), a date like ``"2024-06-30"``, ``"all"``, or a
        list of dates.
    cache:
        Override the global cache setting for this call.
    progress:
        Show a progress bar (needs ``bdcdata[progress]``).

    Returns
    -------
    pandas.DataFrame
        Columns include ``frn``, ``provider_id``, ``brand_name``,
        ``location_id``, ``technology``, ``max_advertised_download_speed``,
        ``max_advertised_upload_speed``, ``low_latency``,
        ``business_residential_code``, ``state_usps``, ``block_geoid``, and
        ``h3_res8_id``, plus ``release`` and ``state_fips``.

    Notes
    -----
    ``location_id`` and ``block_geoid`` are strings, not numbers, so leading
    zeros and full precision survive. Join to the Fabric or to census
    geography on these directly.

    Examples
    --------
    >>> import bdcdata
    >>> df = bdcdata.availability.fixed(state="WA", technology="fiber")  # doctest: +SKIP
    >>> df = bdcdata.availability.fixed(
    ...     state=["WA", "OR"], technology="wired", release="2024-06-30"
    ... )  # doctest: +SKIP
    """
    states = normalize_states(state)
    technologies = normalize_technologies(technology, domain="fixed")
    releases = catalog.resolve_releases(release, "availability")

    files = catalog.availability_files(
        release=releases,
        category="State",
        subcategory="Location Coverage",
        technology_type=FIXED_BROADBAND,
    )
    rows = _select(files, states=states, technologies=technologies)

    return download_frames(
        rows,
        data_type="availability",
        description=_describe("fixed availability", state, technology, releases),
        cache=cache,
        progress=progress,
        extra_columns=_stamp,
    )


def served_unserved(
    state: Any,
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Served / unserved status for every location in the Fabric.

    For each location, whether *any* provider reported service of at least
    100 Mbps down / 20 Mbps up, broken out by any, wired, and terrestrial
    technology groups.

    Parameters
    ----------
    state:
        As in :func:`fixed`.
    release:
        As in :func:`fixed`.

    Returns
    -------
    pandas.DataFrame
        Columns ``location_id``, ``block_geoid``, ``h3_res8_id``,
        ``any_dl100_ul20``, ``wired_dl100_ul20``, ``terrestrial_dl100_ul20``,
        plus ``release`` and ``state_fips``. The three flags are booleans.

    Notes
    -----
    This export was added in the 2026-08-11 revision of the download
    specification, so it is not available for older vintages.
    """
    states = normalize_states(state)
    releases = catalog.resolve_releases(release, "availability")

    files = catalog.availability_files(
        release=releases,
        category="State",
        subcategory="Served-Unserved",
    )
    rows = _select(files, states=states)

    if not rows:
        logger.warning(
            "No served/unserved files published for release(s) %s. This export "
            "was added in the August 2026 specification revision and may not "
            "exist for older vintages.",
            ", ".join(releases),
        )

    return download_frames(
        rows,
        data_type="availability",
        description=_describe("served/unserved", state, None, releases),
        cache=cache,
        progress=progress,
        extra_columns=_stamp,
    )


def mobile(
    state: Any,
    technology: Any = "all",
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Aggregated mobile broadband coverage, as H3 hexagon attributes.

    The FCC publishes these as GIS files. bdcdata reads the attribute table
    and **not** the geometry, so you get one row per H3 resolution-9 cell
    identified by ``h3_res9_id`` without needing geopandas.

    Parameters
    ----------
    state:
        As in :func:`fixed`.
    technology:
        ``"5g"``, ``"4g"``, ``"3g"``, ``500``, ``"all"``, or a list. Mobile
        technologies only.
    release:
        As in :func:`fixed`.

    Returns
    -------
    pandas.DataFrame
        Columns ``technology``, ``mindown``, ``minup``, ``environmnt``, and
        ``h3_res9_id``, plus ``release`` and ``state_fips``.

    Raises
    ------
    BdcOptionalDependencyError
        If ``pyogrio`` is not installed. Install with
        ``pip install 'bdcdata[mobile]'``.

    Notes
    -----
    ``environmnt`` is the FCC's spelling, kept as published. ``0`` means
    outdoor stationary only; ``1`` means in-vehicle mobile and outdoor
    stationary.

    To map these, join ``h3_res9_id`` to hexagon geometry with the ``h3``
    package.

    Examples
    --------
    >>> import bdcdata
    >>> df = bdcdata.availability.mobile(state="WA", technology="5g")  # doctest: +SKIP
    """
    states = normalize_states(state)
    technologies = normalize_technologies(technology, domain="mobile")
    releases = catalog.resolve_releases(release, "availability")

    files = catalog.availability_files(
        release=releases,
        category="State",
        subcategory="Hexagon Coverage",
        technology_type=MOBILE_BROADBAND,
    )
    rows = _select(files, states=states, technologies=technologies)

    return download_frames(
        rows,
        data_type="availability",
        description=_describe("mobile availability", state, technology, releases),
        cache=cache,
        progress=progress,
        gis=True,
        extra_columns=_stamp,
    )


def provider_list(
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """The list of providers that submitted data.

    Returns
    -------
    pandas.DataFrame
        Columns ``frn``, ``provider_id``, ``holding_company``, and related
        fields, plus ``release``.

    Notes
    -----
    Useful as a join target: availability files carry ``provider_id`` and
    ``brand_name``, but not the holding company.
    """
    releases = catalog.resolve_releases(release, "availability")
    files = catalog.availability_files(
        release=releases,
        category="State",
        subcategory="Provider List",
    )
    rows = files.to_dict("records") if not files.empty else []

    return download_frames(
        rows,
        data_type="availability",
        description=_describe("provider list", "all", None, releases),
        cache=cache,
        progress=progress,
        extra_columns=_stamp,
    )


def provider_summary(
    kind: Literal["fixed", "mobile"] = "fixed",
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Per-provider totals.

    Parameters
    ----------
    kind:
        ``"fixed"`` gives location and unit counts by provider and technology.
        ``"mobile"`` gives covered area in square kilometers.
    release:
        As in :func:`fixed`.

    Returns
    -------
    pandas.DataFrame
        For ``"fixed"``: ``provider_id``, ``holding_company``,
        ``technology_code``, ``location_count_res``, ``unit_count_res``,
        ``location_count_bus``, ``unit_count_bus``.
        For ``"mobile"``: ``area_stationary`` and ``area_invehicle``.
    """
    technology_type = _kind_to_technology_type(kind)
    releases = catalog.resolve_releases(release, "availability")

    files = catalog.availability_files(
        release=releases,
        category="Summary",
        subcategory="Provider Summary",
        technology_type=technology_type,
    )
    rows = files.to_dict("records") if not files.empty else []

    return download_frames(
        rows,
        data_type="availability",
        description=_describe(f"{kind} provider summary", "all", None, releases),
        cache=cache,
        progress=progress,
        extra_columns=_stamp,
    )


def summary_by_geography(
    kind: Literal["fixed", "mobile"] = "fixed",
    geography: Literal["place", "other"] = "place",
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Coverage percentages by geography, across all providers.

    Parameters
    ----------
    kind:
        ``"fixed"`` or ``"mobile"``.
    geography:
        ``"place"`` for census places, ``"other"`` for the remaining
        geography types (state, county, congressional district, tribal, CBSA).
        The FCC split these into separate exports in June 2024.
    release:
        As in :func:`fixed`.

    Returns
    -------
    pandas.DataFrame
        Columns include ``geography_type``, ``geography_id``,
        ``geography_desc``, and a set of ``speed_*_pct`` coverage percentages.
    """
    technology_type = _kind_to_technology_type(kind)
    subcategory = {
        "place": "Summary by Geography Type - Census Place",
        "other": "Summary by Geography Type - Other Geographies",
    }.get(geography)
    if subcategory is None:
        raise ValueError(f"geography must be 'place' or 'other', got {geography!r}")

    releases = catalog.resolve_releases(release, "availability")
    files = catalog.availability_files(
        release=releases,
        category="Summary",
        subcategory=subcategory,
        technology_type=technology_type,
    )
    rows = files.to_dict("records") if not files.empty else []

    return download_frames(
        rows,
        data_type="availability",
        description=_describe(f"{kind} summary by {geography}", "all", None, releases),
        cache=cache,
        progress=progress,
        extra_columns=_stamp,
    )


def _kind_to_technology_type(kind: str) -> str:
    if kind == "fixed":
        return FIXED_BROADBAND
    if kind == "mobile":
        return MOBILE_BROADBAND
    raise ValueError(f"kind must be 'fixed' or 'mobile', got {kind!r}")

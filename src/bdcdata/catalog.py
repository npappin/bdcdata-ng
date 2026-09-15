"""What the FCC currently publishes.

Every download is identified by a ``file_id`` that you look up here first.
These functions are thin, faithful wrappers over the API's ``list*``
endpoints -- useful on their own when you want to see what exists before
pulling hundreds of megabytes.

    >>> import bdcdata
    >>> bdcdata.catalog.releases()                        # doctest: +SKIP
    >>> bdcdata.catalog.availability_files(release="latest")   # doctest: +SKIP
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from . import _client
from ._normalize import normalize_release, normalize_states
from ._schemas import dtypes_for, finalize

if TYPE_CHECKING:
    import pandas as pd

__all__ = [
    "availability_files",
    "challenge_files",
    "clear_release_cache",
    "funding_files",
    "geographies",
    "readme_files",
    "releases",
    "resolve_releases",
]

logger = logging.getLogger("bdcdata")

_LIST_AS_OF_DATES = "api/public/map/listAsOfDates"
_LIST_AVAILABILITY = "api/public/map/downloads/listAvailabilityData"
_LIST_CHALLENGE = "api/public/map/downloads/listChallengeData"
_LIST_FUNDING = "api/public/fundingmap/downloads/listFundingData"
_LIST_READMES = "api/public/fundingmap/downloads/listReadmeFiles"
_LIST_GEOGRAPHIES = "api/public/fundingmap/downloads/listGeographyData"

# listAsOfDates is hit by every call that resolves "latest". One request per
# session is plenty -- the FCC publishes new vintages twice a year.
_releases_memo: list[dict[str, Any]] | None = None


def _frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a typed DataFrame from API rows."""
    import pandas as pd

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    dtypes = dtypes_for([str(c) for c in df.columns])
    for column, dtype in dtypes.items():
        try:
            df[column] = df[column].astype(dtype)
        except (TypeError, ValueError):
            logger.debug("Left catalog column %s as %s", column, df[column].dtype)
    return finalize(df)


def clear_release_cache() -> None:
    """Forget the memoized ``listAsOfDates`` response."""
    global _releases_memo
    _releases_memo = None


def _fetch_releases(refresh: bool = False) -> list[dict[str, Any]]:
    global _releases_memo
    if _releases_memo is None or refresh:
        _releases_memo = _client.get_json(_LIST_AS_OF_DATES)
    return _releases_memo


def releases(data_type: str | None = None, refresh: bool = False) -> pd.DataFrame:
    """Return the published "as of" dates for each data type.

    Columns: ``data_type``, ``as_of_date``.

    Parameters
    ----------
    data_type:
        Filter to one type, typically ``"availability"`` or ``"challenge"``.
    refresh:
        Re-request instead of using the memoized response.

    Examples
    --------
    >>> import bdcdata
    >>> bdcdata.catalog.releases("availability")   # doctest: +SKIP
    """
    rows = _fetch_releases(refresh=refresh)
    df = _frame(rows)
    if data_type is not None and not df.empty:
        df = df[df["data_type"].str.lower() == data_type.strip().lower()]
    return df.reset_index(drop=True)


def available_releases(data_type: str) -> list[str]:
    """Return the published release dates for *data_type* as ISO strings."""
    rows = _fetch_releases()
    wanted = data_type.strip().lower()
    return sorted(
        {
            str(row["as_of_date"])[:10]
            for row in rows
            if str(row.get("data_type", "")).lower() == wanted and row.get("as_of_date")
        }
    )


def resolve_releases(value: Any, data_type: str) -> list[str]:
    """Resolve ``"latest"``, ``"all"``, or explicit dates against what is published.

    Raises
    ------
    ValueError
        If a requested date has no published data, listing what does exist.
    """
    published = available_releases(data_type)
    if not published:
        raise ValueError(
            f"The API reports no published releases for data type {data_type!r}. "
            "Check bdcdata.catalog.releases()."
        )
    return normalize_release(value, available=published)


def availability_files(
    release: Any = "latest",
    *,
    category: str | None = None,
    subcategory: str | None = None,
    technology_type: str | None = None,
    speed_tier: str | None = None,
    state: Any = None,
) -> pd.DataFrame:
    """List the availability files published for one or more releases.

    Wraps ``listAvailabilityData/{as_of_date}``.

    Parameters
    ----------
    release:
        ``"latest"`` (default), ``"all"``, a date, or a list of dates.
    category:
        ``"Summary"``, ``"State"``, or ``"Provider"``.
    subcategory:
        Depends on *category*. For ``"State"``: ``"Provider List"``,
        ``"Location Coverage"``, ``"Hexagon Coverage"``, ``"Served-Unserved"``.
    technology_type:
        ``"Fixed Broadband"``, ``"Mobile Broadband"``, or ``"Mobile Voice"``.
    speed_tier:
        ``"35/3"`` or ``"7/1"``, for provider hexagon and raw coverage files.
    state:
        Optional client-side filter, accepting anything
        :func:`bdcdata.lookups.states` lists.

    Returns
    -------
    pandas.DataFrame
        One row per downloadable file, including ``file_id``, ``file_name``,
        ``record_count``, and a ``release`` column naming the vintage.
    """
    import pandas as pd

    dates = resolve_releases(release, "availability")
    params = {
        "category": category,
        "subcategory": subcategory,
        "technology_type": technology_type,
        "speed_tier": speed_tier,
    }

    frames = []
    for as_of_date in dates:
        rows = _client.get_json(f"{_LIST_AVAILABILITY}/{as_of_date}", params=params)
        df = _frame(rows)
        if not df.empty:
            df["release"] = as_of_date
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return _filter_states(combined, state)


def challenge_files(
    release: Any = "latest", *, category: str | None = None, state: Any = None
) -> pd.DataFrame:
    """List the challenge files published for one or more releases.

    Wraps ``listChallengeData/{as_of_date}``.

    Parameters
    ----------
    release:
        ``"latest"`` (default), ``"all"``, a date, or a list of dates.
    category:
        One of the exact strings in :func:`bdcdata.lookups.challenge_categories`,
        for example ``"Fixed Challenge - Resolved"``.
    state:
        Optional client-side filter.

    Returns
    -------
    pandas.DataFrame
        Columns ``file_id``, ``category``, ``state_fips``, ``state_name``,
        ``record_count``, plus a ``release`` column.
    """
    import pandas as pd

    dates = resolve_releases(release, "challenge")

    frames = []
    for as_of_date in dates:
        rows = _client.get_json(f"{_LIST_CHALLENGE}/{as_of_date}", params={"category": category})
        df = _frame(rows)
        if not df.empty:
            df["release"] = as_of_date
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return _filter_states(combined, state)


def funding_files(*, data_type: str | None = None, state: Any = None) -> pd.DataFrame:
    """List every file published on the Broadband Funding Map.

    Wraps ``listFundingData``. The endpoint takes no parameters, so *data_type*
    and *state* filter the result here.

    Parameters
    ----------
    data_type:
        ``"Program"``, ``"Project"``, or ``"State"``.
    state:
        Optional client-side filter.
    """
    rows = _client.get_json(_LIST_FUNDING)
    df = _frame(rows)
    if data_type is not None and not df.empty and "data_type" in df.columns:
        df = df[df["data_type"].str.lower() == data_type.strip().lower()]
    return _filter_states(df.reset_index(drop=True), state)


def readme_files() -> pd.DataFrame:
    """List the Broadband Funding Map readme files.

    Wraps ``listReadmeFiles``. Columns include ``program_id``, ``program_name``,
    ``ref_id``, and ``file_name``.
    """
    return _frame(_client.get_json(_LIST_READMES))


def geographies() -> pd.DataFrame:
    """List the geographies that have funding data available.

    Wraps ``listGeographyData``. Columns: ``geography_type``, ``geography_id``,
    ``geography_desc_full``.
    """
    return _frame(_client.get_json(_LIST_GEOGRAPHIES))


def _filter_states(df: pd.DataFrame, state: Any) -> pd.DataFrame:
    """Filter a catalog frame to the requested states, if any."""
    if state is None or df.empty or "state_fips" not in df.columns:
        return df
    wanted = normalize_states(state)
    if wanted is None:
        return df
    return df[df["state_fips"].isin(wanted)].reset_index(drop=True)

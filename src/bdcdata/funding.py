"""Broadband Funding Map data.

Which programs and projects are funding broadband where, and which locations
are still both unserved and unfunded.

    >>> import bdcdata
    >>> df = bdcdata.funding.unserved_unfunded(state="WA")   # doctest: +SKIP

The funding map is a separate system from the National Broadband Map, with its
own endpoints and its own file catalog. It has no "as of date" concept:
:func:`bdcdata.catalog.funding_files` lists everything currently published.

Field names here follow revision 6.0 of the funding download specification
(2026-03-16), which renamed most columns for clarity -- ``fund_ob`` became
``funding_obligated``, ``loc_sup`` became ``locations_supported``, and so on.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import _client, catalog
from ._fetch import download_frames, records
from ._normalize import normalize_states
from ._readers import read_csv_bytes
from .exceptions import BdcNotFoundError

if TYPE_CHECKING:
    import pandas as pd

__all__ = [
    "download_readme",
    "funded_locations",
    "programs",
    "projects",
    "projects_in_geography",
    "readmes",
    "unserved_unfunded",
]

logger = logging.getLogger("bdcdata")

_DOWNLOAD_GEOGRAPHY = "api/public/fundingmap/downloads/downloadGeographyData"
_DOWNLOAD_README = "api/public/fundingmap/downloads/downloadReadmeFile"

CATEGORY_FUNDING_DATA = "Funding Data"
CATEGORY_UNSERVED_UNFUNDED = "Unserved-Unfunded"
CATEGORY_FUNDED_LOCATIONS = "Funded Locations State"
CATEGORY_FUNDED_LOCATIONS_PROGRAM = "Funded Locations State Program"


def _stamp(row: dict[str, Any]) -> dict[str, Any]:
    """Carry catalog context onto the downloaded rows."""
    extra: dict[str, Any] = {}
    for column in ("agency_name", "program_name", "project_name", "state_fips"):
        if row.get(column) is not None:
            extra.setdefault(column, row[column])
    return extra


def _filter_files(
    files: pd.DataFrame,
    *,
    category: str | None = None,
    data_type: str | None = None,
    agency: str | None = None,
    program: str | None = None,
    states: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Filter the funding catalog. All matching is case-insensitive substring."""
    if files.empty:
        return []
    df = files

    if category is not None and "category" in df.columns:
        df = df[df["category"].str.lower() == category.lower()]
    if data_type is not None and "data_type" in df.columns:
        df = df[df["data_type"].str.lower() == data_type.lower()]
    if agency is not None and "agency_name" in df.columns:
        df = df[df["agency_name"].str.contains(agency, case=False, na=False)]
    if program is not None and "program_name" in df.columns:
        df = df[df["program_name"].str.contains(program, case=False, na=False)]
    if states is not None and "state_fips" in df.columns:
        df = df[df["state_fips"].isin(states)]

    return records(df)


def programs(
    agency: str | None = None,
    program: str | None = None,
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Program-level funding data submitted by agencies.

    Parameters
    ----------
    agency:
        Case-insensitive substring match on ``agency_name``, for example
        ``"Federal Communications Commission"`` or just ``"FCC"``.
    program:
        Case-insensitive substring match on ``program_name``.

    Returns
    -------
    pandas.DataFrame
        Columns include ``agency_name``, ``program_id``, ``program_name``,
        ``authorization_date``, ``funding_committed``, and ``funding_revised``.

    Notes
    -----
    There are thousands of published funding files. Filtering by *agency* or
    *program* is strongly recommended -- an unfiltered call downloads every
    program file the FCC publishes.

    Examples
    --------
    >>> import bdcdata
    >>> bdcdata.funding.programs(agency="Federal Communications")  # doctest: +SKIP
    """
    files = catalog.funding_files()
    rows = _filter_files(
        files, category=CATEGORY_FUNDING_DATA, data_type="Program", agency=agency, program=program
    )
    _warn_if_unfiltered(rows, agency, program, "programs")

    return download_frames(
        rows,
        data_type="funding",
        description=f"funding programs agency={agency!r} program={program!r}",
        cache=cache,
        progress=progress,
        extra_columns=_stamp,
    )


def projects(
    agency: str | None = None,
    program: str | None = None,
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Project-level funding data submitted by agencies.

    Parameters
    ----------
    agency:
        Case-insensitive substring match on ``agency_name``.
    program:
        Case-insensitive substring match on ``program_name``.

    Returns
    -------
    pandas.DataFrame
        Columns include ``project_id``, ``project_name``,
        ``funding_obligated``, ``funding_disbursed``, ``locations_planned``,
        and ``locations_supported``.
    """
    files = catalog.funding_files()
    rows = _filter_files(
        files, category=CATEGORY_FUNDING_DATA, data_type="Project", agency=agency, program=program
    )
    _warn_if_unfiltered(rows, agency, program, "projects")

    return download_frames(
        rows,
        data_type="funding",
        description=f"funding projects agency={agency!r} program={program!r}",
        cache=cache,
        progress=progress,
        extra_columns=_stamp,
    )


def unserved_unfunded(
    state: Any,
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Locations that are both unserved and unfunded.

    The headline BEAD-adjacent dataset: locations with no reported qualifying
    service and no enforceable funding commitment.

    Parameters
    ----------
    state:
        ``"WA"``, ``"Washington"``, ``53``, a list, or ``"all"``.

    Returns
    -------
    pandas.DataFrame
        One row per location, including ``location_id``, ``block_geoid``,
        ``h3_res8_id``, and the technology/speed buildout columns.

    Examples
    --------
    >>> import bdcdata
    >>> df = bdcdata.funding.unserved_unfunded(state="WA")  # doctest: +SKIP
    """
    states = normalize_states(state)
    files = catalog.funding_files()
    rows = _filter_files(files, category=CATEGORY_UNSERVED_UNFUNDED, states=states)

    return download_frames(
        rows,
        data_type="funding",
        description=f"unserved/unfunded state={state!r}",
        cache=cache,
        progress=progress,
        extra_columns=_stamp,
    )


def funded_locations(
    state: Any,
    by_program: bool = False,
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Locations covered by an enforceable funding commitment.

    Parameters
    ----------
    state:
        As in :func:`unserved_unfunded`.
    by_program:
        ``False`` returns one row per funded location. ``True`` returns the
        per-program breakdown, so a location funded by two programs appears
        twice.

    Notes
    -----
    Both exports were added in the 2026-06-08 API specification revision.
    """
    states = normalize_states(state)
    category = CATEGORY_FUNDED_LOCATIONS_PROGRAM if by_program else CATEGORY_FUNDED_LOCATIONS
    files = catalog.funding_files()
    rows = _filter_files(files, category=category, states=states)

    if not rows:
        logger.warning(
            "No %r files published. These exports were added in the June 2026 "
            "specification revision.",
            category,
        )

    return download_frames(
        rows,
        data_type="funding",
        description=f"{category} state={state!r}",
        cache=cache,
        progress=progress,
        extra_columns=_stamp,
    )


def projects_in_geography(
    geography_type: str | None = None,
    geography_id: str | None = None,
    *,
    cache: bool | None = None,
) -> pd.DataFrame:
    """Funded projects within one geography.

    Parameters
    ----------
    geography_type:
        ``"state"``, ``"county"``, ``"cdist"``, ``"place"``, ``"tribal"``, or
        ``"cbsa"``.
    geography_id:
        The identifier for that geography, for example ``"36001"`` for Albany
        County, NY. See :func:`bdcdata.catalog.geographies` for valid pairs.

    Returns
    -------
    pandas.DataFrame
        One row per project in the geography.

    Notes
    -----
    Unlike the other funding endpoints this one returns a plain CSV rather
    than a ZIP archive.

    Examples
    --------
    >>> import bdcdata
    >>> bdcdata.funding.projects_in_geography("county", "36001")  # doctest: +SKIP
    """
    data = _client.get_bytes(
        _DOWNLOAD_GEOGRAPHY,
        params={"geography_type": geography_type, "geography_id": geography_id},
        cache=cache,
        cache_label=f"geography_{geography_type}_{geography_id}",
    )
    return read_csv_bytes(data, source=f"projects in {geography_type}={geography_id}")


def readmes() -> pd.DataFrame:
    """List the readme files published for funding programs.

    Returns
    -------
    pandas.DataFrame
        Columns ``program_id``, ``program_name``, ``ref_id``, ``file_name``.
        Pass ``ref_id`` to :func:`download_readme`.
    """
    return catalog.readme_files()


def download_readme(ref_id: str, dest: str | Path = ".") -> Path:
    """Download one funding program readme (a PDF) to disk.

    Parameters
    ----------
    ref_id:
        The ``ref_id`` from :func:`readmes`.
    dest:
        A directory to write into, or a full file path.

    Returns
    -------
    pathlib.Path
        Where the file was written.

    Raises
    ------
    BdcNotFoundError
        If no readme exists for *ref_id*.
    """
    if not ref_id or not str(ref_id).strip():
        raise ValueError("ref_id is required. Get one from bdcdata.funding.readmes().")

    data = _client.get_bytes(f"{_DOWNLOAD_README}/{ref_id}", cache_label=f"readme_{ref_id}")
    if not data:
        raise BdcNotFoundError(
            f"No readme returned for ref_id={ref_id!r}. "
            "Check bdcdata.funding.readmes() for current values."
        )

    target = Path(dest).expanduser()
    if target.is_dir() or not target.suffix:
        target.mkdir(parents=True, exist_ok=True)
        target = target / f"readme_{ref_id}.pdf"
    else:
        target.parent.mkdir(parents=True, exist_ok=True)

    target.write_bytes(data)
    logger.info("Wrote %s (%d bytes)", target, len(data))
    return target


def _warn_if_unfiltered(
    rows: list[dict[str, Any]], agency: str | None, program: str | None, what: str
) -> None:
    if agency is None and program is None and len(rows) > 50:
        logger.warning(
            "No agency or program filter given: this will download %d %s files. "
            "Narrow it with agency= or program=, or browse "
            "bdcdata.catalog.funding_files() first.",
            len(rows),
            what,
        )

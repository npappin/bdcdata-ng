"""Challenge data.

Challenges filed against the location Fabric, against fixed availability, and
against mobile availability -- plus the verification and audit processes the
FCC added later.

    >>> import bdcdata
    >>> df = bdcdata.challenges.fixed(state="WA", status="resolved")   # doctest: +SKIP

Challenge files are published monthly, so their releases are a different (and
much longer) list than availability releases. ``release="latest"`` resolves
against the challenge list, not the availability one.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from . import catalog
from ._fetch import download_frames, records
from ._normalize import normalize_states
from .lookups import _CHALLENGE_CATEGORIES

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["audit", "fabric", "fixed", "get", "mobile", "verification"]

logger = logging.getLogger("bdcdata")

Status = Literal["in_progress", "resolved", "cumulative"]

_BY_KIND_STATUS = {(kind, status): category for category, kind, status in _CHALLENGE_CATEGORIES}
_STATUS_ALIASES = {
    "in progress": "in_progress",
    "in-progress": "in_progress",
    "inprogress": "in_progress",
    "open": "in_progress",
    "pending": "in_progress",
    "closed": "resolved",
    "complete": "resolved",
    "completed": "resolved",
    "total": "cumulative",
}


def _resolve_category(kind: str, status: str) -> str:
    """Map a (kind, status) pair to the exact API category string."""
    normalized = _STATUS_ALIASES.get(status.strip().lower(), status.strip().lower())
    category = _BY_KIND_STATUS.get((kind, normalized))
    if category is not None:
        return category

    available = sorted(s for k, s in _BY_KIND_STATUS if k == kind)
    if not available:
        kinds = sorted({k for k, _ in _BY_KIND_STATUS})
        raise ValueError(f"{kind!r} is not a challenge kind. Valid kinds: {', '.join(kinds)}.")
    raise ValueError(
        f"status={status!r} is not available for {kind} challenges. "
        f"Valid: {', '.join(repr(s) for s in available)}. "
        "See bdcdata.lookups.challenge_categories()."
    )


def _stamp(row: dict[str, Any]) -> dict[str, Any]:
    """Stamp catalog context onto each file's rows.

    Challenge CSVs carry no state or vintage column of their own, so pulling
    several states at once would otherwise give a frame you cannot split
    apart again.
    """
    extra: dict[str, Any] = {}
    for column in ("release", "state_fips", "category"):
        if row.get(column) is not None:
            extra[column] = row[column]
    return extra


def get(
    category: str,
    state: Any = "all",
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Download challenge files by exact API category string.

    The escape hatch. The FCC added six new categories in 2025 alone, so if
    :func:`bdcdata.lookups.challenge_categories` is behind what the API
    offers, look the current value up with
    :func:`bdcdata.catalog.challenge_files` and pass it here.

    Parameters
    ----------
    category:
        An exact category string, for example ``"Fixed Challenge - Resolved"``.
    state:
        As in :func:`bdcdata.availability.fixed`. Defaults to every state.
    release:
        ``"latest"`` (default), a date, ``"all"``, or a list.

    Examples
    --------
    >>> import bdcdata
    >>> bdcdata.challenges.get("Fabric Challenge - Resolved", state="WA")  # doctest: +SKIP
    """
    states = normalize_states(state)
    releases = catalog.resolve_releases(release, "challenge")

    files = catalog.challenge_files(release=releases, category=category)
    if not files.empty and states is not None and "state_fips" in files.columns:
        files = files[files["state_fips"].isin(states)]
    rows = records(files)

    if not rows:
        logger.warning(
            "No challenge files published for category=%r, state=%r, release=%s.",
            category,
            state,
            ", ".join(releases),
        )

    return download_frames(
        rows,
        data_type="challenge",
        description=f"{category} state={state!r} release={','.join(releases)}",
        cache=cache,
        progress=progress,
        extra_columns=_stamp,
    )


def fabric(
    state: Any = "all",
    status: Status = "in_progress",
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Challenges to the Broadband Serviceable Location Fabric.

    Parameters
    ----------
    state:
        As in :func:`bdcdata.availability.fixed`.
    status:
        ``"in_progress"`` for challenges not yet adjudicated, ``"resolved"``
        for those that have been.
    release:
        As in :func:`get`.

    Returns
    -------
    pandas.DataFrame
        In-progress files carry ``challenge_id``, ``fabric_vintage``,
        ``category_code``, ``category_code_desc``, ``location_id``, and
        ``location_state``. Resolved files add the address fields and the
        adjudication outcome.
    """
    return get(
        _resolve_category("fabric", status),
        state=state,
        release=release,
        cache=cache,
        progress=progress,
    )


def fixed(
    state: Any = "all",
    status: Status = "in_progress",
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Challenges to fixed broadband availability data.

    Parameters
    ----------
    state:
        As in :func:`bdcdata.availability.fixed`.
    status:
        ``"in_progress"``, ``"resolved"``, or ``"cumulative"`` for the
        running count by provider.
    release:
        As in :func:`get`.

    Returns
    -------
    pandas.DataFrame
        Columns include ``challenge_id``, ``location_id``, ``location_state``,
        ``data_vintage``, ``frn``, ``provider_id``, ``technology``,
        ``category_code``, and the relevant dates.
    """
    return get(
        _resolve_category("fixed", status),
        state=state,
        release=release,
        cache=cache,
        progress=progress,
    )


def mobile(
    state: Any = "all",
    status: Status = "in_progress",
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Challenges to mobile broadband availability data.

    Parameters
    ----------
    state:
        As in :func:`bdcdata.availability.fixed`.
    status:
        ``"in_progress"`` or ``"resolved"``.
    release:
        As in :func:`get`.

    Returns
    -------
    pandas.DataFrame
        Columns include ``challenge_id``, ``challenge_date``,
        ``h3_resolution``, and ``h3_cell_id``.
    """
    return get(
        _resolve_category("mobile", status),
        state=state,
        release=release,
        cache=cache,
        progress=progress,
    )


def verification(
    kind: Literal["fixed", "mobile"] = "mobile",
    state: Any = "all",
    status: Status = "in_progress",
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Verification requests, which are distinct from challenges.

    The FCC added these categories in the 2025-09-30 API specification
    revision.

    Parameters
    ----------
    kind:
        ``"fixed"`` or ``"mobile"``.
    status:
        ``"in_progress"`` or ``"resolved"``.
    """
    if kind not in ("fixed", "mobile"):
        raise ValueError(f"kind must be 'fixed' or 'mobile', got {kind!r}")
    return get(
        _resolve_category(f"{kind}_verification", status),
        state=state,
        release=release,
        cache=cache,
        progress=progress,
    )


def audit(
    state: Any = "all",
    status: Status = "in_progress",
    release: Any = "latest",
    *,
    cache: bool | None = None,
    progress: bool = False,
) -> pd.DataFrame:
    """Mobile audit data.

    The FCC publishes audits for mobile only; there is no fixed equivalent.

    Parameters
    ----------
    status:
        ``"in_progress"`` or ``"resolved"``.
    """
    return get(
        _resolve_category("mobile_audit", status),
        state=state,
        release=release,
        cache=cache,
        progress=progress,
    )

"""Downloading a set of catalog rows and stacking them into one DataFrame.

Shared by :mod:`bdcdata.availability`, :mod:`bdcdata.challenges`, and
:mod:`bdcdata.funding` so that size warnings, progress reporting, cache
behavior, and error messages are identical everywhere.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Literal

from . import _client
from ._readers import read_csv_archive, read_gis_archive

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["GIS_GEOPACKAGE", "GIS_SHAPEFILE", "download_frames", "records"]

logger = logging.getLogger("bdcdata")

GIS_SHAPEFILE = "1"
GIS_GEOPACKAGE = "2"

_MAP_DOWNLOAD = "api/public/map/downloads/downloadFile"
_FUNDING_DOWNLOAD = "api/public/fundingmap/downloads/downloadFile"

# Downloading this many rows is worth a heads-up before it starts.
_LARGE_RESULT_ROWS = 5_000_000


def _progress(items: list[Any], enabled: bool, description: str) -> Iterable[Any]:
    if not enabled:
        return items
    try:
        from tqdm.auto import tqdm
    except ImportError:
        logger.info("Install 'bdcdata[progress]' for a progress bar.")
        return items
    return tqdm(items, desc=description, unit="file")


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Return a catalog frame's rows as dictionaries.

    ``DataFrame.to_dict("records")`` is typed as ``list[dict[Hashable, Any]]``
    because column labels need not be strings. Catalog columns always are, so
    this narrows the type once here instead of at every call site.
    """
    if df.empty:
        return []
    return [{str(key): value for key, value in row.items()} for row in df.to_dict("records")]


def _warn_if_large(rows: list[dict[str, Any]], description: str) -> None:
    """Log the real size of what is about to be downloaded."""
    total = 0
    for row in rows:
        count = row.get("record_count")
        if count is None:
            continue
        try:
            total += int(count)
        except (TypeError, ValueError):
            continue

    if len(rows) > 1 or total:
        logger.info(
            "Downloading %d file(s) for %s (%s rows).",
            len(rows),
            description,
            f"{total:,}" if total else "unknown",
        )
    if total >= _LARGE_RESULT_ROWS:
        logger.warning(
            "This will load about %s rows into memory across %d file(s). "
            "Consider narrowing the state or technology, or enabling the cache "
            "with bdcdata.set_cache(True) so a retry is free.",
            f"{total:,}",
            len(rows),
        )


def download_frames(
    rows: list[dict[str, Any]],
    *,
    data_type: Literal["availability", "challenge", "funding"],
    description: str,
    cache: bool | None = None,
    progress: bool = False,
    gis: bool = False,
    extra_columns: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    username: str | None = None,
    token: str | None = None,
) -> pd.DataFrame:
    """Download each catalog row and concatenate the results.

    Parameters
    ----------
    rows:
        Catalog records, each with at least ``file_id``.
    data_type:
        Which download endpoint to use.
    description:
        Human-readable summary of the request, used in logs and errors.
    gis:
        Read the GIS attribute table instead of a CSV.
    extra_columns:
        Called per row; the returned mapping is added as columns to that
        file's frame. Used to stamp on ``release``, ``state_fips``, and so on,
        which the files themselves do not always carry.

    Returns
    -------
    pandas.DataFrame
        All files stacked. Empty (rather than an error) when *rows* is empty.
    """
    import pandas as pd

    if not rows:
        logger.warning("No files published for %s; returning an empty DataFrame.", description)
        return pd.DataFrame()

    _warn_if_large(rows, description)
    reader = read_gis_archive if gis else read_csv_archive

    # Accumulate and concatenate once. Concatenating inside the loop is
    # quadratic, which matters at 50 states.
    frames: list[pd.DataFrame] = []

    for row in _progress(rows, progress, description):
        file_id = row.get("file_id")
        if file_id is None:
            raise ValueError(f"Catalog row for {description} has no file_id: {row}")

        path = _download_path(data_type, str(file_id), gis=gis)
        label = row.get("file_name") or f"{data_type}_{file_id}"
        source = f"{label} (file_id={file_id})"

        data = _client.get_bytes(
            path,
            cache=cache,
            cache_label=str(label),
            username=username,
            token=token,
        )
        df = reader(data, source=source)

        if extra_columns is not None:
            for column, value in extra_columns(row).items():
                df[column] = value

        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    logger.info("Loaded %s rows for %s.", f"{len(combined):,}", description)
    return combined


def _download_path(data_type: str, file_id: str, gis: bool) -> str:
    """Build the download path for a file.

    The map endpoint is ``downloadFile/{data_type}/{file_id}/{file_type}``,
    where ``file_type`` is only meaningful for GIS downloads. The funding map
    has its own endpoint and takes no data type.
    """
    if data_type == "funding":
        return f"{_FUNDING_DOWNLOAD}/{file_id}"
    if gis:
        return f"{_MAP_DOWNLOAD}/{data_type}/{file_id}/{GIS_SHAPEFILE}"
    return f"{_MAP_DOWNLOAD}/{data_type}/{file_id}"

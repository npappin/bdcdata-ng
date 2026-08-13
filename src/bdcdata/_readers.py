"""Turning downloaded archives into DataFrames.

BDC downloads are ZIP archives containing either a single CSV or a set of GIS
files (ESRI Shapefile or GeoPackage). Both paths land on the same thing: a
pandas DataFrame with types from :mod:`bdcdata._schemas`.
"""

from __future__ import annotations

import io
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from ._schemas import dtypes_for, finalize
from .exceptions import BdcDataError, BdcOptionalDependencyError

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["read_csv_archive", "read_csv_bytes", "read_gis_archive", "list_archive"]

logger = logging.getLogger("bdcdata")

_GIS_SUFFIXES = (".shp", ".gpkg")


def _open_archive(data: bytes, source: str) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        preview = data[:200]
        # A plain-text body here usually means the API returned an error page
        # with a 200 status.
        raise BdcDataError(
            f"{source} did not contain a ZIP archive ({exc}). "
            f"First bytes: {preview!r}"
        ) from exc


def list_archive(data: bytes, source: str = "download") -> list[str]:
    """Return the names of the files inside a downloaded archive."""
    with _open_archive(data, source) as archive:
        return [item.filename for item in archive.infolist() if not item.is_dir()]


def _pick_member(names: list[str], suffixes: tuple[str, ...], source: str) -> str:
    """Choose the archive member to read.

    Selects by suffix rather than taking the first entry, so a ``__MACOSX``
    folder, a readme, or a sidecar file cannot be mistaken for the data.
    """
    candidates = [
        name
        for name in names
        if name.lower().endswith(suffixes)
        and not Path(name).name.startswith((".", "__"))
        and "__MACOSX" not in name
    ]
    if not candidates:
        raise BdcDataError(
            f"{source} contained no {' or '.join(suffixes)} file. "
            f"Archive contents: {names}"
        )
    if len(candidates) > 1:
        # Deterministic and explainable: shortest path, then alphabetical.
        candidates.sort(key=lambda n: (len(n), n))
        logger.debug("%s has %d candidates; reading %s", source, len(candidates), candidates[0])
    return candidates[0]


def read_csv_archive(data: bytes, source: str = "download") -> pd.DataFrame:
    """Read the CSV inside a downloaded ZIP archive.

    Column types come from :mod:`bdcdata._schemas`; anything unrecognized is
    inferred with the pyarrow backend.
    """
    import pandas as pd

    with _open_archive(data, source) as archive:
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        member = _pick_member(names, (".csv", ".txt"), source)
        logger.debug("Reading %s from %s", member, source)

        # Read the header alone first so dtypes are only declared for columns
        # that actually exist. Cheap, and it keeps the type registry decoupled
        # from any single file layout.
        with archive.open(member) as handle:
            header = pd.read_csv(handle, nrows=0)
        dtypes = dtypes_for([str(c) for c in header.columns])

        with archive.open(member) as handle:
            try:
                df = pd.read_csv(handle, dtype=dtypes, dtype_backend="pyarrow")
            except (ValueError, pd.errors.ParserError) as exc:
                raise BdcDataError(f"Could not parse {member} from {source}: {exc}") from exc

    return finalize(df)


def read_csv_bytes(data: bytes, source: str = "download") -> pd.DataFrame:
    """Read a bare (unzipped) CSV response.

    Most endpoints return a ZIP, but ``downloadGeographyData`` returns the CSV
    directly.
    """
    import pandas as pd

    if data[:2] == b"PK":
        # It is actually a ZIP -- read it properly rather than producing
        # nonsense from the compressed bytes.
        return read_csv_archive(data, source=source)

    try:
        header = pd.read_csv(io.BytesIO(data), nrows=0)
        dtypes = dtypes_for([str(c) for c in header.columns])
        df = pd.read_csv(io.BytesIO(data), dtype=dtypes, dtype_backend="pyarrow")
    except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise BdcDataError(
            f"Could not parse {source} as CSV: {exc}. First bytes: {data[:200]!r}"
        ) from exc
    return finalize(df)


def read_gis_archive(data: bytes, source: str = "download") -> pd.DataFrame:
    """Read the attribute table of the GIS file inside a downloaded archive.

    Geometry is deliberately **not** read. The mobile coverage files identify
    each hexagon by ``h3_res9_id``, which is enough to join to geometry later
    without making geopandas a dependency of this package.

    Raises
    ------
    BdcOptionalDependencyError
        If ``pyogrio`` is not installed.
    """
    try:
        import pyogrio
    except ImportError as exc:
        raise BdcOptionalDependencyError(
            package="pyogrio",
            extra="mobile",
            feature="Reading mobile coverage files",
        ) from exc

    import pandas as pd

    with tempfile.TemporaryDirectory(prefix="bdcdata-") as tmpdir:
        root = Path(tmpdir)
        with _open_archive(data, source) as archive:
            # A shapefile is several files that must sit together on disk, so
            # the whole archive is extracted rather than a single member.
            archive.extractall(root)
            names = [item.filename for item in archive.infolist() if not item.is_dir()]

        member = _pick_member(names, _GIS_SUFFIXES, source)
        logger.debug("Reading attributes from %s in %s", member, source)

        try:
            table = pyogrio.read_dataframe(root / member, read_geometry=False)
        except Exception as exc:  # pyogrio raises a variety of driver errors
            raise BdcDataError(f"Could not read {member} from {source}: {exc}") from exc

    df = pd.DataFrame(table)
    dtypes = dtypes_for([str(c) for c in df.columns])
    for column, dtype in dtypes.items():
        try:
            df[column] = df[column].astype(dtype)
        except (TypeError, ValueError):
            # Driver-supplied types are usually right already; never lose data
            # to a failed cast.
            logger.debug("Left %s as %s", column, df[column].dtype)
    return finalize(df)

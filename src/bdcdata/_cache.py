"""On-disk cache for downloaded archives.

Off by default. When enabled, files land in ``./bdc_cache`` relative to the
working directory. Cached entries are the raw bytes the FCC returned, so a
cache hit skips both the download and the rate limiter.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from .config import get_cache_settings

__all__ = ["cache_info", "cache_key", "clear_cache", "read_cached", "write_cached"]

logger = logging.getLogger("bdcdata")

SUFFIX = ".bdccache"
"""Distinctive suffix so :func:`clear_cache` can never delete a user's own files."""

_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")


def cache_key(url: str, label: str | None = None) -> str:
    """Build a filename for a cached download.

    The URL is hashed so the key is unique and filesystem-safe; *label* (when
    the catalog gives us a real file name) is prefixed so a human can tell what
    is in the cache directory by looking at it.
    """
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    if label:
        slug = _SLUG_RE.sub("_", label).strip("_")[:80]
        if slug:
            return f"{slug}-{digest}{SUFFIX}"
    return f"{digest}{SUFFIX}"


def _entry_path(key: str) -> Path:
    """Where *key* lives on disk.

    Deliberately ignores the enabled flag: whether to use the cache at all is
    decided by the caller, which also honors a per-call ``cache=`` override.
    Checking the global flag here as well would silently defeat that override.
    """
    return get_cache_settings()[1] / key


def read_cached(key: str) -> bytes | None:
    """Return cached bytes for *key*, or ``None`` on a miss."""
    path = _entry_path(key)
    if not path.is_file():
        return None
    try:
        data = path.read_bytes()
    except OSError as exc:
        # A damaged cache should never be fatal -- fall through to the network.
        logger.warning("Could not read cache entry %s (%s); refetching.", path, exc)
        return None
    logger.debug("Cache hit: %s (%d bytes)", path.name, len(data))
    return data


def write_cached(key: str, data: bytes) -> None:
    """Store *data* under *key*.

    Gating is the caller's job -- see :func:`_entry_path`.
    """
    path = _entry_path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp name then rename, so an interrupted run cannot leave
        # a truncated archive that looks like a valid cache hit.
        tmp = path.with_suffix(path.suffix + ".partial")
        tmp.write_bytes(data)
        tmp.replace(path)
    except OSError as exc:
        logger.warning("Could not write cache entry %s (%s); continuing.", path, exc)
        return
    logger.debug("Cached %s (%d bytes)", path.name, len(data))


def cache_info() -> dict[str, object]:
    """Describe the current cache.

    Returns
    -------
    dict
        Keys ``enabled``, ``path``, ``files``, and ``bytes``.

    Examples
    --------
    >>> import bdcdata
    >>> bdcdata.cache_info()["enabled"]
    False
    """
    enabled, root = get_cache_settings()
    files = list(root.glob(f"*{SUFFIX}")) if root.is_dir() else []
    return {
        "enabled": enabled,
        "path": str(root),
        "files": len(files),
        "bytes": sum(f.stat().st_size for f in files),
    }


def clear_cache() -> int:
    """Delete cached downloads and return the number of files removed.

    Only files bdcdata wrote (those ending in ``.bdccache``) are touched, so
    pointing the cache at a directory with other contents is safe.
    """
    _, root = get_cache_settings()
    if not root.is_dir():
        return 0
    removed = 0
    for entry in list(root.glob(f"*{SUFFIX}")) + list(root.glob(f"*{SUFFIX}.partial")):
        try:
            entry.unlink()
        except OSError as exc:
            logger.warning("Could not delete %s (%s)", entry, exc)
        else:
            removed += 1
    logger.info("Removed %d cached file(s) from %s", removed, root)
    return removed

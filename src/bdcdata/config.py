"""Package-wide settings.

Everything here is resolved lazily, at the moment it is used. Importing
bdcdata reads no environment variables, touches no files, and opens no
sockets.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "set_base_url",
    "get_base_url",
    "set_cache",
    "get_cache_settings",
    "set_timeout",
    "options",
]

logger = logging.getLogger("bdcdata")

DEFAULT_BASE_URL = "https://bdc.fcc.gov"
"""Documented in the BDC Public Data API specification (rev 1.7, 2026-06-08).

The older ``broadbandmap.fcc.gov`` host still answers today, but every sample
in the current spec uses this one.
"""

DEFAULT_CACHE_DIRNAME = "bdc_cache"
RATE_LIMIT_PER_MINUTE = 10
"""Documented on every BDC endpoint. Not configurable upward on purpose."""


@dataclass
class Options:
    """Mutable package settings. Use the module-level setters to change these."""

    base_url: str | None = None
    cache_enabled: bool = False
    cache_path: Path | None = None
    timeout: float = 300.0
    max_retries: int = 3
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


options = Options()


def get_base_url() -> str:
    """Return the API base URL.

    Resolution order: :func:`set_base_url` -> ``BDC_BASE_URL`` -> the default.
    """
    if options.base_url is not None:
        return options.base_url
    return os.environ.get("BDC_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def set_base_url(url: str | None) -> None:
    """Point bdcdata at a different host.

    Mostly useful for testing against a mock server. Pass ``None`` to restore
    the default.
    """
    options.base_url = url.rstrip("/") if url else None


def set_cache(enabled: bool = True, path: str | Path | None = None) -> None:
    """Turn the download cache on or off.

    The cache is **off by default**. When enabled, downloaded archives are
    written to ``./bdc_cache`` relative to the current working directory
    unless *path* says otherwise.

    Turning this on is worth it if you re-run the same query: the FCC allows
    10 calls per minute, and availability archives run to hundreds of
    megabytes.

    Parameters
    ----------
    enabled:
        Whether to read and write cached downloads.
    path:
        Directory to store cached files in. Created on first write.

    Examples
    --------
    >>> import bdcdata
    >>> bdcdata.set_cache(True)
    >>> bdcdata.set_cache(True, path="~/bdc-downloads")
    """
    options.cache_enabled = bool(enabled)
    if path is not None:
        options.cache_path = Path(path).expanduser()


def get_cache_settings() -> tuple[bool, Path]:
    """Return ``(enabled, path)`` for the download cache."""
    path = options.cache_path
    if path is None:
        # Resolved at call time, not import time, so that changing directory
        # between import and use does what the user expects.
        path = Path.cwd() / DEFAULT_CACHE_DIRNAME
    return options.cache_enabled, path


def set_timeout(seconds: float) -> None:
    """Set the per-request timeout in seconds (default 300).

    Availability archives are large; the default is generous on purpose.
    """
    if seconds <= 0:
        raise ValueError("timeout must be a positive number of seconds")
    options.timeout = float(seconds)

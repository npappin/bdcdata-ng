"""bdcdata -- work with FCC Broadband Data Collection data in pandas.

Importing this package does nothing but define names: no network calls, no
files read, no logging configured. Credentials are resolved the first time you
actually ask for data.

Quick start::

    import bdcdata

    bdcdata.set_credentials(username="you@example.com", token="...")
    df = bdcdata.availability.fixed(state="WA", technology="fiber")

See ``bdcdata.lookups`` for the state and technology codes, and
``bdcdata.catalog`` for what the FCC currently publishes.
"""

from __future__ import annotations

import logging

# A NullHandler and nothing else. The host application owns logging config --
# bdcdata never calls basicConfig, never adds a stream handler, and never
# writes a log file.
logging.getLogger(__name__).addHandler(logging.NullHandler())

from . import availability, catalog, challenges, funding, lookups  # noqa: E402
from ._cache import cache_info, clear_cache  # noqa: E402
from ._client import check_credentials, reset_session  # noqa: E402
from .config import get_cache_settings, set_base_url, set_cache, set_timeout  # noqa: E402
from .credentials import (  # noqa: E402
    clear_credentials,
    have_credentials,
    load_dotenv,
    set_credentials,
)
from .exceptions import (  # noqa: E402
    BdcAuthError,
    BdcCredentialsMissing,
    BdcDataError,
    BdcError,
    BdcNotFoundError,
    BdcOptionalDependencyError,
    BdcRateLimitError,
    BdcServerError,
    BdcUnprocessableError,
)

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("bdcdata")
except PackageNotFoundError:  # pragma: no cover - running from a bare checkout
    __version__ = "0.0.0.dev0"

# Grouped by purpose rather than sorted alphabetically: this list doubles as
# the tour of the package, and reading it top to bottom is how you learn what
# is available.
__all__ = [  # noqa: RUF022
    "__version__",
    # submodules
    "availability",
    "catalog",
    "challenges",
    "funding",
    "lookups",
    # credentials
    "set_credentials",
    "clear_credentials",
    "load_dotenv",
    "have_credentials",
    "check_credentials",
    # settings
    "set_cache",
    "get_cache_settings",
    "cache_info",
    "clear_cache",
    "set_base_url",
    "set_timeout",
    "reset_session",
    # exceptions
    "BdcError",
    "BdcAuthError",
    "BdcCredentialsMissing",
    "BdcDataError",
    "BdcNotFoundError",
    "BdcOptionalDependencyError",
    "BdcRateLimitError",
    "BdcServerError",
    "BdcUnprocessableError",
]

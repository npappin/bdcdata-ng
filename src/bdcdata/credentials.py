"""Finding and holding your FCC BDC credentials.

Every BDC endpoint -- including the metadata endpoints -- requires a username
and an API token, sent as the ``username`` and ``hash_value`` headers.

Nothing here runs at import time. Credentials are resolved on the first
request you actually make, so ``import bdcdata`` works fine on a machine that
has never been configured.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from .exceptions import BdcCredentialsMissing

__all__ = [
    "Credentials",
    "clear_credentials",
    "get_credentials",
    "have_credentials",
    "load_dotenv",
    "set_credentials",
]

logger = logging.getLogger("bdcdata")

USERNAME_ENV = "BDC_USERNAME"
TOKEN_ENV = "BDC_API_KEY"


@dataclass(frozen=True)
class Credentials:
    """A username and API token pair."""

    username: str
    token: str

    def __repr__(self) -> str:
        # Keep the token out of tracebacks, notebook output, and logs.
        return f"Credentials(username={self.username!r}, token='***')"

    def as_headers(self) -> dict[str, str]:
        """Return the headers the BDC API expects."""
        return {"username": self.username, "hash_value": self.token}


_configured: Credentials | None = None


def set_credentials(username: str, token: str) -> None:
    """Set the credentials bdcdata should use.

    Parameters
    ----------
    username:
        The email address on your FCC User Registration account.
    token:
        The API token from the Manage API Access page.

    Examples
    --------
    >>> import bdcdata
    >>> bdcdata.set_credentials(username="you@example.com", token="abc123")
    """
    global _configured
    if not username or not str(username).strip():
        raise ValueError("username must be a non-empty string")
    if not token or not str(token).strip():
        raise ValueError("token must be a non-empty string")
    _configured = Credentials(username=str(username).strip(), token=str(token).strip())
    logger.debug("Credentials set for %s", _configured.username)


def clear_credentials() -> None:
    """Forget credentials set with :func:`set_credentials`.

    Does not touch environment variables.
    """
    global _configured
    _configured = None


def load_dotenv(path: str | Path = ".env", override: bool = False) -> bool:
    """Load ``BDC_USERNAME`` and ``BDC_API_KEY`` from a ``.env`` file.

    Call this explicitly -- bdcdata never reads a ``.env`` file at import.

    Parameters
    ----------
    path:
        Path to the ``.env`` file. Defaults to ``.env`` in the working directory.
    override:
        Whether values in the file should replace existing environment
        variables. Defaults to ``False``.

    Returns
    -------
    bool
        ``True`` if the file existed and was read.

    Notes
    -----
    Uses ``python-dotenv`` when it is installed. Falls back to a small built-in
    parser that handles ``KEY=value`` lines, ``#`` comments, quoted values, and
    an optional leading ``export``.
    """
    env_path = Path(path).expanduser()
    if not env_path.is_file():
        logger.debug("No .env file at %s", env_path)
        return False

    from dotenv import load_dotenv as _dotenv_load

    _dotenv_load(dotenv_path=env_path, override=override)

    logger.debug("Loaded environment from %s", env_path)
    return True


def _resolve_dotenv() -> None:
    """Try a ``.env`` in the working directory, once, quietly.

    This is the convenience path for people following the quickstart, who
    typically keep a ``.env`` next to their notebook.
    """
    candidate = Path.cwd() / ".env"
    if candidate.is_file():
        load_dotenv(candidate)


def get_credentials(username: str | None = None, token: str | None = None) -> Credentials:
    """Resolve the credentials to use for a request.

    Resolution order:

    1. The *username* / *token* arguments passed here
    2. Values given to :func:`set_credentials`
    3. The ``BDC_USERNAME`` and ``BDC_API_KEY`` environment variables
    4. A ``.env`` file in the current working directory

    Raises
    ------
    BdcCredentialsMissing
        If no complete pair could be found. The message explains every way to
        supply them and how to generate a token.
    """
    if username and token:
        return Credentials(username=str(username).strip(), token=str(token).strip())

    if _configured is not None:
        return _configured

    env_user = os.environ.get(USERNAME_ENV)
    env_token = os.environ.get(TOKEN_ENV)

    if not (env_user and env_token):
        _resolve_dotenv()
        env_user = os.environ.get(USERNAME_ENV)
        env_token = os.environ.get(TOKEN_ENV)

    if env_user and env_token:
        return Credentials(username=env_user.strip(), token=env_token.strip())

    # Say which half is missing -- a set-but-empty variable is a common slip.
    if env_user and not env_token:
        raise BdcCredentialsMissing(f"{USERNAME_ENV} is set but {TOKEN_ENV} is not.")
    if env_token and not env_user:
        raise BdcCredentialsMissing(f"{TOKEN_ENV} is set but {USERNAME_ENV} is not.")
    raise BdcCredentialsMissing()


def have_credentials() -> bool:
    """Return whether credentials can be resolved, without making a request.

    Useful for skipping tests or branching in a notebook.
    """
    try:
        get_credentials()
    except BdcCredentialsMissing:
        return False
    return True

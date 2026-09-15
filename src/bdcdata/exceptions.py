"""Exceptions raised by bdcdata.

Every exception carries a message that tells the user what to do next. A
traceback ending in ``BdcAuthError`` should be enough to fix the problem
without opening the FCC documentation.
"""

from __future__ import annotations

__all__ = [
    "BdcAuthError",
    "BdcCredentialsMissing",
    "BdcDataError",
    "BdcError",
    "BdcNotFoundError",
    "BdcOptionalDependencyError",
    "BdcRateLimitError",
    "BdcServerError",
    "BdcUnprocessableError",
]


TOKEN_INSTRUCTIONS = (
    "To get a username and API token:\n"
    "  1. Log in at https://broadbandmap.fcc.gov/login with your FCC User "
    "Registration account.\n"
    "  2. Click your username in the top right, then 'Manage API Access'.\n"
    "  3. Click 'Generate' and accept the terms. Copy the token value.\n"
    "Your username is the email address on the FCC account, not a display name."
)


class BdcError(Exception):
    """Base class for every error raised by bdcdata."""


class BdcCredentialsMissing(BdcError):
    """No username/token could be found.

    Raised before any request is made, so the user is not left waiting on a
    network call that was always going to fail.
    """

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            (message or "No BDC credentials configured.") + "\n\nSet them in one of these ways:\n"
            "  bdcdata.set_credentials(username='you@example.com', token='...')\n"
            "  export BDC_USERNAME=you@example.com BDC_API_KEY=...\n"
            "  put BDC_USERNAME/BDC_API_KEY in a .env file, then "
            "bdcdata.load_dotenv()\n\n" + TOKEN_INSTRUCTIONS
        )


class BdcAuthError(BdcError):
    """The FCC rejected the credentials (HTTP 401 or 403)."""

    def __init__(self, message: str = "The FCC rejected your credentials (HTTP 401).") -> None:
        super().__init__(
            message + "\n\nCheck that the username is the email address on your FCC "
            "account and that the token has not been revoked or regenerated.\n\n"
            + TOKEN_INSTRUCTIONS
        )


class BdcNotFoundError(BdcError):
    """The requested resource does not exist (HTTP 404)."""


class BdcUnprocessableError(BdcError):
    """The FCC understood the request but will not process it (HTTP 422).

    In practice this usually means the combination of state, technology, and
    release you asked for has no published file.
    """


class BdcRateLimitError(BdcError):
    """Rate limit exceeded (HTTP 429).

    Every documented BDC endpoint allows 10 calls per minute. bdcdata paces
    requests to stay under that on its own, so seeing this generally means
    another process is sharing your token.
    """


class BdcServerError(BdcError):
    """The FCC returned a 5xx response."""


class BdcDataError(BdcError):
    """A file was downloaded but could not be parsed as expected."""


class BdcOptionalDependencyError(BdcError, ImportError):
    """A feature was used that needs an optional dependency."""

    def __init__(self, package: str, extra: str, feature: str) -> None:
        super().__init__(
            f"{feature} needs the '{package}' package, which is not installed.\n"
            f"Install it with:  pip install 'bdcdata[{extra}]'"
        )

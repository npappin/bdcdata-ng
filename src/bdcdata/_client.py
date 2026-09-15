"""HTTP access to the BDC public API.

One place owns talking to the FCC: authentication headers, the documented
10-calls-per-minute rate limit, retries, and turning HTTP status codes into
exceptions that say something useful.

The session is built on first use, never at import.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections import deque
from collections.abc import Mapping
from typing import Any

import requests

from ._cache import cache_key, read_cached, write_cached
from .config import RATE_LIMIT_PER_MINUTE, get_base_url, options
from .credentials import get_credentials
from .exceptions import (
    BdcAuthError,
    BdcDataError,
    BdcError,
    BdcNotFoundError,
    BdcRateLimitError,
    BdcServerError,
    BdcUnprocessableError,
)

__all__ = ["check_credentials", "get_bytes", "get_json", "reset_session"]

logger = logging.getLogger("bdcdata")

_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


def _user_agent() -> str:
    try:
        from importlib.metadata import version

        pkg_version = version("bdcdata")
    except Exception:  # pragma: no cover - only when running from a bare checkout
        pkg_version = "unknown"
    return f"bdcdata/{pkg_version} (+https://github.com/npappin/bdcdata)"


class _RateLimiter:
    """Sliding-window limiter shared by every request bdcdata makes.

    The FCC documents 10 calls per minute on each endpoint. Pacing here means
    a 50-state pull is slow rather than a wall of 429s.
    """

    def __init__(self, calls: int, period: float) -> None:
        self._calls = calls
        self._period = period
        self._times: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            while True:
                now = time.monotonic()
                while self._times and now - self._times[0] >= self._period:
                    self._times.popleft()
                if len(self._times) < self._calls:
                    self._times.append(now)
                    return
                wait = self._period - (now - self._times[0])
                if wait > 0:
                    logger.debug("Rate limit reached; waiting %.1fs", wait)
                    time.sleep(wait)

    def reset(self) -> None:
        with self._lock:
            self._times.clear()


_limiter = _RateLimiter(RATE_LIMIT_PER_MINUTE, 60.0)
_session: requests.Session | None = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    global _session
    with _session_lock:
        if _session is None:
            _session = requests.Session()
            _session.headers.update({"User-Agent": _user_agent()})
            logger.debug("HTTP session created")
        return _session


def reset_session() -> None:
    """Close the pooled HTTP session and clear the rate-limit window.

    Mostly useful in tests.
    """
    global _session
    with _session_lock:
        if _session is not None:
            _session.close()
        _session = None
    _limiter.reset()


def _raise_for_status(response: requests.Response, url: str) -> None:
    status = response.status_code
    if status == 200:
        return
    detail = _message_from_body(response)
    suffix = f" -- {detail}" if detail else ""
    if status in (401, 403):
        raise BdcAuthError(f"The FCC rejected your credentials (HTTP {status}){suffix}.")
    if status == 404:
        raise BdcNotFoundError(f"No such resource: {url} (HTTP 404){suffix}")
    if status == 422:
        raise BdcUnprocessableError(
            f"The FCC will not process this request (HTTP 422){suffix}.\n"
            "This usually means no file is published for that combination of "
            "state, technology, and release. Check bdcdata.catalog to see what "
            "exists for the release you asked for."
        )
    if status == 429:
        raise BdcRateLimitError(
            f"Rate limit exceeded (HTTP 429){suffix}.\n"
            "bdcdata paces requests to 10/minute on its own, so this usually "
            "means another program is using the same token at the same time."
        )
    if status >= 500:
        raise BdcServerError(f"The FCC server returned HTTP {status}{suffix}. Try again later.")
    raise BdcError(f"Unexpected response from {url}: HTTP {status}{suffix}")


def _message_from_body(response: requests.Response) -> str | None:
    """Pull the API's own error message out of a JSON body, if there is one."""
    try:
        payload = response.json()
    except ValueError:
        return None
    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return None


def _request(
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    username: str | None = None,
    token: str | None = None,
    stream: bool = False,
) -> requests.Response:
    """Make one GET request, with rate limiting and retries."""
    credentials = get_credentials(username=username, token=token)
    url = f"{get_base_url()}/{path.lstrip('/')}"
    session = _get_session()

    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    attempts = max(1, options.max_retries)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        _limiter.acquire()
        logger.debug("GET %s params=%s (attempt %d/%d)", url, clean_params, attempt, attempts)
        try:
            response = session.get(
                url,
                params=clean_params or None,
                headers=credentials.as_headers(),
                timeout=options.timeout,
                stream=stream,
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt == attempts:
                raise BdcError(f"Could not reach {url} after {attempts} attempt(s): {exc}") from exc
            _backoff(attempt, None)
            continue

        if response.status_code in _RETRY_STATUSES and attempt < attempts:
            logger.debug("HTTP %s from %s; retrying", response.status_code, url)
            _backoff(attempt, response.headers.get("Retry-After"))
            continue

        _raise_for_status(response, url)
        return response

    # Only reachable if every attempt raised a transport error.
    raise BdcError(f"Could not reach {url}: {last_error}")


def _backoff(attempt: int, retry_after: str | None) -> None:
    """Sleep before a retry, honoring ``Retry-After`` when the server sends it."""
    delay = 2.0**attempt
    if retry_after:
        # Retry-After may be an HTTP-date rather than seconds; when it is,
        # the exponential default stands.
        with contextlib.suppress(ValueError):
            delay = max(delay, float(retry_after))
    logger.debug("Backing off %.1fs before retry", delay)
    time.sleep(delay)


def get_json(
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    username: str | None = None,
    token: str | None = None,
) -> list[dict[str, Any]]:
    """GET a BDC endpoint and return the ``data`` array from the response body.

    Every list endpoint wraps its rows in ``{"data": [...], "status": ...}``.
    """
    response = _request(path, params=params, username=username, token=token)
    try:
        payload = response.json()
    except ValueError as exc:
        raise BdcDataError(f"{path} did not return JSON. Got: {response.text[:200]!r}") from exc

    if not isinstance(payload, dict):
        raise BdcDataError(f"{path} returned {type(payload).__name__}, expected an object.")

    # The API reports failures in the body as well as the status line.
    if str(payload.get("status", "")).lower() == "fail":
        code = payload.get("status_code")
        message = payload.get("message") or "no message"
        if code in (401, 403):
            raise BdcAuthError(f"The FCC rejected your credentials (HTTP {code}) -- {message}.")
        raise BdcError(f"{path} failed (status_code={code}): {message}")

    data = payload.get("data")
    if data is None:
        raise BdcDataError(f"{path} returned no 'data' field. Body: {str(payload)[:200]}")
    if not isinstance(data, list):
        raise BdcDataError(f"{path} returned a non-list 'data' field ({type(data).__name__}).")
    return data


def get_bytes(
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    username: str | None = None,
    token: str | None = None,
    cache: bool | None = None,
    cache_label: str | None = None,
) -> bytes:
    """GET a file and return its bytes, consulting the cache when enabled.

    Parameters
    ----------
    cache:
        ``None`` follows the global setting from :func:`bdcdata.set_cache`.
        ``True`` or ``False`` overrides it for this call.
    cache_label:
        A human-readable name (usually ``file_name`` from the catalog) used to
        make the cache directory browsable.
    """
    from .config import get_cache_settings

    url = f"{get_base_url()}/{path.lstrip('/')}"
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    if clean_params:
        url_for_key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(clean_params.items()))
    else:
        url_for_key = url

    use_cache = get_cache_settings()[0] if cache is None else bool(cache)
    key = cache_key(url_for_key, label=cache_label)

    if use_cache:
        cached = read_cached(key)
        if cached is not None:
            return cached

    response = _request(path, params=params, username=username, token=token)
    data = response.content

    if use_cache:
        write_cached(key, data)
    return data


def check_credentials(username: str | None = None, token: str | None = None) -> bool:
    """Verify credentials against the live API.

    Makes one request to ``listAsOfDates``.

    Returns
    -------
    bool
        ``True`` if the call succeeded.

    Raises
    ------
    BdcCredentialsMissing
        If no credentials could be found at all.
    BdcAuthError
        If the FCC rejected them.

    Examples
    --------
    >>> import bdcdata
    >>> bdcdata.check_credentials()  # doctest: +SKIP
    True
    """
    get_json("api/public/map/listAsOfDates", username=username, token=token)
    logger.info("Credentials accepted by the BDC API.")
    return True

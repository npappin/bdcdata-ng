"""Turning what people type into what the API expects.

The FCC speaks in 2-digit FIPS codes and integer technology codes. People
think in ``"WA"`` and ``"fiber"``. Everything in this module is pure -- no
network, no state -- so it is cheap to test and cheap to reason about.
"""

from __future__ import annotations

import datetime as dt
import difflib
import re
from collections.abc import Iterable, Sequence
from typing import Any, Literal

from .lookups import (
    _STATES,
    _TECHNOLOGIES,
    _TECHNOLOGY_ALIASES,
    _TECHNOLOGY_GROUPS,
)

__all__ = [
    "normalize_states",
    "normalize_technologies",
    "normalize_release",
    "as_list",
]

Domain = Literal["fixed", "mobile"]

_FIPS_BY_FIPS = {fips: fips for fips, _, _ in _STATES}
_FIPS_BY_USPS = {usps.lower(): fips for fips, usps, _ in _STATES}
_FIPS_BY_NAME = {name.lower(): fips for fips, _, name in _STATES}
_NAME_BY_FIPS = {fips: name for fips, _, name in _STATES}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def as_list(value: Any) -> list[Any]:
    """Wrap a scalar in a list; leave sequences alone.

    Strings count as scalars, which is the whole point.
    """
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        return [value]
    return list(value)


def _suggest(value: str, options: Iterable[str]) -> str:
    """Return a ' Did you mean ...?' fragment, or an empty string."""
    matches = difflib.get_close_matches(value.lower(), list(options), n=3, cutoff=0.6)
    if not matches:
        return ""
    if len(matches) == 1:
        return f" Did you mean {matches[0]!r}?"
    quoted = ", ".join(repr(m) for m in matches)
    return f" Did you mean one of {quoted}?"


def normalize_states(value: Any) -> list[str] | None:
    """Coerce state input to a list of 2-digit FIPS codes.

    Accepts FIPS codes (``53``, ``"53"``, ``6``, ``"06"``), USPS abbreviations
    (``"WA"``, ``"wa"``), full names (``"Washington"``), and lists mixing any
    of those.

    Returns
    -------
    list[str] | None
        ``None`` means "every state", which callers implement by not filtering
        the catalog at all.

    Examples
    --------
    >>> normalize_states("WA")
    ['53']
    >>> normalize_states(["wa", 6, "Texas"])
    ['53', '06', '48']
    >>> normalize_states("all") is None
    True
    """
    items = as_list(value)
    if not items:
        raise ValueError("No state given. Pass a state, a list of states, or 'all'.")

    if any(isinstance(v, str) and v.strip().lower() == "all" for v in items):
        return None

    out: list[str] = []
    for item in items:
        fips = _normalize_one_state(item)
        if fips not in out:
            out.append(fips)
    return out


def _normalize_one_state(item: Any) -> str:
    if isinstance(item, bool):
        raise TypeError(f"{item!r} is not a state.")

    if isinstance(item, int):
        candidate = f"{item:02d}"
        if candidate in _FIPS_BY_FIPS:
            return candidate
        raise ValueError(
            f"{item!r} is not a state FIPS code. See bdcdata.lookups.states() for the list."
        )

    if not isinstance(item, str):
        raise TypeError(
            f"Cannot read {item!r} ({type(item).__name__}) as a state. "
            "Use a FIPS code, a USPS abbreviation like 'WA', or a name like 'Washington'."
        )

    text = item.strip()
    if not text:
        raise ValueError("Got an empty string where a state was expected.")

    if text.isdigit():
        candidate = text.zfill(2)
        if candidate in _FIPS_BY_FIPS:
            return candidate
        raise ValueError(
            f"{item!r} is not a state FIPS code. See bdcdata.lookups.states() for the list."
        )

    lowered = text.lower()
    if lowered in _FIPS_BY_USPS:
        return _FIPS_BY_USPS[lowered]
    if lowered in _FIPS_BY_NAME:
        return _FIPS_BY_NAME[lowered]

    hint = _suggest(lowered, list(_FIPS_BY_USPS) + list(_FIPS_BY_NAME))
    raise ValueError(
        f"{item!r} is not a state, territory, or FIPS code.{hint} "
        "See bdcdata.lookups.states() for the full list."
    )


def state_name(fips: str) -> str:
    """Return the display name for a FIPS code, for use in messages."""
    return _NAME_BY_FIPS.get(fips, fips)


def normalize_technologies(value: Any, domain: Domain) -> list[int] | None:
    """Coerce technology input to a list of codes valid for *domain*.

    Accepts codes (``50``, ``"50"``), slugs (``"fiber"``), descriptions
    (``"Optical Carrier / Fiber to the Premises"``), common aliases
    (``"dsl"``, ``"fttp"``, ``"lte"``), and group names (``"all"``,
    ``"wired"``, ``"satellite"``, ``"terrestrial"``, ``"wireless"``).

    Parameters
    ----------
    domain:
        ``"fixed"`` or ``"mobile"``. Required, because code ``0`` means
        "Other" for fixed and "Mobile Voice" for mobile.

    Returns
    -------
    list[int] | None
        ``None`` means "every technology in this domain".

    Examples
    --------
    >>> normalize_technologies("fiber", domain="fixed")
    [50]
    >>> normalize_technologies(["dsl", "cable"], domain="fixed")
    [10, 40]
    >>> normalize_technologies("5g", domain="mobile")
    [500]
    >>> normalize_technologies("all", domain="mobile") is None
    True
    """
    if domain not in ("fixed", "mobile"):
        raise ValueError(f"domain must be 'fixed' or 'mobile', got {domain!r}")

    items = as_list(value)
    if not items:
        raise ValueError(
            "No technology given. Pass a technology, a list of them, or 'all'. "
            "See bdcdata.lookups.technologies()."
        )

    valid_codes = {code for code, _, _, dom in _TECHNOLOGIES if dom == domain}
    by_slug = {slug: code for code, slug, _, dom in _TECHNOLOGIES if dom == domain}
    by_description = {
        desc.lower(): code for code, _, desc, dom in _TECHNOLOGIES if dom == domain
    }

    out: list[int] = []
    for item in items:
        codes = _normalize_one_technology(item, domain, valid_codes, by_slug, by_description)
        if codes is None:
            return None
        for code in codes:
            if code not in out:
                out.append(code)
    return out


def _normalize_one_technology(
    item: Any,
    domain: Domain,
    valid_codes: set[int],
    by_slug: dict[str, int],
    by_description: dict[str, int],
) -> list[int] | None:
    """Resolve one technology token. ``None`` means 'all in this domain'."""
    if isinstance(item, bool):
        raise TypeError(f"{item!r} is not a technology.")

    if isinstance(item, int):
        if item in valid_codes:
            return [item]
        raise ValueError(_bad_technology_message(item, domain, valid_codes, by_slug))

    if not isinstance(item, str):
        raise TypeError(
            f"Cannot read {item!r} ({type(item).__name__}) as a technology. "
            "Use a code like 50, a name like 'fiber', or 'all'."
        )

    text = item.strip()
    if not text:
        raise ValueError("Got an empty string where a technology was expected.")
    lowered = text.lower()

    if lowered == "all" or lowered == domain:
        return None

    if lowered in _TECHNOLOGY_GROUPS:
        group = [c for c in _TECHNOLOGY_GROUPS[lowered] if c in valid_codes]
        if not group:
            other = "mobile" if domain == "fixed" else "fixed"
            raise ValueError(
                f"{item!r} is a {other} technology group, but this is {domain} data. "
                f"Valid groups here: {_valid_groups(domain)}."
            )
        return group

    if lowered.isdigit():
        code = int(lowered)
        if code in valid_codes:
            return [code]
        raise ValueError(_bad_technology_message(item, domain, valid_codes, by_slug))

    canonical = _TECHNOLOGY_ALIASES.get(lowered, lowered)
    if canonical in by_slug:
        return [by_slug[canonical]]
    if lowered in by_description:
        return [by_description[lowered]]

    raise ValueError(_bad_technology_message(item, domain, valid_codes, by_slug))


def _valid_groups(domain: Domain) -> str:
    valid_codes = {code for code, _, _, dom in _TECHNOLOGIES if dom == domain}
    names = [
        name
        for name, codes in _TECHNOLOGY_GROUPS.items()
        if name != "all" and any(c in valid_codes for c in codes)
    ]
    return ", ".join(repr(n) for n in sorted(names))


def _bad_technology_message(
    item: Any, domain: Domain, valid_codes: set[int], by_slug: dict[str, int]
) -> str:
    hint = _suggest(str(item).lower(), by_slug) if isinstance(item, str) else ""
    codes = ", ".join(str(c) for c in sorted(valid_codes))
    slugs = ", ".join(repr(s) for s in by_slug)
    return (
        f"{item!r} is not a {domain} technology.{hint}\n"
        f"  Valid {domain} codes: {codes}\n"
        f"  Valid {domain} names: {slugs}\n"
        f"  See bdcdata.lookups.technologies({domain!r})."
    )


def normalize_release(value: Any, available: Sequence[str] | None = None) -> list[str]:
    """Coerce release input to a list of ``YYYY-MM-DD`` strings.

    Accepts ISO strings, :class:`datetime.date` and :class:`datetime.datetime`,
    and lists of either. ``"latest"`` and ``"all"`` are resolved by the caller,
    which knows what the API currently publishes; pass *available* to have them
    resolved here.

    Examples
    --------
    >>> normalize_release("2024-06-30")
    ['2024-06-30']
    >>> import datetime as dt
    >>> normalize_release(dt.date(2024, 6, 30))
    ['2024-06-30']
    >>> normalize_release("latest", available=["2023-12-31", "2024-06-30"])
    ['2024-06-30']
    """
    items = as_list(value)
    if not items:
        raise ValueError("No release given. Pass a date like '2024-06-30', or 'latest'.")

    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            keyword = item.strip().lower()
            if keyword in ("latest", "all"):
                if available is None:
                    raise ValueError(
                        f"{item!r} cannot be resolved here; the caller must supply the "
                        "list of published releases."
                    )
                if not available:
                    raise ValueError("The API reported no published releases for this data type.")
                chosen = [max(available)] if keyword == "latest" else sorted(available)
                for release in chosen:
                    if release not in out:
                        out.append(release)
                continue

        release = _normalize_one_release(item)
        if available is not None and release not in available:
            hint = _suggest(release, available)
            published = ", ".join(sorted(available))
            raise ValueError(
                f"No release published for {release!r}.{hint}\n"
                f"  Published releases: {published}\n"
                "  See bdcdata.catalog.releases()."
            )
        if release not in out:
            out.append(release)
    return out


def _normalize_one_release(item: Any) -> str:
    if isinstance(item, dt.datetime):
        return item.date().isoformat()
    if isinstance(item, dt.date):
        return item.isoformat()
    if isinstance(item, str):
        text = item.strip()
        if _ISO_DATE.match(text):
            try:
                dt.date.fromisoformat(text)
            except ValueError as exc:
                raise ValueError(f"{item!r} is not a real date: {exc}") from exc
            return text
        raise ValueError(
            f"{item!r} is not a release date. Use 'YYYY-MM-DD' (for example "
            "'2024-06-30'), a datetime.date, or 'latest'."
        )
    raise TypeError(
        f"Cannot read {item!r} ({type(item).__name__}) as a release. "
        "Use 'YYYY-MM-DD', a datetime.date, or 'latest'."
    )

"""Reference tables: states, technologies, and challenge categories.

These are plain DataFrames so you can *look* at the codes instead of guessing
them::

    >>> import bdcdata
    >>> bdcdata.lookups.technologies()          # doctest: +SKIP
    >>> bdcdata.lookups.states().head()         # doctest: +SKIP

They also back the normalizers, so anything listed in these tables is
something you can pass to a data function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["states", "technologies", "challenge_categories"]


# (fips, usps, name)
_STATES: tuple[tuple[str, str, str], ...] = (
    ("01", "AL", "Alabama"),
    ("02", "AK", "Alaska"),
    ("04", "AZ", "Arizona"),
    ("05", "AR", "Arkansas"),
    ("06", "CA", "California"),
    ("08", "CO", "Colorado"),
    ("09", "CT", "Connecticut"),
    ("10", "DE", "Delaware"),
    ("11", "DC", "District of Columbia"),
    ("12", "FL", "Florida"),
    ("13", "GA", "Georgia"),
    ("15", "HI", "Hawaii"),
    ("16", "ID", "Idaho"),
    ("17", "IL", "Illinois"),
    ("18", "IN", "Indiana"),
    ("19", "IA", "Iowa"),
    ("20", "KS", "Kansas"),
    ("21", "KY", "Kentucky"),
    ("22", "LA", "Louisiana"),
    ("23", "ME", "Maine"),
    ("24", "MD", "Maryland"),
    ("25", "MA", "Massachusetts"),
    ("26", "MI", "Michigan"),
    ("27", "MN", "Minnesota"),
    ("28", "MS", "Mississippi"),
    ("29", "MO", "Missouri"),
    ("30", "MT", "Montana"),
    ("31", "NE", "Nebraska"),
    ("32", "NV", "Nevada"),
    ("33", "NH", "New Hampshire"),
    ("34", "NJ", "New Jersey"),
    ("35", "NM", "New Mexico"),
    ("36", "NY", "New York"),
    ("37", "NC", "North Carolina"),
    ("38", "ND", "North Dakota"),
    ("39", "OH", "Ohio"),
    ("40", "OK", "Oklahoma"),
    ("41", "OR", "Oregon"),
    ("42", "PA", "Pennsylvania"),
    ("44", "RI", "Rhode Island"),
    ("45", "SC", "South Carolina"),
    ("46", "SD", "South Dakota"),
    ("47", "TN", "Tennessee"),
    ("48", "TX", "Texas"),
    ("49", "UT", "Utah"),
    ("50", "VT", "Vermont"),
    ("51", "VA", "Virginia"),
    ("53", "WA", "Washington"),
    ("54", "WV", "West Virginia"),
    ("55", "WI", "Wisconsin"),
    ("56", "WY", "Wyoming"),
    ("60", "AS", "American Samoa"),
    ("66", "GU", "Guam"),
    ("69", "MP", "Northern Mariana Islands"),
    ("72", "PR", "Puerto Rico"),
    ("78", "VI", "United States Virgin Islands"),
)


# (code, slug, description, domain)
#
# Technology codes are NOT unique across domains: code 0 is "Other" for fixed
# broadband and "Mobile Voice" for mobile. Always resolve a code together with
# its domain.
_TECHNOLOGIES: tuple[tuple[int, str, str, str], ...] = (
    (0, "other", "Other", "fixed"),
    (10, "copper", "Copper Wire", "fixed"),
    (40, "cable", "Coaxial Cable / HFC", "fixed"),
    (50, "fiber", "Optical Carrier / Fiber to the Premises", "fixed"),
    (60, "gso_satellite", "Geostationary Satellite", "fixed"),
    (61, "ngso_satellite", "Non-geostationary Satellite", "fixed"),
    (70, "unlicensed_tfw", "Unlicensed Fixed Wireless", "fixed"),
    (71, "licensed_tfw", "Licensed Fixed Wireless", "fixed"),
    (72, "lbr_tfw", "Licensed-by-Rule Fixed Wireless", "fixed"),
    (0, "mobile_voice", "Mobile Voice", "mobile"),
    (300, "3g", "3G", "mobile"),
    (400, "4g", "4G LTE", "mobile"),
    (500, "5g", "5G-NR", "mobile"),
)

# Everyday words people actually type, mapped onto the canonical slug.
_TECHNOLOGY_ALIASES: dict[str, str] = {
    "dsl": "copper",
    "copper wire": "copper",
    "coax": "cable",
    "hfc": "cable",
    "coaxial": "cable",
    "coaxial cable": "cable",
    "fttp": "fiber",
    "fiber to the premises": "fiber",
    "fibre": "fiber",
    "optical carrier": "fiber",
    "satellite": "gso_satellite",
    "geostationary satellite": "gso_satellite",
    "gso": "gso_satellite",
    "non-geostationary satellite": "ngso_satellite",
    "ngso": "ngso_satellite",
    "unlicensed fixed wireless": "unlicensed_tfw",
    "licensed fixed wireless": "licensed_tfw",
    "licensed-by-rule fixed wireless": "lbr_tfw",
    "lbr": "lbr_tfw",
    "3g": "3g",
    "4g": "4g",
    "4g lte": "4g",
    "lte": "4g",
    "5g": "5g",
    "5g-nr": "5g",
    "5g nr": "5g",
    "nr": "5g",
    "voice": "mobile_voice",
    "mobile voice": "mobile_voice",
}

# Group names that expand to several codes.
_TECHNOLOGY_GROUPS: dict[str, tuple[int, ...]] = {
    "all": (),  # filled in per-domain by the normalizer
    "fixed": (0, 10, 40, 50, 60, 61, 70, 71, 72),
    "mobile": (0, 300, 400, 500),
    # "Wired service includes technology codes 10, 40 and 50" -- spec 3.1.1.2
    "wired": (10, 40, 50),
    # "Terrestrial service includes all technology codes other than 60 and 61"
    "terrestrial": (0, 10, 40, 50, 70, 71, 72),
    "satellite": (60, 61),
    "wireless": (70, 71, 72),
}


# (category, kind, status) -- the exact strings the API expects for the
# `category` query parameter on listChallengeData.
_CHALLENGE_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("Fabric Challenge - In Progress", "fabric", "in_progress"),
    ("Fabric Challenge - Resolved", "fabric", "resolved"),
    ("Fixed Challenge - Cumulative", "fixed", "cumulative"),
    ("Fixed Challenge - In Progress", "fixed", "in_progress"),
    ("Fixed Challenge - Resolved", "fixed", "resolved"),
    ("Mobile Challenge - In Progress", "mobile", "in_progress"),
    ("Mobile Challenge - Resolved", "mobile", "resolved"),
    ("Fixed Verification - In Progress", "fixed_verification", "in_progress"),
    ("Fixed Verification - Resolved", "fixed_verification", "resolved"),
    ("Mobile Verification - In Progress", "mobile_verification", "in_progress"),
    ("Mobile Verification - Resolved", "mobile_verification", "resolved"),
    ("Mobile Audit - In Progress", "mobile_audit", "in_progress"),
    ("Mobile Audit - Resolved", "mobile_audit", "resolved"),
)


def states() -> pd.DataFrame:
    """Return every state and territory the BDC publishes data for.

    Columns: ``fips``, ``usps``, ``name``.
    """
    import pandas as pd

    return pd.DataFrame(list(_STATES), columns=["fips", "usps", "name"])


def technologies(domain: Literal["fixed", "mobile", "all"] = "all") -> pd.DataFrame:
    """Return the technology codes.

    Columns: ``code``, ``slug``, ``description``, ``domain``.

    Parameters
    ----------
    domain:
        Limit to ``"fixed"`` or ``"mobile"``, or return both with ``"all"``.

    Notes
    -----
    Code ``0`` appears twice: it is "Other" for fixed broadband and
    "Mobile Voice" for mobile. That is the FCC's numbering, not a mistake here.
    """
    import pandas as pd

    rows = list(_TECHNOLOGIES)
    if domain != "all":
        rows = [r for r in rows if r[3] == domain]
    return pd.DataFrame(rows, columns=["code", "slug", "description", "domain"])


def challenge_categories() -> pd.DataFrame:
    """Return the challenge categories the API accepts.

    Columns: ``category`` (the exact API string), ``kind``, ``status``.

    The FCC has added categories twice since 2023, so treat this as a snapshot;
    :func:`bdcdata.catalog.challenge_files` reports whatever the API currently
    returns.
    """
    import pandas as pd

    return pd.DataFrame(list(_CHALLENGE_CATEGORIES), columns=["category", "kind", "status"])

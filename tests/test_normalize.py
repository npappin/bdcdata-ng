"""Normalizers are pure, so these run with no network and no credentials."""

from __future__ import annotations

import datetime as dt

import pytest

from bdcdata._normalize import (
    as_list,
    normalize_release,
    normalize_states,
    normalize_technologies,
)


class TestAsList:
    def test_scalar_is_wrapped(self):
        assert as_list("WA") == ["WA"]
        assert as_list(53) == [53]

    def test_sequence_passes_through(self):
        assert as_list(["WA", "OR"]) == ["WA", "OR"]
        assert as_list(("WA", "OR")) == ["WA", "OR"]

    def test_none_is_empty(self):
        assert as_list(None) == []

    def test_string_is_not_exploded_into_characters(self):
        # The bug this guards against: iterating "WA" into ["W", "A"].
        assert as_list("Washington") == ["Washington"]


class TestNormalizeStates:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("WA", ["53"]),
            ("wa", ["53"]),
            ("Washington", ["53"]),
            ("washington", ["53"]),
            ("53", ["53"]),
            (53, ["53"]),
            (6, ["06"]),
            ("6", ["06"]),
            ("06", ["06"]),
            ("DC", ["11"]),
            ("PR", ["72"]),
        ],
    )
    def test_accepts_every_spelling(self, value, expected):
        assert normalize_states(value) == expected

    def test_mixed_list(self):
        assert normalize_states(["wa", 6, "Texas"]) == ["53", "06", "48"]

    def test_deduplicates_preserving_order(self):
        assert normalize_states(["WA", "53", "Washington", "OR"]) == ["53", "41"]

    def test_all_returns_none(self):
        assert normalize_states("all") is None
        assert normalize_states(["WA", "all"]) is None

    def test_empty_input_rejected(self):
        with pytest.raises(ValueError, match="No state given"):
            normalize_states([])

    def test_unknown_state_suggests_alternative(self):
        with pytest.raises(ValueError, match="Did you mean"):
            normalize_states("Washingtn")

    def test_unknown_fips_is_rejected(self):
        # 03 is not an assigned state FIPS code.
        with pytest.raises(ValueError, match="not a state FIPS code"):
            normalize_states("03")

    def test_bool_is_rejected(self):
        with pytest.raises(TypeError):
            normalize_states(True)


class TestNormalizeTechnologies:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("fiber", [50]),
            ("Fiber", [50]),
            ("fttp", [50]),
            ("dsl", [10]),
            ("copper", [10]),
            ("cable", [40]),
            ("hfc", [40]),
            (50, [50]),
            ("50", [50]),
            (0, [0]),
            ("Optical Carrier / Fiber to the Premises", [50]),
        ],
    )
    def test_fixed_spellings(self, value, expected):
        assert normalize_technologies(value, domain="fixed") == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("5g", [500]),
            ("5G-NR", [500]),
            ("lte", [400]),
            ("4g", [400]),
            ("3g", [300]),
            (500, [500]),
            ("mobile_voice", [0]),
            ("voice", [0]),
        ],
    )
    def test_mobile_spellings(self, value, expected):
        assert normalize_technologies(value, domain="mobile") == expected

    def test_code_zero_is_domain_dependent(self):
        # 0 is "Other" for fixed and "Mobile Voice" for mobile. Both are valid,
        # and they are different things.
        assert normalize_technologies(0, domain="fixed") == [0]
        assert normalize_technologies(0, domain="mobile") == [0]
        assert normalize_technologies("other", domain="fixed") == [0]
        with pytest.raises(ValueError):
            normalize_technologies("other", domain="mobile")

    def test_groups(self):
        assert normalize_technologies("wired", domain="fixed") == [10, 40, 50]
        assert normalize_technologies("satellite", domain="fixed") == [60, 61]
        assert normalize_technologies("wireless", domain="fixed") == [70, 71, 72]
        assert normalize_technologies("terrestrial", domain="fixed") == [0, 10, 40, 50, 70, 71, 72]

    def test_all_returns_none(self):
        assert normalize_technologies("all", domain="fixed") is None
        assert normalize_technologies("all", domain="mobile") is None

    def test_domain_name_means_all_in_that_domain(self):
        assert normalize_technologies("fixed", domain="fixed") is None
        assert normalize_technologies("mobile", domain="mobile") is None

    def test_mobile_code_rejected_for_fixed(self):
        with pytest.raises(ValueError, match="not a fixed technology"):
            normalize_technologies(500, domain="fixed")

    def test_fixed_code_rejected_for_mobile(self):
        with pytest.raises(ValueError, match="not a mobile technology"):
            normalize_technologies(50, domain="mobile")

    def test_wrong_domain_group_explains_itself(self):
        with pytest.raises(ValueError, match="is a fixed technology group"):
            normalize_technologies("wired", domain="mobile")

    def test_error_lists_valid_options(self):
        with pytest.raises(ValueError) as excinfo:
            normalize_technologies("fibre-optic", domain="fixed")
        message = str(excinfo.value)
        assert "Valid fixed codes" in message
        assert "'fiber'" in message

    def test_dedupe(self):
        assert normalize_technologies(["fiber", 50, "fttp"], domain="fixed") == [50]

    def test_bad_domain(self):
        with pytest.raises(ValueError, match="domain must be"):
            normalize_technologies("fiber", domain="satellite")


class TestNormalizeRelease:
    def test_iso_string(self):
        assert normalize_release("2024-06-30") == ["2024-06-30"]

    def test_date_and_datetime(self):
        assert normalize_release(dt.date(2024, 6, 30)) == ["2024-06-30"]
        assert normalize_release(dt.datetime(2024, 6, 30, 12, 0)) == ["2024-06-30"]

    def test_list(self):
        assert normalize_release(["2023-12-31", "2024-06-30"]) == ["2023-12-31", "2024-06-30"]

    def test_latest_picks_the_newest(self):
        available = ["2022-12-31", "2024-06-30", "2023-06-30"]
        assert normalize_release("latest", available=available) == ["2024-06-30"]

    def test_all_returns_every_published_release_sorted(self):
        available = ["2024-06-30", "2022-12-31"]
        assert normalize_release("all", available=available) == ["2022-12-31", "2024-06-30"]

    def test_latest_needs_the_published_list(self):
        with pytest.raises(ValueError, match="cannot be resolved here"):
            normalize_release("latest")

    def test_unpublished_release_is_rejected_with_the_list(self):
        with pytest.raises(ValueError) as excinfo:
            normalize_release("2021-01-01", available=["2024-06-30"])
        assert "Published releases" in str(excinfo.value)

    def test_bad_format(self):
        with pytest.raises(ValueError, match="not a release date"):
            normalize_release("June 30 2024")

    def test_impossible_date(self):
        with pytest.raises(ValueError, match="not a real date"):
            normalize_release("2024-02-31")

    def test_empty(self):
        with pytest.raises(ValueError, match="No release given"):
            normalize_release([])

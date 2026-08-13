"""The reference tables are documentation as much as code -- check they hold up."""

from __future__ import annotations

from bdcdata import lookups
from bdcdata._normalize import normalize_states, normalize_technologies


class TestStates:
    def test_shape(self):
        df = lookups.states()
        # 50 states + DC + 5 territories
        assert len(df) == 56
        assert list(df.columns) == ["fips", "usps", "name"]

    def test_fips_are_two_digit_strings(self):
        df = lookups.states()
        assert df["fips"].map(len).eq(2).all()
        assert df["fips"].str.isdigit().all()

    def test_no_duplicates(self):
        df = lookups.states()
        assert not df["fips"].duplicated().any()
        assert not df["usps"].duplicated().any()
        assert not df["name"].duplicated().any()

    def test_every_row_round_trips_through_the_normalizer(self):
        for row in lookups.states().itertuples():
            assert normalize_states(row.fips) == [row.fips]
            assert normalize_states(row.usps) == [row.fips]
            assert normalize_states(row.name) == [row.fips]


class TestTechnologies:
    def test_columns(self):
        df = lookups.technologies()
        assert list(df.columns) == ["code", "slug", "description", "domain"]

    def test_domain_filter(self):
        assert set(lookups.technologies("fixed")["domain"]) == {"fixed"}
        assert set(lookups.technologies("mobile")["domain"]) == {"mobile"}
        assert len(lookups.technologies()) == len(lookups.technologies("fixed")) + len(
            lookups.technologies("mobile")
        )

    def test_code_zero_appears_in_both_domains(self):
        df = lookups.technologies()
        zeros = df[df["code"] == 0]
        assert set(zeros["domain"]) == {"fixed", "mobile"}
        assert set(zeros["slug"]) == {"other", "mobile_voice"}

    def test_codes_unique_within_a_domain(self):
        for domain in ("fixed", "mobile"):
            df = lookups.technologies(domain)
            assert not df["code"].duplicated().any()

    def test_slugs_globally_unique(self):
        assert not lookups.technologies()["slug"].duplicated().any()

    def test_every_row_round_trips_through_the_normalizer(self):
        for row in lookups.technologies().itertuples():
            assert normalize_technologies(row.code, domain=row.domain) == [row.code]
            assert normalize_technologies(row.slug, domain=row.domain) == [row.code]
            assert normalize_technologies(row.description, domain=row.domain) == [row.code]


class TestChallengeCategories:
    def test_columns(self):
        df = lookups.challenge_categories()
        assert list(df.columns) == ["category", "kind", "status"]

    def test_categories_unique(self):
        assert not lookups.challenge_categories()["category"].duplicated().any()

    def test_statuses_are_known(self):
        statuses = set(lookups.challenge_categories()["status"])
        assert statuses <= {"in_progress", "resolved", "cumulative"}

    def test_category_strings_match_the_api_format(self):
        # The API matches on these exactly; a stray double space or a
        # lowercase word would silently return nothing.
        for category in lookups.challenge_categories()["category"]:
            assert " - " in category
            assert "  " not in category
            assert category == category.strip()

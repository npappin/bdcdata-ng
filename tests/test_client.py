"""Auth headers, error mapping, retries, and rate limiting."""

from __future__ import annotations

import pytest
import responses

import bdcdata
from bdcdata import _client
from bdcdata.exceptions import (
    BdcAuthError,
    BdcCredentialsMissing,
    BdcDataError,
    BdcError,
    BdcNotFoundError,
    BdcRateLimitError,
    BdcServerError,
    BdcUnprocessableError,
)
from helpers import AS_OF_DATES_URL as AS_OF_DATES
from helpers import api_payload


class TestAuthHeaders:
    def test_sends_username_and_hash_value(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES, json=api_payload([]), status=200)

        _client.get_json("api/public/map/listAsOfDates")

        headers = mock_api.calls[0].request.headers
        assert headers["username"] == "tester@example.com"
        assert headers["hash_value"] == "test-token"

    def test_user_agent_identifies_the_package(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES, json=api_payload([]), status=200)

        _client.get_json("api/public/map/listAsOfDates")

        assert mock_api.calls[0].request.headers["User-Agent"].startswith("bdcdata/")

    def test_explicit_credentials_win(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES, json=api_payload([]), status=200)

        _client.get_json(
            "api/public/map/listAsOfDates", username="other@example.com", token="other-token"
        )

        headers = mock_api.calls[0].request.headers
        assert headers["username"] == "other@example.com"
        assert headers["hash_value"] == "other-token"

    def test_missing_credentials_raises_before_any_request(self, no_credentials, mock_api):
        with pytest.raises(BdcCredentialsMissing) as excinfo:
            _client.get_json("api/public/map/listAsOfDates")

        # No request should have been attempted.
        assert len(mock_api.calls) == 0
        message = str(excinfo.value)
        assert "set_credentials" in message
        assert "BDC_USERNAME" in message
        assert "broadbandmap.fcc.gov/login" in message

    def test_half_configured_credentials_say_which_half(self, monkeypatch, mock_api):
        monkeypatch.delenv("BDC_API_KEY")
        bdcdata.clear_credentials()

        with pytest.raises(BdcCredentialsMissing, match="BDC_USERNAME is set but BDC_API_KEY"):
            _client.get_json("api/public/map/listAsOfDates")


class TestErrorMapping:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (401, BdcAuthError),
            (403, BdcAuthError),
            (404, BdcNotFoundError),
            (422, BdcUnprocessableError),
        ],
    )
    def test_status_codes_map_to_specific_exceptions(self, mock_api, status, expected):
        mock_api.add(responses.GET, AS_OF_DATES, json={"message": "nope"}, status=status)

        with pytest.raises(expected):
            _client.get_json("api/public/map/listAsOfDates")

    def test_auth_error_explains_how_to_get_a_token(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES, json={"message": "Unauthorized"}, status=401)

        with pytest.raises(BdcAuthError) as excinfo:
            _client.get_json("api/public/map/listAsOfDates")

        assert "Manage API Access" in str(excinfo.value)

    def test_422_points_at_the_catalog(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES, status=422)

        with pytest.raises(BdcUnprocessableError, match=r"bdcdata\.catalog"):
            _client.get_json("api/public/map/listAsOfDates")

    def test_server_error_after_retries(self, mock_api, no_backoff):
        for _ in range(3):
            mock_api.add(responses.GET, AS_OF_DATES, status=500)

        with pytest.raises(BdcServerError):
            _client.get_json("api/public/map/listAsOfDates")

    def test_rate_limit_after_retries(self, mock_api, no_backoff):
        for _ in range(3):
            mock_api.add(responses.GET, AS_OF_DATES, status=429)

        with pytest.raises(BdcRateLimitError):
            _client.get_json("api/public/map/listAsOfDates")

    def test_failure_reported_in_a_200_body_is_still_an_error(self, mock_api):
        # The API sometimes reports failure in the body rather than the status.
        mock_api.add(
            responses.GET,
            AS_OF_DATES,
            json={"status": "fail", "status_code": 401, "message": "Unauthorized"},
            status=200,
        )

        with pytest.raises(BdcAuthError):
            _client.get_json("api/public/map/listAsOfDates")

    def test_non_json_body_raises_data_error(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES, body="<html>gateway timeout</html>", status=200)

        with pytest.raises(BdcDataError, match="did not return JSON"):
            _client.get_json("api/public/map/listAsOfDates")

    def test_missing_data_field_raises_data_error(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES, json={"status": "successful"}, status=200)

        with pytest.raises(BdcDataError, match="no 'data' field"):
            _client.get_json("api/public/map/listAsOfDates")


class TestRetries:
    def test_transient_500_then_success(self, mock_api, no_backoff):
        mock_api.add(responses.GET, AS_OF_DATES, status=503)
        mock_api.add(responses.GET, AS_OF_DATES, json=api_payload([{"a": 1}]), status=200)

        rows = _client.get_json("api/public/map/listAsOfDates")

        assert rows == [{"a": 1}]
        assert len(mock_api.calls) == 2

    def test_retry_after_header_is_honored(self, mock_api, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr("bdcdata._client.time.sleep", lambda s: slept.append(s))

        mock_api.add(responses.GET, AS_OF_DATES, status=429, headers={"Retry-After": "42"})
        mock_api.add(responses.GET, AS_OF_DATES, json=api_payload([]), status=200)

        _client.get_json("api/public/map/listAsOfDates")

        assert 42 in slept

    def test_404_is_not_retried(self, mock_api, no_backoff):
        mock_api.add(responses.GET, AS_OF_DATES, status=404)

        with pytest.raises(BdcNotFoundError):
            _client.get_json("api/public/map/listAsOfDates")

        assert len(mock_api.calls) == 1

    def test_connection_error_is_wrapped(self, mock_api, no_backoff):
        with pytest.raises(BdcError, match="Could not reach"):
            _client.get_json("api/public/map/listAsOfDates")


class TestBaseUrl:
    def test_default_host_is_the_documented_one(self):
        from bdcdata.config import get_base_url

        assert get_base_url() == "https://bdc.fcc.gov"

    def test_override(self, mock_api):
        bdcdata.set_base_url("https://example.test")
        mock_api.add(
            responses.GET,
            "https://example.test/api/public/map/listAsOfDates",
            json=api_payload([]),
            status=200,
        )

        _client.get_json("api/public/map/listAsOfDates")

        assert mock_api.calls[0].request.url.startswith("https://example.test")

    def test_env_var_override(self, monkeypatch, mock_api):
        monkeypatch.setenv("BDC_BASE_URL", "https://staging.test")
        from bdcdata.config import get_base_url

        assert get_base_url() == "https://staging.test"


class TestCheckCredentials:
    def test_returns_true_on_success(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES, json=api_payload([]), status=200)

        assert bdcdata.check_credentials() is True

    def test_raises_on_rejection(self, mock_api):
        mock_api.add(responses.GET, AS_OF_DATES, status=401)

        with pytest.raises(BdcAuthError):
            bdcdata.check_credentials()


class TestRateLimiter:
    def test_session_is_rate_limited_to_the_published_rate(self, monkeypatch):
        from requests_ratelimiter import LimiterSession
        from requests_ratelimiter.buckets import HostBucketFactory

        monkeypatch.setattr(_client, "_session", None)  # bypass conftest's fast session
        session = _client._get_session()
        try:
            assert isinstance(session, LimiterSession)
            factory = session.limiter.bucket_factory
            assert isinstance(factory, HostBucketFactory)
            [rate] = factory.rates
            assert (rate.limit, rate.interval) == (10, 60_000)
        finally:
            session.close()

    def test_eleventh_call_in_a_minute_is_held_back(self, monkeypatch, mock_api):
        import requests

        monkeypatch.setattr(_client, "_session", None)
        session = _client._get_session()
        session.max_delay = 0.5  # fail fast instead of waiting out the minute
        mock_api.add(responses.GET, AS_OF_DATES, json={"data": []})
        try:
            for _ in range(10):
                session.get(AS_OF_DATES)
            with pytest.raises(requests.exceptions.Timeout):
                session.get(AS_OF_DATES)
        finally:
            session.close()

    def test_limit_matches_the_published_rate(self):
        from bdcdata.config import RATE_LIMIT_PER_MINUTE

        assert RATE_LIMIT_PER_MINUTE == 10

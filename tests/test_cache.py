"""Cache behavior. Off by default, cwd-relative, and only ever deletes its own files."""

from __future__ import annotations

from pathlib import Path

import responses

import bdcdata
from bdcdata import _cache, _client
from bdcdata.config import get_cache_settings
from helpers import FIXED_AVAILABILITY_CSV, MAP_DOWNLOAD_URL, make_csv_zip

DOWNLOAD_URL = f"{MAP_DOWNLOAD_URL}/availability/12345"


class TestDefaults:
    def test_cache_is_off_by_default(self):
        bdcdata.set_cache(False)
        assert get_cache_settings()[0] is False
        assert bdcdata.cache_info()["enabled"] is False

    def test_default_path_is_cwd_relative(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bdcdata.set_cache(True, path=None)
        # Reset the explicit path set by the isolation fixture.
        from bdcdata.config import options

        options.cache_path = None

        _, path = get_cache_settings()
        assert path == tmp_path / "bdc_cache"

    def test_path_is_resolved_at_call_time_not_import_time(self, tmp_path, monkeypatch):
        from bdcdata.config import options

        options.cache_path = None
        monkeypatch.chdir(tmp_path)
        first = get_cache_settings()[1]

        nested = tmp_path / "elsewhere"
        nested.mkdir()
        monkeypatch.chdir(nested)
        second = get_cache_settings()[1]

        assert first != second
        assert second == nested / "bdc_cache"


class TestRoundTrip:
    def test_miss_then_hit(self, tmp_path):
        bdcdata.set_cache(True, path=tmp_path / "cache")
        key = _cache.cache_key("https://example.test/file", label="bdc_53_fiber")

        assert _cache.read_cached(key) is None
        _cache.write_cached(key, b"payload")
        assert _cache.read_cached(key) == b"payload"

    def test_nothing_written_when_disabled(self, mock_api, tmp_path):
        # Gating lives in the client, not the store, so that a per-call
        # cache=True can override a global cache=False.
        bdcdata.set_cache(False, path=tmp_path / "cache")
        payload = make_csv_zip(FIXED_AVAILABILITY_CSV)
        mock_api.add(responses.GET, DOWNLOAD_URL, body=payload, status=200)
        mock_api.add(responses.GET, DOWNLOAD_URL, body=payload, status=200)

        path = "api/public/map/downloads/downloadFile/availability/12345"
        _client.get_bytes(path)
        _client.get_bytes(path)

        assert len(mock_api.calls) == 2
        assert not (tmp_path / "cache").exists()

    def test_key_includes_a_readable_label(self):
        key = _cache.cache_key("https://example.test/f", label="bdc_53_fiber_J24")
        assert key.startswith("bdc_53_fiber_J24-")
        assert key.endswith(".bdccache")

    def test_different_urls_get_different_keys(self):
        assert _cache.cache_key("https://a.test/1") != _cache.cache_key("https://a.test/2")

    def test_same_url_is_stable(self):
        assert _cache.cache_key("https://a.test/1") == _cache.cache_key("https://a.test/1")

    def test_label_is_sanitized(self):
        key = _cache.cache_key("https://a.test/1", label="../../etc/passwd")
        assert "/" not in key
        assert ".." not in key.split("-")[0]


class TestSecondCallSkipsTheNetwork:
    def test_download_is_served_from_cache(self, mock_api, tmp_path):
        bdcdata.set_cache(True, path=tmp_path / "cache")
        payload = make_csv_zip(FIXED_AVAILABILITY_CSV)
        mock_api.add(responses.GET, DOWNLOAD_URL, body=payload, status=200)

        first = _client.get_bytes("api/public/map/downloads/downloadFile/availability/12345")
        second = _client.get_bytes("api/public/map/downloads/downloadFile/availability/12345")

        assert first == second == payload
        # Only one HTTP call was made; the second was a cache hit.
        assert len(mock_api.calls) == 1

    def test_per_call_override_bypasses_the_global_setting(self, mock_api, tmp_path):
        bdcdata.set_cache(False, path=tmp_path / "cache")
        payload = make_csv_zip(FIXED_AVAILABILITY_CSV)
        mock_api.add(responses.GET, DOWNLOAD_URL, body=payload, status=200)
        mock_api.add(responses.GET, DOWNLOAD_URL, body=payload, status=200)

        path = "api/public/map/downloads/downloadFile/availability/12345"
        _client.get_bytes(path, cache=True)
        _client.get_bytes(path, cache=True)

        assert len(mock_api.calls) == 1


class TestCacheInfoAndClear:
    def test_info_reports_files_and_bytes(self, tmp_path):
        bdcdata.set_cache(True, path=tmp_path / "cache")
        _cache.write_cached(_cache.cache_key("https://a.test/1"), b"12345")
        _cache.write_cached(_cache.cache_key("https://a.test/2"), b"678")

        info = bdcdata.cache_info()

        assert info["enabled"] is True
        assert info["files"] == 2
        assert info["bytes"] == 8

    def test_clear_removes_only_our_files(self, tmp_path):
        cache_dir = tmp_path / "cache"
        bdcdata.set_cache(True, path=cache_dir)
        _cache.write_cached(_cache.cache_key("https://a.test/1"), b"data")

        # A file the user happens to keep in the same directory.
        bystander = cache_dir / "my_notes.txt"
        bystander.write_text("do not delete me")

        removed = bdcdata.clear_cache()

        assert removed == 1
        assert bystander.exists()
        assert bystander.read_text() == "do not delete me"
        assert list(cache_dir.glob("*.bdccache")) == []

    def test_clear_on_missing_directory_is_a_no_op(self, tmp_path):
        bdcdata.set_cache(True, path=tmp_path / "never_created")
        assert bdcdata.clear_cache() == 0


class TestResilience:
    def test_unreadable_entry_falls_back_to_the_network(self, mock_api, tmp_path):
        bdcdata.set_cache(True, path=tmp_path / "cache")
        path = "api/public/map/downloads/downloadFile/availability/12345"
        key = _cache.cache_key(f"https://bdc.fcc.gov/{path}")

        # A directory where a file should be: read_bytes will raise OSError.
        entry = tmp_path / "cache" / key
        entry.mkdir(parents=True)

        payload = make_csv_zip(FIXED_AVAILABILITY_CSV)
        mock_api.add(responses.GET, DOWNLOAD_URL, body=payload, status=200)

        assert _client.get_bytes(path) == payload

    def test_partial_writes_do_not_become_cache_hits(self, tmp_path):
        bdcdata.set_cache(True, path=tmp_path / "cache")
        key = _cache.cache_key("https://a.test/1")
        _cache.write_cached(key, b"complete")

        leftovers = list(Path(tmp_path / "cache").glob("*.partial"))
        assert leftovers == []

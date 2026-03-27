"""pricing.py のキャッシュと main.py のユーティリティのテスト。"""

import json
import os
import tempfile
import time

from pricing import _cache_key, _read_cache, _write_cache, CACHE_TTL
from main import compute_diff, to_markdown_table, _retry, format_diff_markdown


class TestPricingCache:
    def test_cache_key_deterministic(self):
        k1 = _cache_key("AmazonEC2", [{"Field": "a", "Value": "b"}])
        k2 = _cache_key("AmazonEC2", [{"Field": "a", "Value": "b"}])
        assert k1 == k2

    def test_cache_key_different_for_different_input(self):
        k1 = _cache_key("AmazonEC2", [{"Field": "a", "Value": "b"}])
        k2 = _cache_key("AmazonRDS", [{"Field": "a", "Value": "b"}])
        assert k1 != k2

    def test_write_and_read_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pricing.CACHE_DIR", str(tmp_path))
        key = "test_key_123"
        _write_cache(key, 0.0416)
        result = _read_cache(key)
        assert result == 0.0416

    def test_read_expired_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pricing.CACHE_DIR", str(tmp_path))
        key = "expired_key"
        path = tmp_path / f"{key}.json"
        path.write_text(json.dumps({"ts": time.time() - CACHE_TTL - 1, "price": 1.0}))
        assert _read_cache(key) is None

    def test_read_nonexistent_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pricing.CACHE_DIR", str(tmp_path))
        assert _read_cache("nonexistent") is None


class TestRetry:
    def test_success_no_retry(self):
        call_count = 0
        def func():
            nonlocal call_count
            call_count += 1
            return "ok"
        assert _retry(func, max_retries=3, base_delay=0) == "ok"
        assert call_count == 1

    def test_retry_on_throttling(self):
        call_count = 0
        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                err = Exception("Rate exceeded")
                raise err
            return "ok"
        assert _retry(func, max_retries=3, base_delay=0) == "ok"
        assert call_count == 3

    def test_no_retry_on_non_throttling(self):
        def func():
            raise ValueError("bad input")
        try:
            _retry(func, max_retries=3, base_delay=0)
            assert False, "Should have raised"
        except ValueError:
            pass

    def test_exhausted_retries(self):
        def func():
            raise Exception("Throttling")
        try:
            _retry(func, max_retries=2, base_delay=0)
            assert False, "Should have raised"
        except Exception as e:
            assert "Throttling" in str(e)


class TestDiff:
    def _make_inventory(self, services):
        return {"services": [{"name": n, "count": c} for n, c in services.items()]}

    def test_no_change(self, tmp_path):
        old = self._make_inventory({"EC2": 3, "S3": 5})
        new = self._make_inventory({"EC2": 3, "S3": 5})
        path = tmp_path / "old.json"
        path.write_text(json.dumps(old))
        assert compute_diff(str(path), new) is None

    def test_count_changed(self, tmp_path):
        old = self._make_inventory({"EC2": 3})
        new = self._make_inventory({"EC2": 5})
        path = tmp_path / "old.json"
        path.write_text(json.dumps(old))
        diff = compute_diff(str(path), new)
        assert diff is not None
        assert diff["changed"][0]["delta"] == 2

    def test_new_service(self, tmp_path):
        old = self._make_inventory({"EC2": 3})
        new = self._make_inventory({"EC2": 3, "S3": 2})
        path = tmp_path / "old.json"
        path.write_text(json.dumps(old))
        diff = compute_diff(str(path), new)
        assert len(diff["added"]) == 1
        assert diff["added"][0]["service"] == "S3"

    def test_removed_service(self, tmp_path):
        old = self._make_inventory({"EC2": 3, "S3": 2})
        new = self._make_inventory({"EC2": 3})
        path = tmp_path / "old.json"
        path.write_text(json.dumps(old))
        diff = compute_diff(str(path), new)
        assert len(diff["removed"]) == 1

    def test_nonexistent_file(self):
        assert compute_diff("/nonexistent/path.json", {"services": []}) is None


class TestMarkdownTable:
    def test_empty_rows(self):
        assert "リソースなし" in to_markdown_table([])

    def test_single_row(self):
        rows = [{"Name": "test", "Value": "123"}]
        result = to_markdown_table(rows)
        assert "| Name | Value |" in result
        assert "| test | 123 |" in result

    def test_multiple_rows(self):
        rows = [{"A": "1"}, {"A": "2"}]
        result = to_markdown_table(rows)
        assert result.count("| A |") == 1  # header only
        assert "| 1 |" in result
        assert "| 2 |" in result


class TestFormatDiffMarkdown:
    def test_none_diff(self):
        assert format_diff_markdown(None) == ""

    def test_with_changes(self):
        diff = {"changed": [{"service": "EC2", "old": 3, "new": 5, "delta": 2}], "added": [], "removed": []}
        result = format_diff_markdown(diff)
        assert "+2" in result
        assert "EC2" in result

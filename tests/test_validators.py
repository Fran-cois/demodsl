"""Tests for demodsl.validators — centralised validation helpers."""

from __future__ import annotations

import io

import pytest

from demodsl.validators import (
    _validate_safe_path,
    _validate_url,
    read_with_size_limit,
    validate_azure_container_name,
    validate_bucket_name,
)


# ── _validate_safe_path ──────────────────────────────────────────────────────


class TestValidateSafePath:
    def test_clean_relative_path(self):
        assert _validate_safe_path("assets/image.png") == "assets/image.png"

    def test_null_byte_rejected(self):
        with pytest.raises(ValueError, match="Null byte"):
            _validate_safe_path("file\x00.txt")

    def test_traversal_rejected(self):
        with pytest.raises(ValueError, match="Path traversal"):
            _validate_safe_path("../etc/passwd")

    def test_normpath_resolves_traversal(self):
        with pytest.raises(ValueError, match="restricted system directory"):
            _validate_safe_path("/tmp/../etc/passwd")

    def test_blocked_unix_prefix(self):
        with pytest.raises(ValueError, match="restricted system directory"):
            _validate_safe_path("/etc/shadow")

    def test_blocked_windows_prefix(self):
        with pytest.raises(ValueError, match="restricted system directory"):
            _validate_safe_path("C:\\Windows\\System32\\config")


# ── _validate_url ─────────────────────────────────────────────────────────────


class TestValidateUrl:
    def test_http_accepted(self):
        assert _validate_url("http://example.com") == "http://example.com"

    def test_https_accepted(self):
        assert _validate_url("https://example.com") == "https://example.com"

    def test_file_scheme_rejected(self):
        with pytest.raises(ValueError, match="not allowed"):
            _validate_url("file:///etc/passwd")

    def test_javascript_scheme_rejected(self):
        with pytest.raises(ValueError, match="not allowed"):
            _validate_url("javascript:alert(1)")

    def test_data_scheme_rejected(self):
        with pytest.raises(ValueError, match="not allowed"):
            _validate_url("data:text/html,<h1>hi</h1>")

    def test_relative_url_accepted(self):
        assert _validate_url("/page") == "/page"


# ── validate_bucket_name ──────────────────────────────────────────────────────


class TestValidateBucketName:
    def test_valid_simple(self):
        assert validate_bucket_name("my-bucket") == "my-bucket"

    def test_valid_with_dots(self):
        assert validate_bucket_name("my.bucket.name") == "my.bucket.name"

    def test_too_short(self):
        with pytest.raises(ValueError, match="Invalid bucket name"):
            validate_bucket_name("ab")

    def test_too_long(self):
        with pytest.raises(ValueError, match="Invalid bucket name"):
            validate_bucket_name("a" * 64)

    def test_uppercase_rejected(self):
        with pytest.raises(ValueError, match="Invalid bucket name"):
            validate_bucket_name("My-Bucket")

    def test_ip_address_rejected(self):
        with pytest.raises(ValueError, match="IP address"):
            validate_bucket_name("192.168.1.1")

    def test_double_dots_rejected(self):
        with pytest.raises(ValueError, match="must not contain"):
            validate_bucket_name("my..bucket")

    def test_starts_with_hyphen_rejected(self):
        with pytest.raises(ValueError, match="Invalid bucket name"):
            validate_bucket_name("-my-bucket")


# ── validate_azure_container_name ─────────────────────────────────────────────


class TestValidateAzureContainerName:
    def test_valid(self):
        assert validate_azure_container_name("my-container") == "my-container"

    def test_dots_rejected(self):
        with pytest.raises(ValueError, match="Invalid container name"):
            validate_azure_container_name("my.container")

    def test_uppercase_rejected(self):
        with pytest.raises(ValueError, match="Invalid container name"):
            validate_azure_container_name("MyContainer")


# ── read_with_size_limit ──────────────────────────────────────────────────────


class TestReadWithSizeLimit:
    def test_within_limit(self):
        data = b"hello world"
        result = read_with_size_limit(io.BytesIO(data), max_bytes=1024)
        assert result == data

    def test_exact_limit(self):
        data = b"x" * 100
        result = read_with_size_limit(io.BytesIO(data), max_bytes=100)
        assert result == data

    def test_exceeds_limit(self):
        data = b"x" * 200
        with pytest.raises(ValueError, match="size limit"):
            read_with_size_limit(io.BytesIO(data), max_bytes=100)

    def test_empty_response(self):
        result = read_with_size_limit(io.BytesIO(b""), max_bytes=100)
        assert result == b""

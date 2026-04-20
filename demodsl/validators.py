"""Centralised validation helpers for DemoDSL.

Every path, URL, bucket-name or download-size check lives here so that
validation logic is never duplicated across modules.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse

# ── Path safety ──────────────────────────────────────────────────────────────

_BLOCKED_PREFIXES = (
    "/etc",
    "/sys",
    "/proc",
    "/dev",
    "/var/run",
    "/tmp",
    "/root",
    "/home",
)

_BLOCKED_PREFIXES_WIN = (
    "c:\\windows",
    "c:\\system",
    "c:\\users",
    "c:\\programdata",
)


def _validate_safe_path(v: str) -> str:
    """Reject paths with directory traversal or pointing to sensitive system dirs."""
    if "\x00" in v:
        raise ValueError(f"Null byte in path is not allowed: {v!r}")

    # Normalize to resolve sequences like tmp/../etc/passwd
    normalized = os.path.normpath(v).replace("\\", "/")
    if ".." in normalized.split("/"):
        raise ValueError(f"Path traversal ('..') is not allowed: {v}")

    lower = normalized.lower()
    for prefix in _BLOCKED_PREFIXES:
        if lower.startswith(prefix):
            raise ValueError(f"Path points to a restricted system directory: {v}")
    win_lower = v.lower().replace("/", "\\")
    for prefix in _BLOCKED_PREFIXES_WIN:
        if win_lower.startswith(prefix):
            raise ValueError(f"Path points to a restricted system directory: {v}")
    return v


# ── URL safety ────────────────────────────────────────────────────────────────

_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})


def _validate_url(v: str) -> str:
    """Reject URLs with dangerous schemes (file://, javascript:, data:, etc.)."""
    parsed = urlparse(v)
    if parsed.scheme and parsed.scheme not in _ALLOWED_URL_SCHEMES:
        raise ValueError(
            f"URL scheme '{parsed.scheme}' is not allowed. "
            f"Only {sorted(_ALLOWED_URL_SCHEMES)} are accepted: {v}"
        )
    return v


# ── Cloud bucket / container name ─────────────────────────────────────────────

# S3 & GCS bucket naming rules:
#   - 3-63 characters
#   - lowercase letters, digits, hyphens, periods
#   - must start and end with a letter or digit
#   - must not resemble an IP address
#   - must not contain ".."
_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$")
_IP_LIKE_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

# Azure container names: 3-63 chars, lowercase + digits + hyphens only (no dots)
_AZURE_CONTAINER_RE = re.compile(r"^[a-z0-9](?:[a-z0-9\-]{1,61}[a-z0-9])?$")


def validate_bucket_name(name: str) -> str:
    """Validate an S3/GCS bucket name according to AWS/GCP naming rules."""
    if not _BUCKET_NAME_RE.match(name):
        raise ValueError(
            f"Invalid bucket name '{name}': must be 3-63 chars, lowercase "
            "alphanumeric with hyphens/periods, starting and ending with "
            "a letter or digit."
        )
    if ".." in name:
        raise ValueError(f"Invalid bucket name '{name}': must not contain '..'")
    if _IP_LIKE_RE.match(name):
        raise ValueError(
            f"Invalid bucket name '{name}': must not resemble an IP address."
        )
    return name


def validate_azure_container_name(name: str) -> str:
    """Validate an Azure Blob Storage container name."""
    if not _AZURE_CONTAINER_RE.match(name):
        raise ValueError(
            f"Invalid container name '{name}': must be 3-63 chars, lowercase "
            "alphanumeric with hyphens, starting and ending with a letter or digit."
        )
    return name


# ── Download size limiting ────────────────────────────────────────────────────

_CHUNK_SIZE = 64 * 1024  # 64 KiB


def read_with_size_limit(resp, max_bytes: int) -> bytes:
    """Read an HTTP response in chunks, raising if *max_bytes* is exceeded.

    Works with:
    - ``urllib.request`` response objects (``read(size)`` method)
    - ``httpx`` streaming responses (``iter_bytes(chunk_size)`` method)
    - any file-like with a ``read(size)`` method
    """
    chunks: list[bytes] = []
    total = 0

    def _check(data: bytes) -> None:
        nonlocal total
        total += len(data)
        if total > max_bytes:
            raise ValueError(
                f"Download exceeds the {max_bytes / (1024 * 1024):.0f} MB "
                "size limit — aborting."
            )
        chunks.append(data)

    # httpx streaming responses expose iter_bytes()
    if hasattr(resp, "iter_bytes"):
        for chunk in resp.iter_bytes(_CHUNK_SIZE):
            if not chunk:
                break
            _check(chunk)
    else:
        while True:
            chunk = resp.read(_CHUNK_SIZE)
            if not chunk:
                break
            _check(chunk)

    return b"".join(chunks)

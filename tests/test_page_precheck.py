"""Tests for demodsl.page_precheck."""

from __future__ import annotations

from email.message import Message
from unittest.mock import patch

from demodsl.page_precheck import (
    PageProbeResult,
    _classify_protection,
    precheck_urls,
    probe_page_accessible,
)


def _hdrs(pairs: dict[str, str]) -> Message:
    """Build an email.Message that mimics urllib's HTTPMessage."""
    msg = Message()
    for k, v in pairs.items():
        msg[k] = v
    return msg


class _FakeResponse:
    def __init__(
        self,
        headers: Message | dict[str, str],
        body: bytes = b"",
        status: int = 200,
    ) -> None:
        self.headers = headers if isinstance(headers, Message) else _hdrs(headers)
        self._body = body
        self.status = status

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *a: object) -> None:
        pass

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            return self._body
        return self._body[:n]


class TestClassifyProtection:
    def test_cloudflare_mitigated_header(self) -> None:
        prot, reason = _classify_protection(_hdrs({"cf-mitigated": "challenge"}), "", 200)
        assert prot == "cloudflare"
        assert "cf-mitigated" in reason

    def test_cloudflare_server_403(self) -> None:
        prot, _ = _classify_protection(_hdrs({"Server": "cloudflare"}), "", 403)
        assert prot == "cloudflare"

    def test_cloudflare_body_marker(self) -> None:
        prot, _ = _classify_protection(_hdrs({}), "<html>just a moment...</html>", 200)
        assert prot == "cloudflare"

    def test_datadome_header(self) -> None:
        prot, _ = _classify_protection(_hdrs({"x-dd-b": "1"}), "", 403)
        assert prot == "datadome"

    def test_datadome_cookie(self) -> None:
        h = _hdrs({"Set-Cookie": "datadome=abc; Path=/"})
        prot, _ = _classify_protection(h, "", 403)
        assert prot == "datadome"

    def test_datadome_body(self) -> None:
        prot, _ = _classify_protection(
            _hdrs({}), "<a href='https://geo.captcha-delivery.com/'>", 403
        )
        assert prot == "datadome"

    def test_clean_response_returns_none(self) -> None:
        prot, _ = _classify_protection(_hdrs({"Server": "nginx"}), "<html>hello</html>", 200)
        assert prot is None

    def test_imperva_body(self) -> None:
        prot, _ = _classify_protection(_hdrs({}), "<html>incapsula incident id: 123</html>", 403)
        assert prot == "imperva"

    def test_imperva_header(self) -> None:
        prot, _ = _classify_protection(_hdrs({"X-Iinfo": "1-2-3"}), "", 200)
        assert prot == "imperva"

    def test_aws_waf_header(self) -> None:
        prot, _ = _classify_protection(_hdrs({"x-amzn-waf-action": "challenge"}), "", 405)
        assert prot == "aws-waf"

    def test_aws_waf_cookie(self) -> None:
        prot, _ = _classify_protection(_hdrs({"Set-Cookie": "aws-waf-token=xyz; Path=/"}), "", 200)
        assert prot == "aws-waf"

    def test_sucuri_server(self) -> None:
        prot, _ = _classify_protection(_hdrs({"Server": "Sucuri/Cloudproxy"}), "", 200)
        assert prot == "sucuri"

    def test_kasada_header(self) -> None:
        prot, _ = _classify_protection(_hdrs({"x-kpsdk-ct": "1"}), "", 200)
        assert prot == "kasada"

    def test_akamai_bot_manager_cookie(self) -> None:
        prot, _ = _classify_protection(_hdrs({"Set-Cookie": "_abck=abc; ak_bmsc=def"}), "", 429)
        assert prot == "akamai"

    def test_recaptcha_interstitial(self) -> None:
        body = "<html><div class='g-recaptcha'></div></html>"
        prot, _ = _classify_protection(_hdrs({}), body, 403)
        assert prot == "captcha"

    def test_recaptcha_on_normal_page_not_flagged(self) -> None:
        # reCAPTCHA embedded on a form inside a long page — not a gate.
        body = "g-recaptcha " + ("x" * 9000)
        prot, _ = _classify_protection(_hdrs({}), body, 200)
        assert prot is None


class TestProbePageAccessible:
    def test_clean_200_is_accessible(self) -> None:
        with patch("demodsl.page_precheck._open") as mock_open:
            mock_open.return_value = _FakeResponse(
                {"Server": "nginx"}, b"<html>ok</html>", status=200
            )
            r = probe_page_accessible("https://example.com")
        assert r.accessible is True
        assert r.protection is None
        assert r.status == 200

    def test_cloudflare_challenge_blocked(self) -> None:
        with patch("demodsl.page_precheck._open") as mock_open:
            mock_open.return_value = _FakeResponse(
                {"Server": "cloudflare", "cf-ray": "abc"},
                b"<html>Just a moment...</html>",
                status=403,
            )
            r = probe_page_accessible("https://example.com")
        assert r.accessible is False
        assert r.protection == "cloudflare"

    def test_datadome_blocked(self) -> None:
        with patch("demodsl.page_precheck._open") as mock_open:
            mock_open.return_value = _FakeResponse({"x-dd-b": "1"}, b"", status=403)
            r = probe_page_accessible("https://example.com")
        assert r.accessible is False
        assert r.protection == "datadome"

    def test_network_failure_passes_through(self) -> None:
        with patch("demodsl.page_precheck._open", side_effect=OSError("dns")):
            r = probe_page_accessible("https://example.com")
        assert r.accessible is True
        assert "probe skipped" in r.reason

    def test_plain_500_marked_inaccessible(self) -> None:
        import urllib.error

        err = urllib.error.HTTPError(
            "https://example.com", 500, "boom", _hdrs({"Server": "nginx"}), None
        )
        with patch("demodsl.page_precheck._open", side_effect=err):
            r = probe_page_accessible("https://example.com")
        assert r.accessible is False
        assert r.status == 500
        assert r.protection is None

    def test_429_friendly_reason(self) -> None:
        import urllib.error

        err = urllib.error.HTTPError(
            "https://example.com", 429, "slow down", _hdrs({"Server": "nginx"}), None
        )
        with patch("demodsl.page_precheck._open", side_effect=err):
            r = probe_page_accessible("https://example.com")
        assert r.accessible is False
        assert "rate limited" in r.reason

    def test_451_friendly_reason(self) -> None:
        import urllib.error

        err = urllib.error.HTTPError(
            "https://example.com", 451, "blocked", _hdrs({"Server": "nginx"}), None
        )
        with patch("demodsl.page_precheck._open", side_effect=err):
            r = probe_page_accessible("https://example.com")
        assert r.accessible is False
        assert "legal reasons" in r.reason


class TestPrecheckUrls:
    def test_skips_none_and_non_http(self) -> None:
        with patch("demodsl.page_precheck.probe_page_accessible") as mock_probe:
            mock_probe.return_value = PageProbeResult("https://x", True)
            results = precheck_urls([None, "", "about:blank", "https://x"])
        assert len(results) == 1
        mock_probe.assert_called_once()

    def test_dedupes_urls(self) -> None:
        with patch("demodsl.page_precheck.probe_page_accessible") as mock_probe:
            mock_probe.return_value = PageProbeResult("https://x", True)
            results = precheck_urls(["https://x", "https://x"])
        assert len(results) == 1

    def test_warns_on_blocked(self, caplog) -> None:
        import logging

        with patch("demodsl.page_precheck.probe_page_accessible") as mock_probe:
            mock_probe.return_value = PageProbeResult(
                "https://x", False, protection="cloudflare", reason="blocked", status=403
            )
            with caplog.at_level(logging.WARNING, logger="demodsl.page_precheck"):
                precheck_urls(["https://x"])
        joined = " ".join(r.message for r in caplog.records)
        assert "cloudflare" in joined

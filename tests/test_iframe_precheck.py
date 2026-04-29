"""Tests for demodsl.iframe_precheck."""

from __future__ import annotations

from unittest.mock import patch

from demodsl.iframe_precheck import (
    _csp_blocks_embedding,
    auto_record_blocked_urls,
    probe_url_embeddable,
    sanitize_secondary_windows,
)


class _FakeResponse:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *a: object) -> None:
        pass

    def read(self) -> bytes:
        return b""


class TestCspParser:
    def test_frame_ancestors_none_blocks(self) -> None:
        assert _csp_blocks_embedding("frame-ancestors 'none'") is True

    def test_frame_ancestors_self_blocks(self) -> None:
        assert _csp_blocks_embedding("frame-ancestors 'self'") is True

    def test_frame_ancestors_wildcard_allows(self) -> None:
        assert _csp_blocks_embedding("frame-ancestors *") is False

    def test_frame_ancestors_https_scheme_allows(self) -> None:
        assert _csp_blocks_embedding("default-src 'self'; frame-ancestors https:") is False

    def test_no_frame_ancestors_allows(self) -> None:
        assert _csp_blocks_embedding("default-src 'self'") is False

    def test_empty_csp_allows(self) -> None:
        assert _csp_blocks_embedding("") is False


class TestProbeUrlEmbeddable:
    def test_xframe_deny_blocks(self) -> None:
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _FakeResponse({"X-Frame-Options": "DENY"})
            r = probe_url_embeddable("https://example.com")
        assert r.embeddable is False
        assert "X-Frame-Options" in r.reason

    def test_xframe_sameorigin_blocks(self) -> None:
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _FakeResponse({"X-Frame-Options": "SAMEORIGIN"})
            r = probe_url_embeddable("https://example.com")
        assert r.embeddable is False

    def test_csp_frame_ancestors_none_blocks(self) -> None:
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _FakeResponse(
                {"Content-Security-Policy": "frame-ancestors 'none'"}
            )
            r = probe_url_embeddable("https://example.com")
        assert r.embeddable is False
        assert "CSP" in r.reason

    def test_no_restrictive_headers_allows(self) -> None:
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _FakeResponse({"Content-Type": "text/html"})
            r = probe_url_embeddable("https://example.com")
        assert r.embeddable is True

    def test_network_failure_passes_through(self) -> None:
        with patch("urllib.request.urlopen", side_effect=OSError("unreachable")):
            r = probe_url_embeddable("https://example.com")
        # Network errors should not block the demo
        assert r.embeddable is True


class TestSanitizeSecondaryWindows:
    def test_none_is_noop(self) -> None:
        assert sanitize_secondary_windows(None) is None

    def test_empty_is_noop(self) -> None:
        assert sanitize_secondary_windows([]) == []

    def test_strips_blocked_url(self) -> None:
        windows = [
            {"title": "GitHub", "url": "https://github.com"},
            {"title": "No URL", "background_color": "#000"},
        ]
        with patch("demodsl.iframe_precheck.probe_url_embeddable") as mock_probe:
            from demodsl.iframe_precheck import IframeProbeResult

            mock_probe.return_value = IframeProbeResult(
                "https://github.com", False, "X-Frame-Options: DENY"
            )
            sanitize_secondary_windows(windows)
        assert windows[0]["url"] is None
        assert "title" in windows[1]

    def test_keeps_embeddable_url(self) -> None:
        windows = [{"title": "example", "url": "https://example.com"}]
        with patch("demodsl.iframe_precheck.probe_url_embeddable") as mock_probe:
            from demodsl.iframe_precheck import IframeProbeResult

            mock_probe.return_value = IframeProbeResult("https://example.com", True)
            sanitize_secondary_windows(windows)
        assert windows[0]["url"] == "https://example.com"


class TestAutoRecordBlockedUrls:
    def test_embeddable_url_untouched(self) -> None:
        windows = [{"title": "ok", "url": "https://example.com", "width": 600, "height": 400}]
        with patch("demodsl.iframe_precheck.probe_url_embeddable") as mock_probe:
            from demodsl.iframe_precheck import IframeProbeResult

            mock_probe.return_value = IframeProbeResult("https://example.com", True)
            auto_record_blocked_urls(windows)
        assert windows[0]["url"] == "https://example.com"
        assert "_video_path" not in windows[0]

    def test_blocked_url_records_video(self, tmp_path) -> None:
        fake_video = tmp_path / "fake.mp4"
        fake_video.write_bytes(b"fake mp4 bytes")
        windows = [
            {
                "title": "GitHub",
                "url": "https://github.com",
                "width": 620,
                "height": 400,
            }
        ]
        with (
            patch("demodsl.iframe_precheck.probe_url_embeddable") as mock_probe,
            patch("demodsl.sub_recorder.record_sub_demo") as mock_record,
        ):
            from demodsl.iframe_precheck import IframeProbeResult

            mock_probe.return_value = IframeProbeResult(
                "https://github.com", False, "X-Frame-Options: DENY"
            )
            mock_record.return_value = fake_video
            auto_record_blocked_urls(windows)
        assert windows[0]["url"] is None
        assert windows[0]["_video_path"] == str(fake_video)
        mock_record.assert_called_once_with(
            "https://github.com", width=620, height=400, cache_dir=None
        )

    def test_blocked_url_recording_fails_falls_back(self) -> None:
        windows = [
            {
                "title": "GitHub",
                "url": "https://github.com",
                "width": 600,
                "height": 400,
            }
        ]
        with (
            patch("demodsl.iframe_precheck.probe_url_embeddable") as mock_probe,
            patch("demodsl.sub_recorder.record_sub_demo") as mock_record,
        ):
            from demodsl.iframe_precheck import IframeProbeResult

            mock_probe.return_value = IframeProbeResult(
                "https://github.com", False, "X-Frame-Options: DENY"
            )
            mock_record.return_value = None
            auto_record_blocked_urls(windows)
        assert windows[0]["url"] is None
        assert "_video_path" not in windows[0]

    def test_disabled_strips_url(self) -> None:
        windows = [{"title": "GitHub", "url": "https://github.com"}]
        with (
            patch("demodsl.iframe_precheck.probe_url_embeddable") as mock_probe,
            patch("demodsl.sub_recorder.record_sub_demo") as mock_record,
        ):
            from demodsl.iframe_precheck import IframeProbeResult

            mock_probe.return_value = IframeProbeResult(
                "https://github.com", False, "X-Frame-Options: DENY"
            )
            auto_record_blocked_urls(windows, enabled=False)
        assert windows[0]["url"] is None
        assert "_video_path" not in windows[0]
        mock_record.assert_not_called()

"""Regression tests for GitHub issues #29-#32.

- #29 crawl ranks page content by rendered weight, not DOM order
- #30 ``pace()`` no longer ships a timeline shorter than the render
- #31 the social export is honest about what it truncates and reframes
- #32 the subtitle burn has a real safe area
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.discover.controller import _PAGE_CONTENT_JS, pick_hero
from demodsl.discover.explore import SitePage, crawl_site
from demodsl.effects.subtitle import (
    MAX_BLOCK_RATIO,
    SAFE_MARGIN_RATIO,
    build_subtitle_entries,
    generate_ass_subtitle,
    max_chars_per_line,
    safe_horizontal_margins,
)
from demodsl.models import DemoConfig, Metadata
from demodsl.orchestrators.export import ExportOrchestrator
from demodsl.orchestrators.post_processing import PostProcessingOrchestrator
from demodsl.recipe import EFFECT_MAX, LONG_BEAT_WARN, beat_overruns, pace, walkthrough

# ── Issue #29: the "hero" is ranked, not the first node in the DOM ──────────


class TestIssue29RankedPageContent:
    # Linear's actual failure: a mockup caption comes first in the DOM, the
    # real headline is a div, and the footer nav trails behind.
    CANDIDATES = [
        {
            "text": "Faster app launch",
            "tag": "h3",
            "fontSizePx": 14,
            "viewportY": 0.6,
            "insideMockup": True,
            "furniture": False,
            "score": 12,
        },
        {
            "text": "The product development system",
            "tag": "div",
            "fontSizePx": 72,
            "viewportY": 0.3,
            "insideMockup": False,
            "furniture": False,
            "score": 68,
        },
        {
            "text": "Company",
            "tag": "h4",
            "fontSizePx": 14,
            "viewportY": 6.2,
            "insideMockup": False,
            "furniture": True,
            "score": -46,
        },
    ]

    def test_hero_skips_a_caption_inside_a_product_mockup(self) -> None:
        assert pick_hero(self.CANDIDATES) == "The product development system"

    def test_hero_skips_footer_furniture(self) -> None:
        assert pick_hero([self.CANDIDATES[2], self.CANDIDATES[1]]) != "Company"

    def test_hero_of_nothing_is_empty(self) -> None:
        assert pick_hero([]) == ""

    def test_hero_falls_back_when_everything_is_below_the_fold(self) -> None:
        deep = [{"text": "Way down", "viewportY": 12.0, "insideMockup": False}]
        assert pick_hero(deep) == "Way down"

    def test_extraction_js_is_not_tag_gated(self) -> None:
        """A modern hero is a div/span — a h1,h2,h3 selector never sees it."""
        assert "querySelectorAll('h1,h2,h3" not in _PAGE_CONTENT_JS
        assert "getBoundingClientRect" in _PAGE_CONTENT_JS
        assert "getComputedStyle" in _PAGE_CONTENT_JS
        assert "fontSize" in _PAGE_CONTENT_JS

    def test_extraction_js_filters_on_visibility(self) -> None:
        for guard in ("display", "visibility", "opacity", "aria-hidden"):
            assert guard in _PAGE_CONTENT_JS

    def test_crawl_records_the_hero_on_the_page(self) -> None:
        class Env:
            def navigate(self, url: str) -> None: ...
            def extract_elements(self) -> list[dict]:
                return []

            def current_url(self) -> str:
                return "https://acme.com"

            def title(self) -> str:
                return "Acme"

            def page_content(self, limit: int = 12) -> list[dict]:
                return TestIssue29RankedPageContent.CANDIDATES

        graph = crawl_site(Env(), start_url="https://acme.com", max_pages=1)
        page = graph.page("https://acme.com")
        assert page is not None
        assert page.hero == "The product development system"
        # Backwards compatible: the flat list survives, weight-ordered.
        assert page.headings[0] == "Faster app launch"

    def test_crawl_still_works_with_a_headings_only_environment(self) -> None:
        class LegacyEnv:
            def navigate(self, url: str) -> None: ...
            def extract_elements(self) -> list[dict]:
                return []

            def current_url(self) -> str:
                return "https://acme.com"

            def title(self) -> str:
                return "Acme"

            def page_headings(self, limit: int = 12) -> list[str]:
                return ["Only a flat list"]

        graph = crawl_site(LegacyEnv(), start_url="https://acme.com", max_pages=1)
        page = graph.page("https://acme.com")
        assert page is not None
        assert page.headings == ["Only a flat list"]

    def test_graph_serialises_the_hero(self) -> None:
        page = SitePage(url="https://acme.com", title="Acme", hero="Real headline")
        assert page.hero == "Real headline"


# ── Issue #30: the declared timeline must match the rendered one ─────────────


class TestIssue30PacingIsHonest:
    LONG = " ".join(["word"] * 60)  # ~24s of narration

    def test_wait_is_not_clamped_under_the_spoken_length(self) -> None:
        assert pace(self.LONG) > LONG_BEAT_WARN

    def test_walkthrough_timeline_covers_its_own_narration(self) -> None:
        """The sum of `wait` must not undershoot what the voice will play."""
        cfg = walkthrough(
            company="Acme",
            url="https://acme.com",
            beats=[{"locator": {"type": "css", "value": "h1"}, "narration": self.LONG}],
        )
        steps = cfg["scenarios"][0]["steps"]
        beat = next(s for s in steps if s.get("narration") == self.LONG)
        assert beat["wait"] >= len(self.LONG.split()) / 2.6

    def test_effects_outlive_the_beat_they_mark(self) -> None:
        """A mark that expires mid-sentence leaves a frozen frame on screen."""
        cfg = walkthrough(
            company="Acme",
            url="https://acme.com",
            beats=[
                {
                    "locator": {"type": "css", "value": "h1"},
                    "narration": self.LONG,
                    "sentiment": "bad",
                }
            ],
        )
        beat = next(s for s in cfg["scenarios"][0]["steps"] if s.get("narration") == self.LONG)
        assert beat["effects"], "the beat should still be marked"
        for effect in beat["effects"]:
            if "duration" in effect:
                assert effect["duration"] >= min(beat["wait"], EFFECT_MAX)

    def test_over_long_copy_is_reported(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="demodsl.recipe"):
            walkthrough(
                company="Acme",
                url="https://acme.com",
                beats=[{"locator": {"type": "css", "value": "h1"}, "narration": self.LONG}],
            )
        assert any(
            "narration" in r.message.lower() or "beat" in r.message.lower() for r in caplog.records
        )

    def test_short_copy_is_silent(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="demodsl.recipe"):
            walkthrough(
                company="Acme",
                url="https://acme.com",
                beats=[{"locator": {"type": "css", "value": "h1"}, "narration": "Short."}],
            )
        assert not caplog.records

    def test_beat_overruns_threshold(self) -> None:
        assert beat_overruns(self.LONG)
        assert not beat_overruns("Three short words.")

    def test_walkthrough_no_longer_ships_a_blur_pad_crop(self) -> None:
        """#31: a 9:16 deliverable is its own render, never a crop."""
        cfg = walkthrough(
            company="Acme",
            url="https://acme.com",
            beats=[{"locator": {"type": "css", "value": "h1"}, "narration": "Hi."}],
        )
        assert "social" not in cfg["output"]


# ── Issue #31: the social export must not lie about what it dropped ─────────


def _social_config(**social: object) -> DemoConfig:
    return DemoConfig(
        metadata=Metadata(title="Test"),
        output={"filename": "demo.mp4", "social": [{"platform": "tiktok", **social}]},
    )


class TestIssue31HonestSocialExport:
    def test_truncation_is_logged_loudly(self, caplog: pytest.LogCaptureFixture) -> None:
        with (
            patch.object(ExportOrchestrator, "_probe_duration", return_value=141.0),
            caplog.at_level(logging.WARNING, logger="demodsl.orchestrators.export"),
        ):
            cut = ExportOrchestrator._honest_cut(Path("demo.mp4"), 60.0, "tiktok")
        assert cut == 60.0
        assert any("max_duration" in r.message for r in caplog.records)

    def test_cut_snaps_back_to_the_last_complete_step(self) -> None:
        with patch.object(ExportOrchestrator, "_probe_duration", return_value=141.0):
            cut = ExportOrchestrator._honest_cut(
                Path("demo.mp4"), 60.0, "tiktok", [0.0, 20.0, 42.5, 71.0, 120.0]
            )
        assert cut == 42.5

    def test_no_cut_when_the_render_already_fits(self) -> None:
        with patch.object(ExportOrchestrator, "_probe_duration", return_value=25.0):
            assert ExportOrchestrator._honest_cut(Path("d.mp4"), 60.0, "tiktok") is None

    def test_unmeasurable_source_keeps_the_declared_cap(self) -> None:
        with patch.object(ExportOrchestrator, "_probe_duration", return_value=None):
            assert ExportOrchestrator._honest_cut(Path("d.mp4"), 60.0, "tiktok") == 60.0

    def test_blur_pad_fills_most_of_the_vertical_frame(self, tmp_path: Path) -> None:
        """A 1080x608 strip in a 1920-tall canvas is 68 % blur — unpublishable."""
        orch = ExportOrchestrator(_social_config(crop_mode="blur_pad"))
        source = tmp_path / "demo.mp4"
        source.write_bytes(b"\x00" * 10)

        with (
            patch("subprocess.run") as mock_run,
            patch.object(ExportOrchestrator, "verify_video", return_value=True),
            patch.object(ExportOrchestrator, "_probe_duration", return_value=30.0),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            orch.export_social(source, tmp_path)

        cmd = mock_run.call_args.args[0]
        graph = cmd[cmd.index("-filter_complex") + 1]
        # The sharp copy is sized by height now, not stretched to the width.
        fg_height = int(graph.split("[fg]scale=-2:")[1].split(",")[0])
        assert fg_height / 1920 >= 0.6

    def test_blur_pad_warns_that_it_is_a_reframe(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        orch = ExportOrchestrator(_social_config(crop_mode="blur_pad"))
        source = tmp_path / "demo.mp4"
        source.write_bytes(b"\x00" * 10)

        with (
            patch("subprocess.run") as mock_run,
            patch.object(ExportOrchestrator, "verify_video", return_value=True),
            patch.object(ExportOrchestrator, "_probe_duration", return_value=30.0),
            caplog.at_level(logging.WARNING, logger="demodsl.orchestrators.export"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            orch.export_social(source, tmp_path)

        assert any("blurred padding" in r.message for r in caplog.records)

    def test_engine_forwards_step_timestamps(self) -> None:
        from demodsl.engine import DemoEngine

        assert "step_timestamps" in DemoEngine._run_social_exports.__code__.co_varnames


# ── Issue #32: the subtitle burn needs a safe area ──────────────────────────


class TestIssue32SubtitleSafeArea:
    CFG = {"style": "classic", "font_size": 48, "position": "bottom"}

    def _ass(self, tmp_path: Path, **kw: object) -> str:
        entries = [{"start": 0.0, "end": 2.0, "text": "Hello there", "words": []}]
        out = tmp_path / "s.ass"
        generate_ass_subtitle(entries, dict(self.CFG), out, **kw)  # type: ignore[arg-type]
        return out.read_text(encoding="utf-8")

    @staticmethod
    def _default_style(text: str) -> list[str]:
        """Fields of the ``Style: Default,…`` line (MarginL/R/V are [-4:-1])."""
        line = next(ln for ln in text.splitlines() if ln.startswith("Style: Default,"))
        return line.split(",")

    def test_script_resolution_matches_the_real_frame(self, tmp_path: Path) -> None:
        """A 1080-wide PlayResX on a 1920-tall render rescales every margin."""
        text = self._ass(tmp_path, frame_size=(1080, 1920))
        assert "PlayResX: 1080" in text
        assert "PlayResY: 1920" in text

    def test_bottom_margin_is_a_share_of_the_frame(self, tmp_path: Path) -> None:
        fields = self._default_style(self._ass(tmp_path, frame_size=(1920, 1080)))
        margin_v = int(fields[-2])
        assert margin_v >= 1080 * SAFE_MARGIN_RATIO * 0.99
        assert margin_v > 40  # the old flat value

    def test_corner_overlays_inset_the_subtitle_box(self, tmp_path: Path) -> None:
        fields = self._default_style(
            self._ass(
                tmp_path,
                frame_size=(1920, 1080),
                reserved_corners={"bottom-left": 264, "bottom-right": 168},
            )
        )
        margin_l, margin_r = int(fields[-4]), int(fields[-3])
        assert margin_l > 264
        assert margin_r > 168

    def test_margins_never_swallow_the_frame(self) -> None:
        left, right = safe_horizontal_margins(
            1920, "bottom", {}, {"bottom-left": 900, "bottom-right": 900}
        )
        assert left + right <= 1920 * 0.5 + 1

    def test_centered_subtitles_keep_the_default_gutters(self) -> None:
        left, right = safe_horizontal_margins(1920, "center", {}, {"bottom-left": 900})
        assert left == right

    def test_lines_are_bounded_by_rendered_width(self) -> None:
        """Eight long words wrap to three lines at 48px — that is the overflow."""
        text = " ".join(["internationalisation"] * 8)
        entries = build_subtitle_entries(
            {0: text},
            [0.0],
            {0: 8.0},
            max_words_per_line=8,
            max_chars=max_chars_per_line(48, 1920, 80, 80),
        )
        assert len(entries) > 1
        budget = max_chars_per_line(48, 1920, 80, 80)
        assert all(len(e["text"]) <= budget for e in entries)

    def test_word_count_still_caps_a_line(self) -> None:
        entries = build_subtitle_entries(
            {0: " ".join(["a"] * 20)}, [0.0], {0: 8.0}, max_words_per_line=4
        )
        assert all(len(e["text"].split()) <= 4 for e in entries)

    def test_chunking_loses_no_words(self) -> None:
        words = ["alpha", "bravo", "charlie", "deltaaaaaaaaaaaaa", "echo", "foxtrot"]
        entries = build_subtitle_entries(
            {0: " ".join(words)}, [0.0], {0: 6.0}, max_words_per_line=8, max_chars=20
        )
        assert " ".join(e["text"] for e in entries).split() == words

    def test_max_chars_scales_with_the_font(self) -> None:
        assert max_chars_per_line(96, 1920) < max_chars_per_line(32, 1920)

    def test_orchestrator_reports_the_corners_its_overlays_own(self) -> None:
        cfg = DemoConfig(
            metadata=Metadata(title="T"),
            video={
                "reviewer": {"enabled": True, "name": "A", "position": "bottom-left", "size": 88},
                "live_avatar": {"enabled": True, "position": "bottom-right", "size": 168},
            },
        )
        orch = PostProcessingOrchestrator(cfg, MagicMock())
        reserved = orch.reserved_corners()
        assert reserved["bottom-left"] > 88  # a badge is wider than it is tall
        assert reserved["bottom-right"] == 168

    def test_disabled_overlays_reserve_nothing(self) -> None:
        cfg = DemoConfig(
            metadata=Metadata(title="T"),
            video={"reviewer": {"enabled": False, "name": "A", "position": "bottom-left"}},
        )
        orch = PostProcessingOrchestrator(cfg, MagicMock())
        assert orch.reserved_corners() == {}

    def test_block_height_is_bounded(self) -> None:
        assert 0 < MAX_BLOCK_RATIO < 0.5

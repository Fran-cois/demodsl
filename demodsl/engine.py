"""DemoEngine — main orchestrator for DemoDSL."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from demodsl.models.rendering import DeviceRendering

from demodsl import __version__
from demodsl.config_loader import load_config_with_library
from demodsl.determinism import apply_determinism
from demodsl.effects.browser_effects import register_all_browser_effects
from demodsl.effects.post_effects import register_all_post_effects
from demodsl.effects.registry import EffectRegistry
from demodsl.encoding import x264_args
from demodsl.models import DemoConfig
from demodsl.models.video import Transitions
from demodsl.orchestrators.export import ExportOrchestrator
from demodsl.orchestrators.narration import NarrationOrchestrator
from demodsl.orchestrators.post_processing import PostProcessingOrchestrator
from demodsl.orchestrators.scenario import ScenarioOrchestrator
from demodsl.pipeline.run_cache import RunCache
from demodsl.pipeline.segment_cache import parse_only_steps, plan_segments
from demodsl.pipeline.stages import PipelineContext, build_chain
from demodsl.pipeline.workspace import Workspace
from demodsl.stats import StatsStore
from demodsl.theme import apply_theme, resolve_theme

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConcatResult:
    """Outcome of joining the per-scenario recordings.

    ``boundaries`` are the junctions on the *butt-joined* timeline the step
    timestamps were built on, and ``shift`` the seconds each junction removes
    (0 when the clips were simply appended).
    """

    path: Path
    boundaries: tuple[float, ...] = field(default=())
    shift: float = 0.0

    def remap(self, t: float) -> float:
        """Move a butt-joined timestamp onto the cross-faded timeline."""
        if self.shift <= 0:
            return t
        crossed = sum(1 for b in self.boundaries if t >= b)
        return max(0.0, t - crossed * self.shift)


@dataclass(frozen=True)
class StepEffectResult:
    """Outcome of baking per-step ``freeze_frame``/``speed_ramp`` into the video.

    Unlike :class:`ConcatResult` (one uniform shift), each step effect moves
    everything *after* its own boundary by its own signed delta — a freeze
    adds time, a speed ramp can add or remove it depending on whether it
    nets faster or slower than 1x. ``shifts`` is ``(original_boundary,
    delta_seconds)`` pairs, unordered; a timestamp past several boundaries
    accumulates all of their deltas.
    """

    path: Path
    shifts: tuple[tuple[float, float], ...] = ()

    def remap(self, t: float) -> float:
        """Move a pre-effect timestamp onto the post-effect timeline."""
        if not self.shifts:
            return t
        return max(0.0, t + sum(delta for boundary, delta in self.shifts if t >= boundary))


@lru_cache(maxsize=1)
def _ffmpeg_has_drawtext() -> bool:
    """Whether the installed ffmpeg exposes the ``drawtext`` filter.

    ffmpeg builds compiled without ``libfreetype`` have no ``drawtext``,
    which makes any text-burning filter fail with an opaque multi-line
    dump.  When the probe itself is inconclusive we assume the filter is
    present so a quirky ffmpeg build never disables a working watermark.
    """
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        return False
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:  # pragma: no cover - defensive
        return True
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 or not output.strip():
        return True  # inconclusive → don't disable the watermark
    return "drawtext" in output


# ── Hook system ───────────────────────────────────────────────────────────

# Frozen set: typos in `cb(event=...)` raise KeyError instead of silently
# missing every subscription.
HOOK_EVENTS: frozenset[str] = frozenset(
    {
        "engine_start",
        "engine_end",
        "voice_start",
        "voice_end",
        "record_start",
        "record_end",
        "pipeline_start",
        "pipeline_end",
        "export_start",
        "export_end",
    }
)


def _discover_hooks(
    config_dict: dict[str, Any],
) -> dict[str, list[Callable[..., None]]]:
    """Auto-discover plugins registered under ``demodsl.hooks`` entry-points."""
    from importlib.metadata import entry_points

    hooks: dict[str, list[Callable[..., None]]] = {evt: [] for evt in HOOK_EVENTS}
    for ep in entry_points(group="demodsl.hooks"):
        try:
            cls = ep.load()
            instance = cls(config_dict=config_dict)
            for evt in HOOK_EVENTS:
                method = getattr(instance, f"on_{evt}", None)
                if callable(method):
                    hooks[evt].append(method)
            logger.info("Discovered hook plugin '%s' from %s", ep.name, ep.value)
        except Exception:
            logger.warning("Failed to load hook plugin '%s'", ep.name, exc_info=True)
    return hooks


def _dispatch(hooks: dict[str, list[Callable[..., None]]], event: str, **kwargs: Any) -> None:
    """Fire all callbacks registered for *event*.

    Hook callbacks may opt in to fail-fast behaviour by setting a truthy
    ``critical`` attribute on the callable (``cb.critical = True``); such
    exceptions propagate to the caller. Non-critical hook failures are
    logged at WARNING level and swallowed so a misbehaving plugin can't
    take down a demo run.
    """
    for cb in hooks.get(event, []):
        try:
            cb(**kwargs)
        except Exception:
            critical = bool(getattr(cb, "critical", False))
            logger.warning("Hook callback %s failed (critical=%s)", cb, critical, exc_info=True)
            if critical:
                raise


def _accepts_one_arg(func: Callable[..., Any]) -> bool:
    """Whether *func* can be called with a single positional argument."""
    import inspect

    try:
        inspect.signature(func).bind(None)
    except (TypeError, ValueError):
        return False
    return True


def _discover_effect_plugins(registry: Any, *, quiet: bool = False) -> None:
    """Auto-discover browser effects from plugins via entry-points.

    Plugins expose ``demodsl.effects.browser`` entry-points. Each entry-point
    may resolve to:

    * a ``BrowserEffect`` subclass → registered under the entry-point name;
    * an instance → registered under the entry-point name;
    * a callable ``register(registry)`` → called to register any number of
      effects using custom names.

    Plugins that expose an effect also opt-in its ``type`` literal and its
    accepted params by importing / mutating
    :mod:`demodsl.models.effects` (see ``register_plugin_effect_type``).
    """
    from importlib.metadata import entry_points

    from demodsl.effects.registry import BrowserEffect
    from demodsl.models.effects import register_plugin_effect_type

    for ep in entry_points(group="demodsl.effects.browser"):
        try:
            obj = ep.load()
            if callable(obj) and not isinstance(obj, type):
                # Assume a registration callable: obj(registry) -> None
                # or obj() -> dict[str, BrowserEffect]
                # Decide on the signature rather than on a TypeError, which
                # would also swallow one raised inside the plugin itself.
                result = obj(registry) if _accepts_one_arg(obj) else obj()
                if isinstance(result, dict):
                    for name, eff in result.items():
                        inst = eff() if isinstance(eff, type) else eff
                        registry.register_browser(name, inst)
                        register_plugin_effect_type(name)
            elif isinstance(obj, type) and issubclass(obj, BrowserEffect):
                registry.register_browser(ep.name, obj())
                register_plugin_effect_type(ep.name)
            elif isinstance(obj, BrowserEffect):
                registry.register_browser(ep.name, obj)
                register_plugin_effect_type(ep.name)
            else:
                logger.warning(
                    "Effect plugin '%s' from %s has unsupported type %s",
                    ep.name,
                    ep.value,
                    type(obj).__name__,
                )
                continue
            if not quiet:
                logger.info("Discovered browser effect plugin '%s' from %s", ep.name, ep.value)
        except Exception:
            logger.warning("Failed to load effect plugin '%s'", ep.name, exc_info=True)


def _pre_register_plugin_effect_types() -> None:
    """Pre-register plugin effect *type names* so Pydantic accepts them.

    Runs before ``DemoConfig(**raw)``. A plugin exposing one effect names it
    after its entry point, but a plugin exposing several only declares their
    real names from inside its ``register()`` callable — so that callable has
    to run here too, against a throwaway registry. Without it, an effect like
    ``app_vscode`` is rejected as an unknown type even though its plugin is
    installed: discovery proper happens after the config is already parsed.
    """
    from importlib.metadata import entry_points

    from demodsl.effects.registry import EffectRegistry
    from demodsl.models.effects import register_plugin_effect_type

    for ep in entry_points(group="demodsl.effects.browser"):
        # Always register the entry-point name as a valid type.
        register_plugin_effect_type(ep.name)

    _discover_effect_plugins(EffectRegistry(), quiet=True)


class DemoEngine:
    """Orchestrator: loads config, runs scenarios, executes the pipeline."""

    def __init__(
        self,
        config_path: Path,
        *,
        dry_run: bool = False,
        skip_voice: bool = False,
        skip_deploy: bool = False,
        tts_cache: bool = True,
        run_cache: bool = True,
        cache_dir: Path | None = None,
        force_record: bool = False,
        output_dir: Path | None = None,
        renderer: str = "remotion",
        separate_audio: bool = False,
        thumbnails: int = 0,
        turbo: bool = False,
        deterministic: bool = False,
        incremental: bool = False,
        only_steps: str | None = None,
        explain_cache: bool = False,
    ) -> None:
        self.config_path = config_path
        self.dry_run = dry_run
        self.skip_voice = skip_voice
        self.skip_deploy = skip_deploy
        self.tts_cache = tts_cache
        if renderer != "remotion":
            raise ValueError(
                f"Unsupported renderer {renderer!r}. Since v3.0, only 'remotion' "
                "is supported (MoviePy was removed)."
            )
        self.renderer = renderer
        self._force_record = force_record
        self._separate_audio = separate_audio
        self._thumbnails = thumbnails
        self.turbo = turbo
        self.deterministic = deterministic
        self.incremental = incremental
        self.explain_cache = explain_cache
        self._only_steps = parse_only_steps(only_steps)
        self._skipped_steps: list[dict[str, Any]] = []

        _pre_register_plugin_effect_types()
        raw = load_config_with_library(config_path)
        self.config = DemoConfig(**raw)

        # Theme tokens (issue #27) feed every overlay that would otherwise
        # hard-code a colour; explicit per-field values keep winning.
        themed = apply_theme(self.config)
        if themed:
            logger.info("Theme applied to %d overlay field(s)", len(themed))

        # Determinism contract (issue #26): pin every stochastic subsystem.
        self.determinism = apply_determinism(self.config, strict=deterministic)
        if self.determinism["seed"] is not None or self.determinism["strict"]:
            logger.info(
                "Determinism: seed=%s strict=%s (%d subsystem(s) pinned)",
                self.determinism["seed"],
                self.determinism["strict"],
                len(self.determinism["pinned"]),
            )

        self._output_dir = output_dir or Path(
            self.config.output.directory if self.config.output else "output"
        )

        # Run cache
        self._cache = RunCache(config_path, enabled=run_cache, cache_dir=cache_dir)

        # Effects
        self._effects = EffectRegistry()
        register_all_browser_effects(self._effects)
        register_all_post_effects(self._effects)
        _discover_effect_plugins(self._effects)

        # Sub-orchestrators
        # Resolve TTS language: use languages.default if separate-audio is active
        tts_language: str | None = None
        if self._separate_audio and self.config.languages:
            tts_language = self.config.languages.default
        self._narration = NarrationOrchestrator(
            self.config,
            skip_voice=skip_voice,
            tts_cache=tts_cache,
            language=tts_language,
        )
        self._scenario = ScenarioOrchestrator(self.config, self._effects, turbo=turbo)
        self._post = PostProcessingOrchestrator(self.config, self._effects, renderer=renderer)
        self._export = ExportOrchestrator(self.config)

        logger.info(
            "demodsl v%s — %s (%s)",
            __version__,
            self.config.metadata.title,
            config_path.name,
        )

        # Auto-discover hook plugins (no YAML needed)
        self._hooks = _discover_hooks(raw)

    # ── Public API ────────────────────────────────────────────────────────

    def validate(self) -> DemoConfig:
        """Parse + validate only (already done in __init__)."""
        logger.info("Validation OK: %s", self.config.metadata.title)
        return self.config

    def run(self) -> Path | None:
        """Execute the full demo pipeline."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        _run_start = time.monotonic()

        if self.turbo:
            logger.info(
                "TURBO mode: minimal waits, skipping avatars/3D/post-effects/"
                "subtitles/speed-reencode for fast preview"
            )

        # Compute per-section fingerprints for cache invalidation
        fps = RunCache.fingerprint_config_sections(self.config)

        # Collect pause config for narration track
        pauses: list[dict[str, object]] = []
        if self.config.edit and self.config.edit.pauses:
            pauses = [p.model_dump() for p in self.config.edit.pauses]

        with Workspace() as ws:
            _dispatch(self._hooks, "engine_start", config=self.config)

            # ── Pass 1: Voice ─────────────────────────────────────────────
            narration_map: dict[int, Path] = {}
            narration_durations: dict[int, float] = {}

            cached_voice = (
                not self.dry_run
                and self._cache.section_unchanged("voice", fps["voice"])
                and self._cache.section_unchanged("scenarios", fps["scenarios"])
            )
            cached_narration = self._cache.get_artifact("narration_map")

            if cached_voice and cached_narration:
                # Restore narration clips from cache
                restored_all = True
                for step_key, rel_path in cached_narration.items():
                    dest = ws.audio_clips / Path(rel_path).name
                    if self._cache.restore_file(rel_path, dest):
                        narration_map[int(step_key)] = dest
                    else:
                        restored_all = False
                        break

                if restored_all:
                    cached_durs = self._cache.get_artifact("narration_durations")
                    if cached_durs:
                        narration_durations = {int(k): v for k, v in cached_durs.items()}
                        logger.info(
                            "Restored %d narration clips from run cache",
                            len(narration_map),
                        )
                    else:
                        narration_durations = self._narration.measure_narration_durations(
                            narration_map
                        )
                else:
                    narration_map = {}

            if not narration_map:
                _dispatch(self._hooks, "voice_start")
                narration_map = self._narration.generate_narrations(ws, dry_run=self.dry_run)
                narration_map = self._narration.apply_breathing(narration_map, ws)
                narration_durations = self._narration.measure_narration_durations(narration_map)
                # Store narration clips in cache
                cached_map: dict[str, str] = {}
                for step_idx, clip_path in narration_map.items():
                    rel = f"audio_clips/{clip_path.name}"
                    self._cache.store_file(clip_path, rel)
                    cached_map[str(step_idx)] = rel
                self._cache.update_manifest(
                    {"voice": fps["voice"], "scenarios": fps["scenarios"]},
                    {
                        "narration_map": cached_map,
                        "narration_durations": {str(k): v for k, v in narration_durations.items()},
                    },
                )

            _dispatch(self._hooks, "voice_end", narration_map=narration_map)

            # Pass 1.5: Avatar
            narration_texts = self._narration.build_narration_texts()
            if self.turbo:
                avatar_clips: dict[int, Path] = {}
                logger.info("turbo: skipping avatar generation")
            else:
                avatar_clips = self._post.generate_avatar_clips(
                    ws,
                    narration_map,
                    narration_texts,
                    dry_run=self.dry_run,
                )

            # ── Pass 2: Scenarios — browser capture ───────────────────────
            raw_videos: list[Path] = []
            step_timestamps: list[float] = []
            step_post_effects: list[list[tuple[str, dict[str, Any]]]] = []
            scroll_positions: list[tuple[float, int]] = []

            scenarios_cached = (
                self._cache.section_unchanged("scenarios", fps["scenarios"])
                and not self._force_record
                and not self.dry_run
            )

            # Incremental mode (issue #25): decide per *step* instead of per
            # config section, so editing one narration line no longer throws
            # the whole recording away.
            segment_plan = None
            if (self.incremental or self.explain_cache) and not self.dry_run:
                segment_plan = plan_segments(
                    self.config,
                    cached_keys=self._cache.get_artifact("segment_keys") or {},
                    only_steps=self._only_steps,
                )
                if self.explain_cache:
                    logger.info("Segment cache plan:\n%s", segment_plan.explain())
                if self.incremental:
                    scenarios_cached = (
                        not segment_plan.dirty and not self._force_record and not self.dry_run
                    )

            cached_videos = self._cache.get_artifact("raw_videos")

            if scenarios_cached and cached_videos:
                # Try to restore raw videos from cache
                restored_all = True
                for rel_path in cached_videos:
                    dest = ws.raw_video / Path(rel_path).name
                    if self._cache.restore_file(rel_path, dest):
                        # Validate the restored video is not broken
                        if self._is_suspect_video(dest):
                            logger.warning(
                                "Cached video '%s' looks suspect (too small or "
                                "very short). Use --no-run-cache or --force-record "
                                "to re-record.",
                                dest.name,
                            )
                            restored_all = False
                            break
                        raw_videos.append(dest)
                    else:
                        restored_all = False
                        break

                if restored_all:
                    step_timestamps = self._cache.get_artifact("step_timestamps") or []
                    step_post_effects = self._cache.get_artifact("step_post_effects") or []
                    logger.info(
                        "Restored %d raw videos from run cache (skipped browser recording)",
                        len(raw_videos),
                    )
                else:
                    raw_videos = []

            if not raw_videos:
                _dispatch(self._hooks, "record_start")
                recording = self._scenario.run_scenarios(
                    ws,
                    narration_durations=narration_durations,
                    dry_run=self.dry_run,
                )
                raw_videos = recording.raw_videos
                step_timestamps = recording.step_timestamps
                step_post_effects = recording.step_post_effects
                scroll_positions = recording.scroll_positions
                self._skipped_steps = list(recording.skipped_steps)

                # Store in cache
                cached_vids: list[str] = []
                for vid in raw_videos:
                    if vid.exists():
                        rel = f"raw_video/{vid.name}"
                        self._cache.store_file(vid, rel)
                        cached_vids.append(rel)
                self._cache.update_manifest(
                    {"scenarios": fps["scenarios"]},
                    {
                        "raw_videos": cached_vids,
                        "step_timestamps": step_timestamps,
                        "step_post_effects": step_post_effects,
                        "segment_keys": {
                            str(e.index): e.key
                            for e in (
                                segment_plan or plan_segments(self.config, cached_keys={})
                            ).entries
                        },
                    },
                )

            _dispatch(self._hooks, "record_end", raw_videos=raw_videos)

            # Concatenate multi-scenario videos into one
            transition = self.config.video.transitions if self.config.video else None
            scenario_cuts: tuple[float, ...] = ()
            if len(raw_videos) > 1:
                joined = self._concat_videos(
                    raw_videos,
                    ws.root / "combined.mp4",
                    transition=transition,
                )
                if joined.shift > 0:
                    # Each transition overlaps two clips, so everything past a
                    # junction happens earlier than the recorder measured.
                    step_timestamps = [joined.remap(t) for t in step_timestamps]
                    scroll_positions = [(joined.remap(t), y) for t, y in scroll_positions]
                    scenario_cuts = tuple(joined.remap(b) for b in joined.boundaries)
                raw_videos = [joined.path]

            # Transitions between beats of a single clip (navigations / steps)
            if transition is not None and raw_videos and step_timestamps:
                cuts = self.transition_boundaries(
                    self.config,
                    step_timestamps,
                    exclude=scenario_cuts,
                    min_gap=2 * transition.duration,
                )
                if cuts:
                    beat = self._apply_step_transitions(
                        raw_videos[0], ws.root / "beats.mp4", cuts, transition
                    )
                    if beat.shift > 0:
                        step_timestamps = [beat.remap(t) for t in step_timestamps]
                        scroll_positions = [(beat.remap(t), y) for t, y in scroll_positions]
                    raw_videos = [beat.path]

            # ── Pass 2.75: Device rendering (Blender 3D) ─────────────────
            # Skip if render_device_3d is declared in the pipeline (handled there).
            _pipeline_has_3d = any(s.stage_type == "render_device_3d" for s in self.config.pipeline)
            if self.turbo:
                if self.config.device_rendering:
                    logger.info("turbo: skipping 3D device rendering")
            elif (
                self.config.device_rendering
                and raw_videos
                and raw_videos[0].exists()
                and not _pipeline_has_3d
            ):
                raw_videos = [
                    self._apply_device_rendering(
                        raw_videos[0],
                        self.config.device_rendering,
                        ws.root / "device_rendered.mp4",
                        scroll_positions=scroll_positions,
                    )
                ]

            # ── Pass 2.5: Build combined narration audio track ────────────
            narration_audio: Path | None = None
            if narration_map:
                narration_audio = self._narration.build_narration_track(
                    narration_map,
                    ws.root / "narration_combined.mp3",
                    step_timestamps,
                    pauses=pauses,
                )

            # ── Pass 2.6: Multi-language tracks (audio + subtitles) ───────
            # Triggered by config.languages.targets being non-empty.
            # Skipped under turbo / dry-run / separate-audio (which has its
            # own flow) to keep behaviour predictable.
            multilang_audio_tracks: list[tuple[str, Path]] = []
            multilang_subtitle_tracks: list[tuple[str, Path]] = []
            self._multilang_active = False
            if (
                self.config.languages
                and (
                    self.config.languages.targets
                    or self.config.languages.audio_only
                    or self.config.languages.subtitle_only
                )
                and not self.dry_run
                and not self.turbo
                and not self._separate_audio
            ):
                multilang_audio_tracks, multilang_subtitle_tracks = self._generate_multilang_tracks(
                    ws,
                    narration_audio=narration_audio,
                    step_timestamps=step_timestamps,
                    pauses=pauses,
                )
                self._multilang_active = bool(multilang_audio_tracks or multilang_subtitle_tracks)

            # ── Pass 3: Pipeline — chain of responsibility ────────────────
            ctx = PipelineContext(
                workspace_root=ws.root,
                raw_video=raw_videos[0] if raw_videos else None,
                narration_map=narration_map,
                config={
                    "background_music": (
                        self.config.audio.background_music.model_dump()
                        if self.config.audio and self.config.audio.background_music
                        else None
                    ),
                    "webinar": self.config.webinar,
                    "appless": self.config.appless,
                    "_timelines": [
                        (sc.name, sc.timeline, self.config_path.resolve().parent)
                        for sc in self.config.scenarios
                        if sc.timeline is not None
                    ],
                },
                scroll_positions=scroll_positions,
                device_rendering=self.config.device_rendering,
                theme=resolve_theme(self.config.theme),
                metadata={"config_dir": str(self.config_path.resolve().parent)},
                scenario_name=self.config.scenarios[0].name if self.config.scenarios else "",
            )

            pipeline_dicts = [
                {"stage_type": s.stage_type, "params": s.params} for s in self.config.pipeline
            ]
            chain = build_chain(pipeline_dicts)
            _dispatch(self._hooks, "pipeline_start", ctx=ctx)
            if chain:
                ctx = chain.handle(ctx)
            _dispatch(self._hooks, "pipeline_end", ctx=ctx)

            # ── Pass 3.5: Apply post-processing effects ───────────────────
            final = ctx.processed_video or ctx.raw_video

            # Insert freeze-frame pauses if requested
            freeze_pauses = [p for p in pauses if p.get("type") == "freeze"]
            if not self.turbo and final and final.exists() and freeze_pauses and step_timestamps:
                final = self._insert_freeze_pauses(final, step_timestamps, freeze_pauses, ws)

            # Bake per-step freeze_frame / speed_ramp / reverse into pixels —
            # Remotion's fixed-duration Sequences cannot change a step's local
            # duration or play direction, so these three are applied here via
            # ffmpeg and the resulting shift is folded into every downstream
            # timestamp before Remotion draws camera/vignette/subtitles on top.
            if (
                not self.turbo
                and final
                and final.exists()
                and step_post_effects
                and step_timestamps
            ):
                final, step_post_effects, effect_shifts = self._apply_step_time_effects(
                    final, step_timestamps, step_post_effects, ws
                )
                if effect_shifts:
                    remap = StepEffectResult(final, effect_shifts).remap
                    step_timestamps = [remap(t) for t in step_timestamps]
                    scroll_positions = [(remap(t), y) for t, y in scroll_positions]

            if not self.turbo and final and final.exists() and step_post_effects:
                final = self._post.remotion_full_compose(
                    final,
                    ws,
                    narration_durations,
                    step_timestamps,
                    step_post_effects,
                    avatar_clips=avatar_clips,
                    narration_texts=narration_texts,
                )

            # ── Pass 3.6: Apply global video speed ────────────────────
            global_speed = (
                self.config.video.speed if self.config.video and self.config.video.speed else None
            )
            if self.turbo:
                if global_speed and global_speed != 1.0:
                    logger.info("turbo: skipping global speed re-encode (%.1fx)", global_speed)
            elif final and final.exists() and global_speed is not None and global_speed != 1.0:
                final = self._apply_global_speed(final, global_speed, ws)

            # Copy final output
            if final and final.exists():
                # Avatars + subtitles + watermark are handled inside
                # remotion_full_compose; the only remaining concern at this
                # stage is the @demodsl branding watermark.

                # ── @demodsl branding watermark (opt-out) ────────────
                branding = True
                if self.config.output and self.config.output.branding is False:
                    branding = False
                if branding:
                    watermarked = ws.root / "watermarked.mp4"
                    final = self._burn_watermark(final, watermarked)

                if self._separate_audio:
                    # ── Separate-audio mode: 3 output files ───────────
                    self._output_dir.mkdir(parents=True, exist_ok=True)

                    # 1) video.mp4 — muted video (no narration)
                    video_dest = self._output_dir / "video.mp4"
                    _dispatch(self._hooks, "export_start", video=final, dest=video_dest)
                    self._export.export_video(final, video_dest, audio=None)
                    logger.info("Separate-audio: video → %s", video_dest)

                    # 2) narration.mp3 — narration audio track
                    narration_dest = self._output_dir / "narration.mp3"
                    if narration_audio and narration_audio.exists():
                        import shutil

                        shutil.copy2(narration_audio, narration_dest)
                        logger.info("Separate-audio: narration → %s", narration_dest)
                    else:
                        # Build from narration clips even if not previously assembled
                        if narration_map:
                            built = self._narration.build_narration_track(
                                narration_map,
                                narration_dest,
                                step_timestamps,
                                pauses=pauses,
                            )
                            if built:
                                logger.info(
                                    "Separate-audio: narration → %s",
                                    narration_dest,
                                )
                            else:
                                logger.warning("Separate-audio: no narration audio produced")
                        else:
                            logger.warning("Separate-audio: no narration clips available")

                    # 3) timing.json — narration timestamps
                    timing_dest = self._output_dir / "timing.json"
                    timing_data = self._build_timing_json(
                        step_timestamps,
                        narration_durations,
                        narration_map,
                    )
                    timing_dest.write_text(
                        json.dumps(timing_data, indent=2, ensure_ascii=False) + "\n"
                    )
                    logger.info("Separate-audio: timing → %s", timing_dest)

                    _dispatch(self._hooks, "export_end", output=video_dest)

                    # Save final pipeline fingerprints
                    self._cache.update_manifest(
                        fps,
                        {
                            "final_output": str(video_dest),
                            "separate_audio": True,
                        },
                    )

                    dest = video_dest
                else:
                    # ── Normal mode: single MP4 with audio ────────────
                    out_name = self.config.output.filename if self.config.output else "output.mp4"
                    if not Path(out_name).suffix:
                        out_name += ".mp4"
                    dest = self._output_dir / out_name
                    _dispatch(self._hooks, "export_start", video=final, dest=dest)
                    if self._multilang_active and (
                        self.config.languages and self.config.languages.embed
                    ):
                        # Mux multiple audio + subtitle tracks into the MP4.
                        self._export.export_multilang_video(
                            final,
                            dest,
                            audio_tracks=multilang_audio_tracks,
                            subtitle_tracks=multilang_subtitle_tracks,
                        )
                    else:
                        self._export.export_video(final, dest, audio=narration_audio)
                        # Sidecar files when languages.embed is False
                        if (
                            self._multilang_active
                            and self.config.languages
                            and not self.config.languages.embed
                        ):
                            import shutil as _sh

                            for lang, audio_path in multilang_audio_tracks:
                                _sh.copy2(
                                    audio_path,
                                    self._output_dir / f"narration_{lang}{audio_path.suffix}",
                                )
                            for lang, sub_path in multilang_subtitle_tracks:
                                _sh.copy2(
                                    sub_path,
                                    self._output_dir / f"subtitles_{lang}{sub_path.suffix}",
                                )
                            logger.info(
                                "Wrote multilang sidecar files for %d audio "
                                "and %d subtitle track(s) → %s",
                                len(multilang_audio_tracks),
                                len(multilang_subtitle_tracks),
                                self._output_dir,
                            )
                    logger.info("Final output: %s", dest)
                    _dispatch(self._hooks, "export_end", output=dest)

                    # ── Social exports (TikTok shorts …) declared in
                    # output.social — derived automatically from the final MP4.
                    self._run_social_exports(dest, narration_audio, step_timestamps)

                    # Save final pipeline fingerprints
                    self._cache.update_manifest(
                        fps,
                        {"final_output": str(dest)},
                    )

                if not self.skip_deploy:
                    deploy_url = self._export.deploy_to_cloud(dest)
                    if deploy_url:
                        logger.info("Deployed to: %s", deploy_url)

                # ── Thumbnail generation (opt-in via --thumbnails N) ──
                if self._thumbnails > 0:
                    thumb_paths = self._generate_thumbnails(
                        dest, self._output_dir, self._thumbnails
                    )
                    if thumb_paths:
                        logger.info(
                            "Generated %d thumbnail(s): %s",
                            len(thumb_paths),
                            ", ".join(p.name for p in thumb_paths),
                        )

                try:
                    StatsStore().record_run(
                        project_title=self.config.metadata.title,
                        config_path=self.config_path,
                        renderer=self.renderer,
                        output=dest,
                        dry_run=self.dry_run,
                        duration_minutes=(time.monotonic() - _run_start) / 60,
                    )
                except Exception:
                    logger.warning("Failed to record usage stats", exc_info=True)

                try:
                    manifest_path = self.write_run_manifest(
                        self._output_dir / "run.json",
                        step_timestamps=step_timestamps,
                        narration_durations=narration_durations,
                        output=dest,
                    )
                    logger.info("Run manifest → %s (feed it to `demodsl qa`)", manifest_path)
                except Exception:
                    logger.warning("Failed to write the run manifest", exc_info=True)

                _dispatch(self._hooks, "engine_end", output=dest)
                return dest

            try:
                StatsStore().record_run(
                    project_title=self.config.metadata.title,
                    config_path=self.config_path,
                    renderer=self.renderer,
                    output=None,
                    dry_run=self.dry_run,
                    duration_minutes=(time.monotonic() - _run_start) / 60,
                )
            except Exception:
                logger.warning("Failed to record usage stats", exc_info=True)

            _dispatch(self._hooks, "engine_end", output=None)
            logger.info("Pipeline completed (no output video produced in dry-run)")
            return None

    # ── Helpers ───────────────────────────────────────────────────────────

    def build_run_manifest(
        self,
        *,
        step_timestamps: list[float],
        narration_durations: dict[int, float] | None = None,
        output: Path | None = None,
    ) -> dict[str, Any]:
        """Assemble the run manifest consumed by ``demodsl qa`` (issue #24).

        Carries per-step timings, the overlay rectangles resolved during
        recording (effects anchored on a locator write their normalised
        target back onto the config) and the steps that were degraded by
        their ``on_error`` policy.
        """
        narration_durations = narration_durations or {}
        skipped = list(getattr(self, "_skipped_steps", []) or [])
        skipped_by_index = {entry.get("index"): entry for entry in skipped}

        frame_w, frame_h = 1920, 1080
        if self.config.scenarios:
            frame_w = self.config.scenarios[0].viewport.width
            frame_h = self.config.scenarios[0].viewport.height

        steps: list[dict[str, Any]] = []
        overlays: list[dict[str, Any]] = []
        index = 0
        total = step_timestamps[-1] if step_timestamps else 0.0
        theme = self.config.theme

        for scenario in self.config.scenarios:
            for step in scenario.steps:
                t = step_timestamps[index] if index < len(step_timestamps) else 0.0
                next_t = (
                    step_timestamps[index + 1]
                    if index + 1 < len(step_timestamps)
                    else max(total, t)
                )
                narration = float(narration_durations.get(index, 0.0) or 0.0)
                locator = step.locator
                steps.append(
                    {
                        "index": index,
                        "action": step.action,
                        "t": round(t, 3),
                        "duration": round(max(0.0, next_t - t), 3),
                        "narration_duration": round(narration, 3),
                        "locator": f"[{locator.type}] {locator.value}" if locator else None,
                        "motion": step.action not in ("pause", "wait_for")
                        and index not in skipped_by_index,
                    }
                )
                for effect in step.effects or []:
                    rect = self._effect_rect(effect, frame_w, frame_h)
                    if rect is None:
                        continue
                    overlays.append(
                        {
                            "kind": effect.type,
                            "step": index,
                            "t": round(t, 3),
                            "duration": float(getattr(effect, "duration", None) or 1.5),
                            "rect": rect,
                            "color": getattr(effect, "color", None)
                            or (theme.accent if theme else None),
                            "background": theme.surface if theme else None,
                        }
                    )
                index += 1

        enriched_skipped: list[dict[str, Any]] = []
        for entry in skipped:
            idx = entry.get("index")
            if isinstance(idx, int) and idx < len(step_timestamps):
                entry = {**entry, "t": round(step_timestamps[idx], 3)}
            enriched_skipped.append(entry)

        return {
            "config": str(self.config_path),
            "output": str(output) if output else None,
            "engine_version": __version__,
            "duration": round(total, 3),
            "frame": {"width": frame_w, "height": frame_h},
            "seed": self.config.seed,
            "deterministic": bool(getattr(self, "determinism", {}).get("strict")),
            "steps": steps,
            "overlays": overlays,
            "skipped_steps": enriched_skipped,
        }

    def write_run_manifest(
        self,
        path: Path,
        *,
        step_timestamps: list[float],
        narration_durations: dict[int, float] | None = None,
        output: Path | None = None,
    ) -> Path:
        """Write the run manifest to *path* and return it."""
        manifest = self.build_run_manifest(
            step_timestamps=step_timestamps,
            narration_durations=narration_durations,
            output=output,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def _effect_rect(effect: Any, frame_w: int, frame_h: int) -> dict[str, float] | None:
        """Approximate the on-screen rectangle of an anchored overlay effect."""
        tx = getattr(effect, "target_x", None)
        ty = getattr(effect, "target_y", None)
        if tx is None or ty is None:
            return None
        radius = float(getattr(effect, "radius", None) or 90.0)
        ratio = float(getattr(effect, "ratio", None) or 1.0) or 1.0
        half_w = radius
        half_h = radius / ratio
        return {
            "x": round(tx * frame_w - half_w, 2),
            "y": round(ty * frame_h - half_h, 2),
            "w": round(half_w * 2, 2),
            "h": round(half_h * 2, 2),
        }

    def _run_social_exports(
        self,
        dest: Path,
        narration_audio: Path | None,
        step_timestamps: list[float] | None = None,
    ) -> list[Path]:
        """Derive the ``output.social`` exports from the final MP4.

        Declaring ``output.social`` used to validate and then silently produce
        nothing because the engine never called ``export_social``. A failure
        here must never fail the main render, so everything is swallowed.
        """
        if not (self.config.output and self.config.output.social):
            return []
        try:
            # Prefer the native 1080x1920 Remotion composition (overlays
            # re-laid-out for vertical) over cropping the 16:9 final; mux the
            # narration onto it first.
            vertical_src: Path | None = None
            vert_comp = getattr(self._post, "vertical_composition", None)
            if vert_comp and Path(vert_comp).exists():
                vertical_src = self._output_dir / "_vertical_tmp.mp4"
                self._export.export_video(Path(vert_comp), vertical_src, audio=narration_audio)
            outputs = list(
                self._export.export_social(
                    dest,
                    self._output_dir,
                    vertical_source=vertical_src,
                    step_timestamps=step_timestamps,
                )
            )
            for social_out in outputs:
                logger.info("Social export: %s", social_out)
            if vertical_src and vertical_src.exists():
                vertical_src.unlink()
            return outputs
        except Exception as exc:  # never fail the main render
            logger.warning("Social export failed: %s", exc)
            return []

    def _generate_multilang_tracks(
        self,
        ws: Workspace,
        *,
        narration_audio: Path | None,
        step_timestamps: list[float],
        pauses: list[dict[str, Any]],
    ) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
        """Build per-language audio + subtitle tracks for the final mux.

        The default-language audio track reuses ``narration_audio`` when
        available. Target languages run their own TTS pass and assemble a
        dedicated narration track. ASS subtitle files are produced for
        every language that resolves to non-empty text.
        """
        languages = self.config.languages
        assert languages is not None  # caller checks

        default_lang = languages.default
        audio_tracks: list[tuple[str, Path]] = []
        subtitle_tracks: list[tuple[str, Path]] = []

        # Ordered, deduplicated list of languages to materialise.
        ordered: list[str] = [default_lang]
        for code in (
            *languages.targets,
            *languages.audio_only,
            *languages.subtitle_only,
        ):
            if code and code not in ordered:
                ordered.append(code)

        # Cache per-language clip maps so we can derive accurate subtitle
        # durations from the freshly-generated audio clips.
        per_lang_clip_map: dict[str, dict[int, Path]] = {}

        for lang in ordered:
            audio_only_lang = lang in languages.audio_only
            subtitle_only_lang = lang in languages.subtitle_only

            # ── Audio track ──
            if not subtitle_only_lang:
                if lang == default_lang and narration_audio and narration_audio.exists():
                    audio_tracks.append((lang, narration_audio))
                else:
                    lang_map = self._narration.generate_narrations_for_lang(
                        ws, lang, default_lang, dry_run=self.dry_run
                    )
                    per_lang_clip_map[lang] = lang_map
                    if lang_map:
                        track_path = ws.root / f"narration_{lang}.mp3"
                        built = self._narration.build_narration_track(
                            lang_map,
                            track_path,
                            step_timestamps,
                            pauses=pauses,
                        )
                        if built and built.exists():
                            audio_tracks.append((lang, built))

            # ── Subtitle track ──
            if not audio_only_lang:
                texts = self._narration.build_narration_texts_for_lang(lang, default_lang)
                if not texts:
                    continue
                clip_map = per_lang_clip_map.get(lang)
                if clip_map is None and lang == default_lang:
                    # Reuse the default narration map already measured by
                    # the main pipeline (durations are stable).
                    clip_map = {}
                durations = (
                    self._narration.measure_narration_durations(clip_map) if clip_map else {}
                )
                ass_path = self._post.generate_subtitle_file(
                    ws, texts, durations, step_timestamps, lang
                )
                if ass_path is not None:
                    subtitle_tracks.append((lang, ass_path))

        if audio_tracks or subtitle_tracks:
            logger.info(
                "Multilang ready: %d audio track(s) [%s], %d subtitle track(s) [%s]",
                len(audio_tracks),
                ", ".join(c for c, _ in audio_tracks),
                len(subtitle_tracks),
                ", ".join(c for c, _ in subtitle_tracks),
            )
        return audio_tracks, subtitle_tracks

    def _build_timing_json(
        self,
        step_timestamps: list[float],
        narration_durations: dict[int, float],
        narration_map: dict[int, Path],
    ) -> list[dict[str, Any]]:
        """Build the timing.json data for --separate-audio mode.

        Returns a list of dicts with step, text, start, and end for each
        narrated step, ordered by appearance in the YAML.
        """
        narration_texts = self._narration.build_narration_texts()
        timing: list[dict[str, Any]] = []

        for step_idx in sorted(narration_map.keys()):
            text = narration_texts.get(step_idx)
            if text is None:
                continue

            start = step_timestamps[step_idx] if step_idx < len(step_timestamps) else 0.0
            duration = narration_durations.get(step_idx, 0.0)
            end = round(start + duration, 1)
            start = round(start, 1)

            timing.append(
                {
                    "step": step_idx,
                    "text": text,
                    "start": start,
                    "end": end,
                }
            )

        return timing

    @staticmethod
    def _generate_thumbnails(
        video: Path,
        output_dir: Path,
        count: int,
    ) -> list[Path]:
        """Extract *count* candidate thumbnail images from evenly-spaced timestamps.

        Returns a list of paths to the generated PNG files.
        Falls back gracefully if ffmpeg/ffprobe are not available.
        """
        import shutil
        import subprocess

        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            logger.warning("ffmpeg/ffprobe not found — skipping thumbnail generation.")
            return []

        # Probe video duration
        try:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(video),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            duration = float(probe.stdout.strip())
        except (subprocess.SubprocessError, ValueError):
            logger.warning("Could not probe video duration for thumbnails")
            return []

        if duration <= 0:
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []

        for i in range(count):
            # Distribute timestamps evenly, avoiding the very first and last frames
            ts = duration * (i + 1) / (count + 1)
            out = output_dir / f"thumbnail_{i:02d}.png"
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                f"{ts:.2f}",
                "-i",
                str(video),
                "-vframes",
                "1",
                "-q:v",
                "2",
                str(out),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and out.exists():
                paths.append(out)
                logger.info("Thumbnail %d/%d at %.1fs → %s", i + 1, count, ts, out.name)
            else:
                logger.warning(
                    "Thumbnail extraction failed at %.1fs: %s",
                    ts,
                    result.stderr[-200:] if result.stderr else "unknown",
                )

        return paths

    @staticmethod
    def _apply_global_speed(video: Path, speed: float, ws: Any) -> Path:
        """Apply a global speed multiplier to the entire video using ffmpeg.

        Uses ffmpeg's ``setpts`` filter (video) — matches previous behavior
        which dropped audio (``audio=False``). Renderer-agnostic, no MoviePy
        dependency.
        """
        import shutil
        import subprocess

        if not shutil.which("ffmpeg"):
            logger.warning("ffmpeg not found in PATH — skipping global speed adjustment")
            return video

        logger.info("Applying global video speed: %.2fx", speed)
        output = ws.root / "global_speed_applied.mp4"
        # setpts=PTS/speed → speed=2 makes the clip twice as fast.
        pts_factor = 1.0 / speed
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-an",  # drop audio (matches previous MoviePy audio=False)
            "-vf",
            f"setpts={pts_factor:.6f}*PTS",
            *x264_args(pix_fmt=None),
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(
                "ffmpeg global speed adjustment failed (%s) — keeping original",
                (result.stderr or "")[-300:],
            )
            return video
        logger.info("Global speed applied: %.2fx", speed)
        return output

    @staticmethod
    def _burn_watermark(video: Path, output: Path) -> Path:
        """Burn a mandatory '@demodsl' text watermark onto the video."""
        import shutil
        import subprocess

        if not shutil.which("ffmpeg"):
            logger.warning(
                "ffmpeg not found in PATH — skipping watermark burn. "
                "Install ffmpeg to enable the @demodsl branding watermark."
            )
            return video

        if not _ffmpeg_has_drawtext():
            logger.warning(
                "Watermark skipped: this ffmpeg build has no 'drawtext' filter. "
                "Install an ffmpeg built with libfreetype to enable the "
                "@demodsl branding watermark."
            )
            return video

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            ("drawtext=text='@demodsl':fontsize=24:fontcolor=white@0.5:x=w-tw-16:y=h-th-12"),
            *x264_args(pix_fmt=None),
            "-c:a",
            "copy",
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.warning("Watermark burn failed: %s", result.stderr[-400:])
            return video
        return output

    @staticmethod
    def _apply_device_rendering(
        video: Path,
        config: DeviceRendering,  # noqa: F821
        output: Path,
        *,
        scroll_positions: list[tuple[float, int]] | None = None,
    ) -> Path:
        """Render *video* inside a 3D device mockup via Blender.

        Falls back gracefully to the original video if Blender is not
        available or the render fails.  The provider is discovered
        automatically from installed plugins (``demodsl-blender``).
        """
        try:
            from demodsl.providers.base import BlenderProviderFactory

            blender = BlenderProviderFactory.create("headless")
            if not blender.check_available():
                logger.warning(
                    "Blender not available — skipping 3D device rendering. "
                    "The pipeline continues with the raw recording."
                )
                return video
            return blender.render(video, config, output, scroll_positions=scroll_positions)
        except Exception:
            logger.warning(
                "Blender 3D device rendering failed — continuing with raw video.",
                exc_info=True,
            )
            return video

    @staticmethod
    def _insert_freeze_pauses(
        video: Path,
        step_timestamps: list[float],
        freeze_pauses: list[dict[str, Any]],
        ws: Workspace,
    ) -> Path:
        """Insert freeze-frame pauses into the video at specified step boundaries."""
        import subprocess

        # Sort pauses by step index descending so offsets stay valid
        sorted_pauses = sorted(
            freeze_pauses,
            key=lambda p: int(p["after_step"]),
            reverse=True,
        )

        current = video
        for pause in sorted_pauses:
            step_idx = int(pause["after_step"])
            duration = float(pause["duration"])

            # Compute the split timestamp (end of step = start of next step)
            if step_idx + 1 < len(step_timestamps):
                split_t = step_timestamps[step_idx + 1]
            elif step_idx < len(step_timestamps):
                # Last step: freeze at end
                split_t = step_timestamps[step_idx] + 2.0
            else:
                continue

            out = ws.root / f"freeze_pause_{step_idx}.mp4"
            # ffmpeg: extract last frame at split_t, loop for duration, then concat
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(current),
                "-filter_complex",
                (
                    f"[0:v]split=2[before][after];"
                    f"[before]trim=0:{split_t},setpts=PTS-STARTPTS[v1];"
                    f"[after]trim={split_t},setpts=PTS-STARTPTS[v2];"
                    f"[0:v]trim={split_t}:{split_t + 0.04},setpts=PTS-STARTPTS,"
                    f"loop=loop={int(duration * 25)}:size=1:start=0,setpts=PTS-STARTPTS[freeze];"
                    f"[v1][freeze][v2]concat=n=3:v=1:a=0[outv]"
                ),
                "-map",
                "[outv]",
                *x264_args(),
                "-an",
                str(out),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode == 0 and out.exists():
                logger.info(
                    "Inserted %.1fs freeze pause after step %d at %.1fs",
                    duration,
                    step_idx,
                    split_t,
                )
                current = out
            else:
                logger.warning(
                    "Freeze pause insertion failed for step %d: %s",
                    step_idx,
                    result.stderr[-200:] if result.stderr else "unknown error",
                )

        return current

    @staticmethod
    def _apply_step_time_effects(
        video: Path,
        step_timestamps: list[float],
        step_post_effects: list[list[tuple[str, dict[str, Any]]]],
        ws: Workspace,
    ) -> tuple[Path, list[list[tuple[str, dict[str, Any]]]], tuple[tuple[float, float], ...]]:
        """Bake per-step ``freeze_frame``/``speed_ramp``/``reverse`` into pixels.

        These three change the LOCAL duration of a step (freeze, speed_ramp)
        or its play direction (reverse) — Remotion's ``Sequence`` durations
        are fixed by the manifest, so its ``EffectLayer`` cannot do any of
        this. Returns the new video, ``step_post_effects`` with those three
        names stripped out (already baked in, nothing left for Remotion to
        do), and the ``(original_boundary, delta_seconds)`` shifts the
        caller must fold into every downstream timestamp.
        """
        handled = {"freeze_frame", "speed_ramp", "reverse"}
        tasks: list[tuple[int, str, dict[str, Any]]] = []
        filtered: list[list[tuple[str, dict[str, Any]]]] = []
        for i, effects in enumerate(step_post_effects):
            kept: list[tuple[str, dict[str, Any]]] = []
            for name, params in effects:
                if name in handled:
                    tasks.append((i, name, params))
                else:
                    kept.append((name, params))
            filtered.append(kept)

        if not tasks or not step_timestamps:
            return video, step_post_effects, ()

        duration, _fps = DemoEngine._probe_stream(video)
        if duration <= 0:
            logger.warning(
                "Could not probe video duration — skipping freeze_frame/"
                "speed_ramp/reverse for %d step(s)",
                len(tasks),
            )
            return video, filtered, ()

        # Highest step index first: every earlier boundary stays a valid
        # position in each intermediate video, since a step's effect only
        # ever touches content at or after its own start.
        tasks.sort(key=lambda item: item[0], reverse=True)

        # step_timestamps run on the recorder's clock, which drifts from the
        # video's own by up to ~0.5s (see _apply_step_transitions) — snap
        # onto the nearest real cut so a boundary never lands mid-transition
        # (reversing/freezing/ramping half of the OLD page with half of the
        # NEW one instead of a clean split).
        cuts = DemoEngine._scene_cuts(video)

        current = video
        current_duration = duration
        shifts: list[tuple[float, float]] = []
        for idx, name, params in tasks:
            raw_start = step_timestamps[idx]
            raw_end = min(
                step_timestamps[idx + 1] if idx + 1 < len(step_timestamps) else current_duration,
                current_duration,
            )
            start = (
                DemoEngine._snap_to_cuts([raw_start], cuts, window=1.5)[0]
                if raw_start > 0.05
                else raw_start
            )
            end = (
                DemoEngine._snap_to_cuts([raw_end], cuts, window=1.5)[0]
                if raw_end < current_duration - 0.05
                else raw_end
            )
            if end <= start:
                continue
            has_after = end < current_duration - 0.02

            if name == "reverse":
                spliced = DemoEngine._splice_time_effect(
                    current,
                    start,
                    end,
                    has_after,
                    "[mid]reverse[midout]",
                    ws,
                    f"step_reverse_{idx}.mp4",
                )
                if spliced is not None:
                    current = spliced
                    logger.info("Reversed step %d (%.2fs-%.2fs)", idx, start, end)

            elif name == "freeze_frame":
                hold = float(params.get("freeze_duration") or 0.0)
                if hold <= 0:
                    continue
                spliced = DemoEngine._insert_step_freeze(current, end, hold, ws, idx)
                if spliced is not None:
                    current = spliced
                    shifts.append((end, hold))
                    current_duration += hold
                    logger.info("Froze step %d for %.1fs at %.2fs", idx, hold, end)

            elif name == "speed_ramp":
                start_speed = float(params.get("start_speed", 1.0)) or 1.0
                end_speed = float(params.get("end_speed", 1.0)) or 1.0
                ease = params.get("ease", "ease-in-out")
                mid_filter, new_len = DemoEngine._speed_ramp_filter(
                    end - start, start_speed, end_speed, ease
                )
                spliced = DemoEngine._splice_time_effect(
                    current,
                    start,
                    end,
                    has_after,
                    mid_filter,
                    ws,
                    f"step_speed_ramp_{idx}.mp4",
                )
                if spliced is not None:
                    current = spliced
                    delta = new_len - (end - start)
                    if abs(delta) > 1e-3:
                        shifts.append((end, delta))
                    current_duration += delta
                    logger.info(
                        "Speed-ramped step %d (%.2fx->%.2fx) %.2fs->%.2fs",
                        idx,
                        start_speed,
                        end_speed,
                        end - start,
                        new_len,
                    )

        return current, filtered, tuple(shifts)

    @staticmethod
    def _splice_time_effect(
        video: Path,
        start: float,
        end: float,
        has_after: bool,
        mid_filter: str,
        ws: Workspace,
        out_name: str,
    ) -> Path | None:
        """Cut ``[start, end)`` out of *video*, transform it via *mid_filter*.

        *mid_filter* is an ffmpeg filter-graph fragment that reads ``[mid]``
        and must write ``[midout]``; the untouched before/after slices (if
        any) are concatenated back around the transformed middle. Returns
        ``None`` on ffmpeg failure so the caller can keep the untouched video.
        """
        import subprocess

        has_before = start > 0.02
        n = 1 + int(has_before) + int(has_after)
        split_labels = [f"s{i}" for i in range(n)]
        parts = ["[0:v]split=" + str(n) + "".join(f"[{lbl}]" for lbl in split_labels)]

        order: list[str] = []
        i = 0
        if has_before:
            parts.append(f"[{split_labels[i]}]trim=0:{start:.4f},setpts=PTS-STARTPTS[v{i}]")
            order.append(f"v{i}")
            i += 1
        parts.append(f"[{split_labels[i]}]trim={start:.4f}:{end:.4f},setpts=PTS-STARTPTS[mid]")
        parts.append(mid_filter)
        order.append("midout")
        i += 1
        if has_after:
            parts.append(f"[{split_labels[i]}]trim={end:.4f},setpts=PTS-STARTPTS[v{i}]")
            order.append(f"v{i}")

        parts.append("".join(f"[{lbl}]" for lbl in order) + f"concat=n={len(order)}:v=1:a=0[outv]")

        out = ws.root / out_name
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-filter_complex",
            ";".join(parts),
            "-map",
            "[outv]",
            *x264_args(pix_fmt=None),
            str(out),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0 or not out.exists():
            logger.warning(
                "Step time-effect splice failed: %s",
                (result.stderr or "")[-300:],
            )
            return None
        return out

    @staticmethod
    def _speed_ramp_filter(
        seg_dur: float,
        start_speed: float,
        end_speed: float,
        ease: str,
    ) -> tuple[str, float]:
        """Build a filter-graph fragment ramping ``[mid]`` -> ``[midout]``.

        Approximates a continuous speed ramp with 8 constant-speed slices,
        each sampling the eased speed at its own midpoint — smooth enough to
        read as a ramp without needing a per-sample ffmpeg expression.
        Returns ``(filter_fragment, new_segment_duration)``.
        """
        from demodsl.effects.timeline.easing import _ease

        n = 8
        slice_dur = seg_dur / n
        parts = ["[mid]split=" + str(n) + "".join(f"[m{i}]" for i in range(n))]
        labels: list[str] = []
        new_len = 0.0
        for i in range(n):
            s0 = i * slice_dur
            s1 = seg_dur if i == n - 1 else (i + 1) * slice_dur
            mid_t = (i + 0.5) / n
            speed = max(0.05, start_speed + (end_speed - start_speed) * _ease(mid_t, ease))
            pts_factor = 1.0 / speed
            parts.append(
                f"[m{i}]trim=start={s0:.4f}:end={s1:.4f},"
                f"setpts=(PTS-STARTPTS)*{pts_factor:.6f}[r{i}]"
            )
            labels.append(f"r{i}")
            new_len += (s1 - s0) * pts_factor
        parts.append(
            "".join(f"[{lbl}]" for lbl in labels)
            + f"concat=n={n}:v=1:a=0,setpts=PTS-STARTPTS[midout]"
        )
        return ";".join(parts), new_len

    @staticmethod
    def _insert_step_freeze(
        video: Path,
        at: float,
        hold: float,
        ws: Workspace,
        tag: int,
    ) -> Path | None:
        """Freeze the frame at time *at* for *hold* seconds, splicing it in."""
        import subprocess

        out = ws.root / f"step_freeze_{tag}.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-filter_complex",
            (
                f"[0:v]split=2[before][after];"
                f"[before]trim=0:{at:.4f},setpts=PTS-STARTPTS[v1];"
                f"[after]trim={at:.4f},setpts=PTS-STARTPTS[v2];"
                f"[0:v]trim={at:.4f}:{at + 0.04:.4f},setpts=PTS-STARTPTS,"
                f"loop=loop={int(hold * 25)}:size=1:start=0,setpts=PTS-STARTPTS[freeze];"
                f"[v1][freeze][v2]concat=n=3:v=1:a=0[outv]"
            ),
            "-map",
            "[outv]",
            *x264_args(),
            "-an",
            str(out),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0 or not out.exists():
            logger.warning(
                "Step freeze-frame insertion failed: %s",
                (result.stderr or "")[-300:],
            )
            return None
        return out

    @staticmethod
    def _is_suspect_video(path: Path) -> bool:
        """Return ``True`` if the video file looks broken (too small or bad codec)."""
        if not path.exists():
            return True
        size = path.stat().st_size
        # Less than 10 KB is almost certainly a broken file
        if size < 10_240:
            return True
        # Try a quick ffprobe check for duration if available
        try:
            import subprocess

            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=duration,codec_name",
                    "-of",
                    "json",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                import json

                info = json.loads(result.stdout)
                streams = info.get("streams", [])
                if streams:
                    stream = streams[0]
                    raw_dur = stream.get("duration")
                    duration = float(raw_dur) if raw_dur and raw_dur != "N/A" else 0.0
                    codec = stream.get("codec_name", "")
                    if duration < 1.0:
                        logger.warning("Cached video duration=%.1fs — likely broken", duration)
                        return True
                    if codec == "mjpeg":
                        logger.warning(
                            "Cached video uses MJPEG codec — likely a static "
                            "slideshow, not a real recording"
                        )
                        return True
        except Exception:
            pass  # ffprobe not available — rely on file-size check only
        return False

    @staticmethod
    def _probe_stream(video: Path) -> tuple[float, float]:
        """Return ``(duration, fps)`` for *video*; zeros when unprobeable."""
        import subprocess

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=avg_frame_rate:format=duration",
                    "-of",
                    "json",
                    str(video),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return (0.0, 0.0)
            info = json.loads(result.stdout)
            duration = float(info.get("format", {}).get("duration") or 0.0)
            streams = info.get("streams") or [{}]
            num, _, den = (streams[0].get("avg_frame_rate") or "0/0").partition("/")
            fps = float(num) / float(den) if float(den or 0) else 0.0
            return (duration, fps)
        except (subprocess.SubprocessError, ValueError, json.JSONDecodeError, OSError):
            return (0.0, 0.0)

    @staticmethod
    def _concat_videos(
        videos: list[Path],
        output: Path,
        transition: Transitions | None = None,
    ) -> ConcatResult:
        """Join per-scenario videos, optionally cross-fading each junction.

        Without *transition* the clips are butt-joined and the timeline is
        untouched. With one, every junction overlaps by ``transition.duration``
        seconds, so the result is shorter — the caller must push step
        timestamps through :meth:`ConcatResult.remap`.
        """
        import subprocess

        existing = [v for v in videos if v.exists()]
        if not existing:
            return ConcatResult(videos[0])
        if len(existing) == 1:
            return ConcatResult(existing[0])

        n = len(existing)
        inputs: list[str] = []
        for v in existing:
            inputs.extend(["-i", str(v)])

        overlap = 0.0
        durations: list[float] = []
        fps = 0.0
        boundaries: tuple[float, ...] = ()
        if transition is not None and transition.duration > 0:
            probed = [DemoEngine._probe_stream(v) for v in existing]
            durations = [d for d, _ in probed]
            fps = next((f for _, f in probed if f > 0), 0.0)
            if min(durations) <= 0:
                logger.warning(
                    "Could not probe every scenario clip — joining without a %s transition",
                    transition.type,
                )
            else:
                # A junction eats a slice of both neighbours: cap it at half
                # the shortest clip or ffmpeg's xfade offsets go negative.
                overlap = min(transition.duration, min(durations) / 2)
                if overlap < 0.05:
                    logger.warning(
                        "Scenario clips are too short (%.1fs) for a %.2fs %s — "
                        "joining without a transition",
                        min(durations),
                        transition.duration,
                        transition.type,
                    )
                    overlap = 0.0
                else:
                    if overlap < transition.duration:
                        logger.warning(
                            "Clamped the %s transition from %.2fs to %.2fs "
                            "(shortest scenario clip is %.1fs)",
                            transition.type,
                            transition.duration,
                            overlap,
                            min(durations),
                        )
                    acc = 0.0
                    bounds: list[float] = []
                    for d in durations[:-1]:
                        acc += d
                        bounds.append(acc)
                    boundaries = tuple(bounds)

        if overlap > 0:
            filter_str = DemoEngine._xfade_filter(n, durations, overlap, transition.xfade_name, fps)
        else:
            boundaries = ()
            filter_str = "".join(f"[{i}:v:0]" for i in range(n)) + f"concat=n={n}:v=1:a=0[outv]"

        cmd = [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            filter_str,
            "-map",
            "[outv]",
            *x264_args(pix_fmt=None),
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            logger.error("Video concatenation failed: %s", result.stderr[-300:])
            return ConcatResult(existing[0])
        if overlap > 0:
            logger.info(
                "Concatenated %d videos with a %.2fs %s → %s",
                n,
                overlap,
                transition.type if transition else "transition",
                output.name,
            )
        else:
            logger.info("Concatenated %d videos → %s", n, output.name)
        return ConcatResult(output, boundaries=boundaries, shift=overlap)

    @staticmethod
    def _xfade_filter(
        n: int,
        durations: list[float],
        overlap: float,
        name: str,
        fps: float,
    ) -> str:
        """Build the ``xfade`` chain joining *n* separate inputs."""
        norm = "format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS"
        if fps > 0:
            norm = f"fps={fps:.6f}," + norm
        parts = [f"[{i}:v:0]{norm}[c{i}]" for i in range(n)]
        parts.append(DemoEngine._xfade_chain(n, durations, overlap, name))
        return ";".join(parts)

    @staticmethod
    def _xfade_chain(n: int, durations: list[float], overlap: float, name: str) -> str:
        """Chain ``[c0]…[cN-1]`` into ``[outv]``.

        xfade's ``offset`` is expressed on the *accumulated* output, which
        shrinks by ``overlap`` at every junction.
        """
        parts = []
        acc = durations[0]
        prev = "[c0]"
        for i in range(1, n):
            label = "[outv]" if i == n - 1 else f"[x{i}]"
            offset = max(0.0, acc - overlap)
            parts.append(
                f"{prev}[c{i}]xfade=transition={name}:"
                f"duration={overlap:.3f}:offset={offset:.3f}{label}"
            )
            acc += durations[i] - overlap
            prev = label
        return ";".join(parts)

    @staticmethod
    def transition_boundaries(
        config: DemoConfig,
        step_timestamps: list[float],
        *,
        exclude: Sequence[float] = (),
        min_gap: float = 0.0,
    ) -> list[float]:
        """Step boundaries that should carry a transition.

        ``step_timestamps[i]`` is when step *i* becomes visible, so it is also
        the cut between step *i-1* and step *i* — for a ``navigate`` step that
        is exactly the moment the page swaps.
        """
        transition = config.video.transitions if config.video else None
        if transition is None or transition.between == "scenarios":
            return []

        steps = [s for scenario in config.scenarios for s in scenario.steps]
        candidates = list(step_timestamps[1:])
        if transition.between == "navigations":
            if len(steps) != len(step_timestamps):
                logger.warning(
                    "Recorded %d step boundaries for %d authored steps — "
                    "cannot tell which ones navigate, skipping step transitions",
                    len(step_timestamps),
                    len(steps),
                )
                return []
            candidates = [t for t, step in zip(candidates, steps[1:]) if step.action == "navigate"]

        kept: list[float] = []
        for t in candidates:
            if t <= 0:
                continue
            # Never start a fade inside another one.
            if any(abs(t - e) < min_gap for e in exclude):
                continue
            if kept and t - kept[-1] < min_gap:
                continue
            kept.append(t)
        return kept

    @staticmethod
    def _scene_cuts(video: Path, threshold: float = 0.3) -> list[float] | None:
        """Timestamps where the picture actually changes, per ffmpeg's scene score.

        ``None`` means the detection itself could not run — which is not the
        same answer as "this clip has no cut".
        """
        import re
        import subprocess

        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-i",
                    str(video),
                    "-vf",
                    f"select='gt(scene,{threshold})',metadata=print:file=-",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                timeout=600,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        if result.returncode != 0:
            return None
        return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", result.stdout)]

    @staticmethod
    def _snap_to_cuts(
        boundaries: list[float],
        cuts: list[float] | None,
        window: float,
        *,
        require_cut: bool = False,
    ) -> list[float]:
        """Pull each boundary onto the nearest real cut within *window* seconds.

        Step timestamps are measured on the recorder's clock, which drifts from
        the video's by the un-trimmed part of the pre-roll — enough for a
        sub-second fade to land beside the page swap instead of on it.

        With *require_cut*, a boundary with no cut in range is dropped rather
        than faded over identical frames.
        """
        if cuts is None:
            return boundaries
        snapped: list[float] = []
        for t in boundaries:
            nearest = min(cuts, key=lambda c: abs(c - t)) if cuts else None
            if nearest is not None and abs(nearest - t) <= window:
                candidate = nearest
            elif require_cut:
                continue
            else:
                candidate = t
            if candidate not in snapped:
                snapped.append(candidate)
        return sorted(snapped)

    @staticmethod
    def _apply_step_transitions(
        video: Path,
        output: Path,
        boundaries: list[float],
        transition: Transitions,
    ) -> ConcatResult:
        """Re-cut *video* at *boundaries* and cross-fade the slices back together."""
        import subprocess

        duration, _fps = DemoEngine._probe_stream(video)
        if duration <= 0 or not boundaries:
            return ConcatResult(video)

        requested = len(boundaries)
        boundaries = [
            t
            for t in DemoEngine._snap_to_cuts(
                boundaries,
                DemoEngine._scene_cuts(video),
                window=2.0,
                require_cut=transition.needs_visual_change,
            )
            if 0 < t < duration
        ]
        if len(boundaries) < requested:
            logger.info(
                "Dropped %d of %d beat transition(s): a %s over an unchanged picture "
                "is invisible and only shortens the video",
                requested - len(boundaries),
                requested,
                transition.type,
            )
        if not boundaries:
            return ConcatResult(video)

        cuts = [0.0, *boundaries, duration]
        slices = [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]
        durations = [end - start for start, end in slices]
        if min(durations) <= 0:
            logger.warning("Step boundaries do not split %s cleanly — skipping", video.name)
            return ConcatResult(video)

        overlap = min(transition.duration, min(durations) / 2)
        if overlap < 0.05:
            logger.warning(
                "Shortest beat is %.2fs — too short for a %.2fs %s, skipping step transitions",
                min(durations),
                transition.duration,
                transition.type,
            )
            return ConcatResult(video)

        n = len(slices)
        parts = [f"[0:v:0]split={n}" + "".join(f"[s{i}]" for i in range(n))]
        for i, (start, end) in enumerate(slices):
            parts.append(
                f"[s{i}]trim=start={start:.3f}:end={end:.3f},"
                f"setpts=PTS-STARTPTS,format=yuv420p,settb=AVTB[c{i}]"
            )
        parts.append(DemoEngine._xfade_chain(n, durations, overlap, transition.xfade_name))

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-filter_complex",
            ";".join(parts),
            "-map",
            "[outv]",
            *x264_args(pix_fmt=None),
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            logger.error("Step transitions failed: %s", result.stderr[-300:])
            return ConcatResult(video)
        logger.info(
            "Applied %d × %.2fs %s between beats → %s",
            n - 1,
            overlap,
            transition.type,
            output.name,
        )
        return ConcatResult(output, boundaries=tuple(boundaries), shift=overlap)

"""Pydantic v2 models for the DemoDSL DSL.

All public symbols are re-exported here so that existing imports like
``from demodsl.models import DemoConfig`` continue to work unchanged.
"""

from demodsl.models._base import _validate_css_color, _validate_css_color_list  # noqa: F401
from demodsl.models.audio import (
    AudioConfig,
    AudioEffects,
    BackgroundMusic,
    Compression,
    EQBand,
    VoiceProcessing,
)
from demodsl.models.config import Analytics, DemoConfig, LanguagesConfig
from demodsl.models.edit import EditConfig, PauseEdit
from demodsl.models.effects import EFFECT_VALID_PARAMS, Effect, EffectType
from demodsl.models.metadata import Metadata
from demodsl.models.mobile import MobileConfig
from demodsl.models.output import DeployConfig, OutputConfig, SocialExport, Thumbnail
from demodsl.models.overlays import (
    AVATAR_STYLES,
    AvatarConfig,
    CursorConfig,
    GlowSelectConfig,
    PopupCardConfig,
    SubtitleConfig,
)
from demodsl.models.pipeline import PipelineStage
from demodsl.models.rendering import DeviceRendering
from demodsl.models.scenario import (
    CameraMove,
    CardContent,
    DemoStoppedError,
    Locator,
    NaturalConfig,
    Scenario,
    Step,
    StopCondition,
    Viewport,
    ZoomInputConfig,
)
from demodsl.models.terminal import TerminalConfig
from demodsl.models.timeline import (
    Camera3D,
    Counter,
    DataBinding,
    DropShadow,
    FractalNoiseLayer,
    ImageLayer,
    Keyframe,
    MotionBlur,
    NullLayer,
    ParticleEmitter,
    PolylineLayer,
    Precomp,
    PrecompLayer,
    PropertyTrack,
    ShapeLayer,
    SpotlightLayer,
    TextAnimator,
    TextLayer,
    Timeline,
    TimeRemap,
    Tracker,
    TrackPoint,
    Transform,
)
from demodsl.models.video import (
    ChapterMarker,
    ColorCorrection,
    Intro,
    Outro,
    PictureInPicture,
    SpeedRamp,
    Transitions,
    VideoConfig,
    VideoOptimization,
    Watermark,
)
from demodsl.models.voice import VoiceConfig

# Re-export validators for backward compatibility (some modules import these
# private names directly from demodsl.models).
from demodsl.validators import (  # noqa: F401
    _ALLOWED_URL_SCHEMES,
    _BLOCKED_PREFIXES,
    _BLOCKED_PREFIXES_WIN,
    _validate_safe_path,
    _validate_url,
)

__all__ = [
    "Analytics",
    "AudioConfig",
    "AudioEffects",
    "AvatarConfig",
    "AVATAR_STYLES",
    "BackgroundMusic",
    "CameraMove",
    "CardContent",
    "ChapterMarker",
    "ColorCorrection",
    "Compression",
    "CursorConfig",
    "DemoConfig",
    "DemoStoppedError",
    "DeployConfig",
    "EditConfig",
    "DeviceRendering",
    "EQBand",
    "Effect",
    "EFFECT_VALID_PARAMS",
    "EffectType",
    "GlowSelectConfig",
    "Intro",
    "LanguagesConfig",
    "Locator",
    "Metadata",
    "MobileConfig",
    "NaturalConfig",
    "OutputConfig",
    "Outro",
    "PauseEdit",
    "PictureInPicture",
    "PipelineStage",
    "PopupCardConfig",
    "PropertyTrack",
    "Scenario",
    "ShapeLayer",
    "SocialExport",
    "SpeedRamp",
    "Step",
    "StopCondition",
    "SubtitleConfig",
    "TextLayer",
    "Thumbnail",
    "Timeline",
    "Transform",
    "Transitions",
    "VideoConfig",
    "VideoOptimization",
    "Viewport",
    "VoiceConfig",
    "VoiceProcessing",
    "Watermark",
    "ZoomInputConfig",
    "Camera3D",
    "Counter",
    "DataBinding",
    "DropShadow",
    "ImageLayer",
    "Keyframe",
    "MotionBlur",
    "NullLayer",
    "FractalNoiseLayer",
    "ParticleEmitter",
    "PolylineLayer",
    "Precomp",
    "PrecompLayer",
    "SpotlightLayer",
    "TextAnimator",
    "TimeRemap",
    "TrackPoint",
    "Tracker",
]

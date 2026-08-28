"""Output, deploy, and distribution models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from demodsl.models._base import _StrictBase


class Thumbnail(_StrictBase):
    timestamp: float | None = Field(default=None, ge=0)
    auto: bool = Field(
        default=False,
        description="Auto-select best frame based on contrast/sharpness.",
    )
    overlay_text: str | None = None
    format: Literal["png", "jpeg", "webp"] = "png"


class SocialExport(_StrictBase):
    platform: Literal[
        "youtube",
        "instagram_reels",
        "tiktok",
        "twitter",
        "linkedin",
        "custom",
    ]
    resolution: str | None = None
    bitrate: str | None = None
    aspect_ratio: str | None = None
    max_duration: int | None = Field(default=None, gt=0)
    max_size_mb: int | None = Field(default=None, gt=0)
    crop_mode: Literal["center", "smart", "blur_pad"] = "center"


class DeployConfig(_StrictBase):
    """Cloud deployment configuration for uploading output videos."""

    provider: str = Field(
        description=(
            "Built-in: s3, r2, gcs, azure_blob, custom. Plugins add more "
            "through the demodsl.providers.deploy entry-point group."
        )
    )
    bucket: str
    region: str | None = None
    prefix: str = ""
    acl: str | None = None
    content_type: str = "video/mp4"
    endpoint_url: str | None = None  # custom S3-compatible endpoint (R2, MinIO, etc.)
    # Credentials resolve via env vars — supports ${ENV_VAR} syntax
    access_key: str | None = Field(default=None, repr=False)  # ${AWS_ACCESS_KEY_ID}
    secret_key: str | None = Field(default=None, repr=False)  # ${AWS_SECRET_ACCESS_KEY}
    # GCS
    project: str | None = None
    credentials_file: str | None = None  # path to service account JSON
    # Azure
    connection_string: str | None = Field(
        default=None,
        repr=False,
    )  # ${AZURE_STORAGE_CONNECTION_STRING}
    container: str | None = None  # alias for bucket in Azure terminology

    @field_validator("provider")
    @classmethod
    def _known_provider(cls, v: str) -> str:
        """Reject an unknown name here rather than at upload time.

        The list has to be resolved at validation time, not frozen in a
        Literal: a plugin's providers only exist once its entry points are
        scanned. Loading them does not pull their cloud SDK, so this stays
        cheap enough to run on every parse.
        """
        from demodsl.providers.deploy import DeployProviderFactory

        available = DeployProviderFactory.available()
        if v not in available:
            raise ValueError(f"Unknown deploy provider {v!r}. Available: {available}")
        return v


class OutputConfig(_StrictBase):
    filename: str = "output.mp4"
    directory: str = "output/"
    formats: list[str] = Field(default_factory=lambda: ["mp4"])
    branding: bool = Field(
        default=True,
        description="Burn '@demodsl' watermark on the final video. Set to false to disable.",
    )
    thumbnails: list[Thumbnail] | None = None
    social: list[SocialExport] | None = None
    deploy: DeployConfig | None = None

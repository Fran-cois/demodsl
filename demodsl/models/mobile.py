"""Mobile (Appium) configuration model."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from demodsl.models._base import _StrictBase
from demodsl.validators import _validate_safe_path


class MobileConfig(_StrictBase):
    """Configuration for native mobile app demos via Appium."""

    platform: Literal["android", "ios"]
    device_name: str = Field(
        description="Appium device/emulator name (e.g. 'Pixel 7', 'iPhone 15 Pro')."
    )
    app: str | None = Field(
        default=None,
        description="Path or URL to the .apk / .ipa to install.",
    )
    app_package: str | None = Field(
        default=None,
        description="Android app package (e.g. 'com.example.app').",
    )
    app_activity: str | None = Field(
        default=None,
        description="Android app launch activity.",
    )
    bundle_id: str | None = Field(
        default=None,
        description="iOS bundle identifier (e.g. 'com.example.app').",
    )
    udid: str | None = Field(
        default=None,
        description="Unique device ID (required for real devices).",
    )
    automation_name: Literal["UiAutomator2", "XCUITest"] | None = Field(
        default=None,
        description="Appium automation engine. Defaults based on platform.",
    )
    appium_server: str = Field(
        default="http://127.0.0.1:4723",
        description="Appium server URL.",
    )
    no_reset: bool = Field(
        default=True,
        description="Don't reset app state between sessions.",
    )
    full_reset: bool = Field(
        default=False,
        description="Uninstall app before session starts.",
    )
    orientation: Literal["portrait", "landscape"] = "portrait"

    @field_validator("app")
    @classmethod
    def _safe_app(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("http"):
            return _validate_safe_path(v)
        return v

    @model_validator(mode="after")
    def _validate_platform_fields(self) -> MobileConfig:
        if self.platform == "android" and not self.app and not self.app_package:
            raise ValueError("Android requires 'app' (path to APK) or 'app_package'.")
        if self.platform == "ios" and not self.app and not self.bundle_id:
            raise ValueError("iOS requires 'app' (path to IPA) or 'bundle_id'.")
        return self

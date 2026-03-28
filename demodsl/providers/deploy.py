"""Cloud deploy providers — upload output videos to S3, GCS, Azure Blob, R2, or custom."""

from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def resolve_env_vars(value: str | None) -> str | None:
    """Resolve ``${ENV_VAR}`` placeholders in a string."""
    if value is None:
        return None
    return re.sub(
        r"\$\{(\w+)\}",
        lambda m: os.environ.get(m.group(1), m.group(0)),
        value,
    )


# ── Abstract base ─────────────────────────────────────────────────────────────


class DeployProvider(ABC):
    """Upload a file to a cloud storage provider."""

    @abstractmethod
    def upload(self, local_path: Path, remote_key: str) -> str:
        """Upload *local_path* to *remote_key*. Returns the public URL (or URI)."""

    @abstractmethod
    def close(self) -> None:
        """Release resources / connections."""


class DeployProviderFactory:
    _registry: dict[str, type[DeployProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[DeployProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> DeployProvider:
        if name not in cls._registry:
            raise ValueError(
                f"Unknown deploy provider '{name}'. Available: {list(cls._registry)}"
            )
        return cls._registry[name](**kwargs)


# ── S3 (AWS + S3-compatible: R2, MinIO, Wasabi, Backblaze) ────────────────────


class S3DeployProvider(DeployProvider):
    """Upload to Amazon S3 or any S3-compatible service."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        acl: str | None = None,
        content_type: str = "video/mp4",
        **_kwargs: Any,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.endpoint_url = resolve_env_vars(endpoint_url)
        self.access_key = resolve_env_vars(access_key)
        self.secret_key = resolve_env_vars(secret_key)
        self.acl = acl
        self.content_type = content_type
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3

            kwargs: dict[str, Any] = {}
            if self.region:
                kwargs["region_name"] = self.region
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            if self.access_key and self.secret_key:
                kwargs["aws_access_key_id"] = self.access_key
                kwargs["aws_secret_access_key"] = self.secret_key
            self._client = boto3.client("s3", **kwargs)
        return self._client

    def upload(self, local_path: Path, remote_key: str) -> str:
        client = self._get_client()
        extra_args: dict[str, str] = {"ContentType": self.content_type}
        if self.acl:
            extra_args["ACL"] = self.acl

        logger.info("Uploading %s → s3://%s/%s", local_path.name, self.bucket, remote_key)
        client.upload_file(str(local_path), self.bucket, remote_key, ExtraArgs=extra_args)

        if self.endpoint_url:
            url = f"{self.endpoint_url}/{self.bucket}/{remote_key}"
        elif self.region:
            url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{remote_key}"
        else:
            url = f"https://{self.bucket}.s3.amazonaws.com/{remote_key}"

        logger.info("Uploaded: %s", url)
        return url

    def close(self) -> None:
        self._client = None


# ── GCS (Google Cloud Storage) ────────────────────────────────────────────────


class GCSDeployProvider(DeployProvider):
    """Upload to Google Cloud Storage."""

    def __init__(
        self,
        *,
        bucket: str,
        project: str | None = None,
        credentials_file: str | None = None,
        content_type: str = "video/mp4",
        acl: str | None = None,
        **_kwargs: Any,
    ) -> None:
        self.bucket_name = bucket
        self.project = project
        self.credentials_file = resolve_env_vars(credentials_file)
        self.content_type = content_type
        self.acl = acl
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google.cloud import storage

            kwargs: dict[str, Any] = {}
            if self.project:
                kwargs["project"] = self.project
            if self.credentials_file:
                self._client = storage.Client.from_service_account_json(
                    self.credentials_file, **kwargs
                )
            else:
                self._client = storage.Client(**kwargs)
        return self._client

    def upload(self, local_path: Path, remote_key: str) -> str:
        client = self._get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(remote_key)

        logger.info("Uploading %s → gs://%s/%s", local_path.name, self.bucket_name, remote_key)
        blob.upload_from_filename(str(local_path), content_type=self.content_type)

        if self.acl:
            blob.acl.save_predefined(self.acl)

        url = f"https://storage.googleapis.com/{self.bucket_name}/{remote_key}"
        logger.info("Uploaded: %s", url)
        return url

    def close(self) -> None:
        self._client = None


# ── Azure Blob Storage ────────────────────────────────────────────────────────


class AzureBlobDeployProvider(DeployProvider):
    """Upload to Azure Blob Storage."""

    def __init__(
        self,
        *,
        bucket: str | None = None,
        container: str | None = None,
        connection_string: str | None = None,
        content_type: str = "video/mp4",
        **_kwargs: Any,
    ) -> None:
        self.container_name = container or bucket
        if not self.container_name:
            raise ValueError("Azure deploy requires 'bucket' or 'container'")
        self.connection_string = resolve_env_vars(connection_string)
        if not self.connection_string:
            # Fall back to environment variable
            self.connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.content_type = content_type
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from azure.storage.blob import BlobServiceClient

            if not self.connection_string:
                raise ValueError(
                    "Azure deploy requires 'connection_string' or AZURE_STORAGE_CONNECTION_STRING env var"
                )
            self._client = BlobServiceClient.from_connection_string(self.connection_string)
        return self._client

    def upload(self, local_path: Path, remote_key: str) -> str:
        client = self._get_client()
        container_client = client.get_container_client(self.container_name)

        from azure.storage.blob import ContentSettings

        content_settings = ContentSettings(content_type=self.content_type)

        logger.info(
            "Uploading %s → az://%s/%s", local_path.name, self.container_name, remote_key
        )
        with open(local_path, "rb") as f:
            container_client.upload_blob(
                name=remote_key,
                data=f,
                overwrite=True,
                content_settings=content_settings,
            )

        account_name = self._extract_account_name()
        url = f"https://{account_name}.blob.core.windows.net/{self.container_name}/{remote_key}"
        logger.info("Uploaded: %s", url)
        return url

    def _extract_account_name(self) -> str:
        if self.connection_string:
            match = re.search(r"AccountName=([^;]+)", self.connection_string)
            if match:
                return match.group(1)
        return "unknown"

    def close(self) -> None:
        self._client = None


# ── Register all providers ────────────────────────────────────────────────────

DeployProviderFactory.register("s3", S3DeployProvider)
DeployProviderFactory.register("r2", S3DeployProvider)  # Cloudflare R2 is S3-compatible
DeployProviderFactory.register("gcs", GCSDeployProvider)
DeployProviderFactory.register("azure_blob", AzureBlobDeployProvider)
# "custom" uses S3 protocol with custom endpoint_url
DeployProviderFactory.register("custom", S3DeployProvider)

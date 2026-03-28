"""Tests for demodsl.providers.deploy — Cloud deploy providers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.providers.deploy import (
    AzureBlobDeployProvider,
    DeployProvider,
    DeployProviderFactory,
    GCSDeployProvider,
    S3DeployProvider,
    resolve_env_vars,
)

_has_boto3 = (
    "boto3" in sys.modules
    or __import__("importlib").util.find_spec("boto3") is not None
)
_has_azure = (
    __import__("importlib").util.find_spec("azure") is not None
    and __import__("importlib").util.find_spec("azure.storage") is not None
)


# ── resolve_env_vars ──────────────────────────────────────────────────────────


class TestResolveEnvVars:
    def test_none_returns_none(self) -> None:
        assert resolve_env_vars(None) is None

    def test_no_placeholders(self) -> None:
        assert resolve_env_vars("plain-value") == "plain-value"

    def test_single_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_KEY", "secret123")
        assert resolve_env_vars("${MY_KEY}") == "secret123"

    def test_multiple_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")
        assert resolve_env_vars("${HOST}:${PORT}") == "localhost:8080"

    def test_missing_env_var_keeps_placeholder(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        assert resolve_env_vars("${NONEXISTENT_VAR}") == "${NONEXISTENT_VAR}"

    def test_allowlist_permits_listed_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ALLOWED", "yes")
        assert resolve_env_vars("${ALLOWED}", allowed=frozenset({"ALLOWED"})) == "yes"

    def test_allowlist_blocks_unlisted_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SECRET", "nope")
        result = resolve_env_vars("${SECRET}", allowed=frozenset({"OTHER"}))
        assert result == "${SECRET}"

    def test_allowlist_partial(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OK", "val")
        monkeypatch.setenv("BLOCKED", "hidden")
        result = resolve_env_vars("${OK}-${BLOCKED}", allowed=frozenset({"OK"}))
        assert result == "val-${BLOCKED}"


# ── DeployProviderFactory ─────────────────────────────────────────────────────


class TestDeployProviderFactory:
    def test_registered_providers(self) -> None:
        for name in ("s3", "r2", "gcs", "azure_blob", "custom"):
            assert name in DeployProviderFactory._registry

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown deploy provider 'nope'"):
            DeployProviderFactory.create("nope")

    def test_create_s3(self) -> None:
        provider = DeployProviderFactory.create("s3", bucket="my-bucket")
        assert isinstance(provider, S3DeployProvider)

    def test_create_r2_returns_s3(self) -> None:
        provider = DeployProviderFactory.create("r2", bucket="my-bucket")
        assert isinstance(provider, S3DeployProvider)

    def test_create_custom_returns_s3(self) -> None:
        provider = DeployProviderFactory.create(
            "custom", bucket="b", endpoint_url="https://my.s3.endpoint"
        )
        assert isinstance(provider, S3DeployProvider)

    def test_create_gcs(self) -> None:
        provider = DeployProviderFactory.create("gcs", bucket="my-bucket")
        assert isinstance(provider, GCSDeployProvider)

    def test_create_azure(self) -> None:
        provider = DeployProviderFactory.create(
            "azure_blob",
            container="my-container",
            connection_string="DefaultEndpointsProtocol=https;AccountName=test",
        )
        assert isinstance(provider, AzureBlobDeployProvider)

    def test_register_custom_provider(self) -> None:
        class DummyDeploy(DeployProvider):
            def upload(self, local_path: Path, remote_key: str) -> str:
                return "dummy://ok"

            def close(self) -> None:
                pass

        DeployProviderFactory.register("dummy_test", DummyDeploy)
        p = DeployProviderFactory.create("dummy_test")
        assert isinstance(p, DummyDeploy)
        # Cleanup
        del DeployProviderFactory._registry["dummy_test"]


# ── S3DeployProvider ──────────────────────────────────────────────────────────


class TestS3DeployProvider:
    def test_init_stores_fields(self) -> None:
        p = S3DeployProvider(
            bucket="b",
            region="us-east-1",
            acl="public-read",
            access_key="ak",
            secret_key="sk",
        )
        assert p.bucket == "b"
        assert p.region == "us-east-1"
        assert p.acl == "public-read"

    @patch("demodsl.providers.deploy.S3DeployProvider._get_client")
    def test_upload_returns_url(self, mock_get: MagicMock, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        video = tmp_path / "demo.mp4"
        video.write_bytes(b"\x00" * 10)

        p = S3DeployProvider(bucket="my-bucket", region="eu-west-1")
        url = p.upload(video, "demos/demo.mp4")
        assert "my-bucket" in url
        assert "demos/demo.mp4" in url
        mock_client.upload_file.assert_called_once()

    @patch("demodsl.providers.deploy.S3DeployProvider._get_client")
    def test_upload_with_endpoint_url(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        video = tmp_path / "v.mp4"
        video.write_bytes(b"\x00")

        p = S3DeployProvider(bucket="b", endpoint_url="https://r2.example.com")
        url = p.upload(video, "k")
        assert url == "https://r2.example.com/b/k"

    @patch("demodsl.providers.deploy.S3DeployProvider._get_client")
    def test_upload_no_region_no_endpoint(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        video = tmp_path / "v.mp4"
        video.write_bytes(b"\x00")

        p = S3DeployProvider(bucket="b")
        url = p.upload(video, "k")
        assert url == "https://b.s3.amazonaws.com/k"

    def test_close(self) -> None:
        p = S3DeployProvider(bucket="b")
        p._client = MagicMock()
        p.close()
        assert p._client is None

    @pytest.mark.skipif(not _has_boto3, reason="boto3 not installed")
    @patch("boto3.client")
    def test_get_client_lazy(self, mock_boto: MagicMock) -> None:
        p = S3DeployProvider(bucket="b", region="us-east-1")
        assert p._client is None
        c = p._get_client()
        mock_boto.assert_called_once()
        assert c is mock_boto.return_value
        # Second call returns cached
        c2 = p._get_client()
        assert c2 is c
        mock_boto.assert_called_once()  # not called again


# ── GCSDeployProvider ─────────────────────────────────────────────────────────


class TestGCSDeployProvider:
    def test_init_stores_fields(self) -> None:
        p = GCSDeployProvider(bucket="my-gcs-bucket", project="my-project")
        assert p.bucket_name == "my-gcs-bucket"
        assert p.project == "my-project"

    @patch("demodsl.providers.deploy.GCSDeployProvider._get_client")
    def test_upload_returns_url(self, mock_get: MagicMock, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_get.return_value = mock_client

        video = tmp_path / "demo.mp4"
        video.write_bytes(b"\x00" * 10)

        p = GCSDeployProvider(bucket="gcs-bucket")
        url = p.upload(video, "demos/demo.mp4")
        assert "gcs-bucket" in url
        assert "demos/demo.mp4" in url
        mock_blob.upload_from_filename.assert_called_once()

    @patch("demodsl.providers.deploy.GCSDeployProvider._get_client")
    def test_upload_with_acl(self, mock_get: MagicMock, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_get.return_value = mock_client

        video = tmp_path / "v.mp4"
        video.write_bytes(b"\x00")

        p = GCSDeployProvider(bucket="b", acl="publicRead")
        p.upload(video, "k")
        mock_blob.acl.save_predefined.assert_called_once_with("publicRead")

    def test_close(self) -> None:
        p = GCSDeployProvider(bucket="b")
        p._client = MagicMock()
        p.close()
        assert p._client is None


# ── AzureBlobDeployProvider ───────────────────────────────────────────────────


class TestAzureBlobDeployProvider:
    def test_init_with_container(self) -> None:
        p = AzureBlobDeployProvider(
            container="my-container",
            connection_string="DefaultEndpointsProtocol=https;AccountName=acct;",
        )
        assert p.container_name == "my-container"

    def test_init_with_bucket_alias(self) -> None:
        p = AzureBlobDeployProvider(
            bucket="my-bucket",
            connection_string="DefaultEndpointsProtocol=https;AccountName=acct;",
        )
        assert p.container_name == "my-bucket"

    def test_init_no_container_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
        with pytest.raises(ValueError, match="'bucket' or 'container'"):
            AzureBlobDeployProvider()

    def test_extract_account_name(self) -> None:
        p = AzureBlobDeployProvider(
            container="c",
            connection_string="DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=xxx",
        )
        assert p._extract_account_name() == "myaccount"

    def test_extract_account_name_fallback(self) -> None:
        p = AzureBlobDeployProvider(container="c", connection_string="no-account-here")
        assert p._extract_account_name() == "unknown"

    @pytest.mark.skipif(not _has_azure, reason="azure-storage-blob not installed")
    @patch("demodsl.providers.deploy.AzureBlobDeployProvider._get_client")
    def test_upload_returns_url(self, mock_get: MagicMock, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.get_container_client.return_value = mock_container
        mock_get.return_value = mock_client

        video = tmp_path / "demo.mp4"
        video.write_bytes(b"\x00" * 10)

        p = AzureBlobDeployProvider(
            container="my-container",
            connection_string="DefaultEndpointsProtocol=https;AccountName=acct;",
        )
        url = p.upload(video, "demos/demo.mp4")
        assert "acct.blob.core.windows.net" in url
        assert "my-container" in url
        mock_container.upload_blob.assert_called_once()

    def test_close(self) -> None:
        p = AzureBlobDeployProvider(container="c", connection_string="x")
        p._client = MagicMock()
        p.close()
        assert p._client is None


# ── DeployConfig model ────────────────────────────────────────────────────────


class TestDeployConfigModel:
    def test_s3_config(self) -> None:
        from demodsl.models import DeployConfig

        cfg = DeployConfig(provider="s3", bucket="my-bucket", region="us-east-1")
        assert cfg.provider == "s3"
        assert cfg.bucket == "my-bucket"

    def test_gcs_config(self) -> None:
        from demodsl.models import DeployConfig

        cfg = DeployConfig(provider="gcs", bucket="gcs-bucket", project="proj")
        assert cfg.provider == "gcs"
        assert cfg.project == "proj"

    def test_azure_config(self) -> None:
        from demodsl.models import DeployConfig

        cfg = DeployConfig(
            provider="azure_blob",
            bucket="my-container",
            connection_string="conn_str",
        )
        assert cfg.provider == "azure_blob"
        assert cfg.connection_string == "conn_str"

    def test_deploy_in_output_config(self) -> None:
        from demodsl.models import OutputConfig

        out = OutputConfig(
            filename="demo.mp4",
            deploy={"provider": "s3", "bucket": "b"},
        )
        assert out.deploy is not None
        assert out.deploy.provider == "s3"

    def test_output_config_no_deploy(self) -> None:
        from demodsl.models import OutputConfig

        out = OutputConfig(filename="demo.mp4")
        assert out.deploy is None

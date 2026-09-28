"""Tests for application configuration."""

import pytest
from pydantic import ValidationError

from jev_plugin.config import Settings


def test_settings_loads_required_typesafe_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings should load successfully when the API key is provided."""
    monkeypatch.setenv(
        "TYPESAFE_API_KEY",
        "test-api-key",
    )

    settings = Settings()

    assert settings.app_name == "jev-chatgpt-plugin"
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.typesafe_model == "jev-latest"
    assert settings.typesafe_api_key.get_secret_value() == "test-api-key"


def test_settings_rejects_missing_typesafe_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings should fail when the required API key is missing."""
    monkeypatch.delenv(
        "TYPESAFE_API_KEY",
        raising=False,
    )

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_loads_mcp_log_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MCP log level should be read from its dedicated environment variable."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-api-key")
    monkeypatch.setenv("MCP_LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.mcp_log_level == "DEBUG"

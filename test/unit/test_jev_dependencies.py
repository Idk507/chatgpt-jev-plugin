"""Unit tests for the Jev dependency composition layer.

These tests verify that the application dependency graph is composed and
released correctly without making any real TypeSafe API requests.

Dependency graph under test:

    Settings
        |
        v
    JevClient
        |
        v
    JevService
        |
        v
    JevDependencies

The tests use an injected TypeSafe SDK client so that the test suite remains
deterministic and does not require network access or a real API key.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr
from typesafe_sdk import TypeSafeClient

from jev_plugin.config import Settings
from jev_plugin.jev import JevClient, JevService
from jev_plugin.mcp.dependencies import (
    JevDependencies,
    create_jev_dependencies,
)


@pytest.fixture
def settings() -> Settings:
    """Return deterministic application settings for tests."""
    return Settings(
        app_name="jev-test",
        app_env="test",
        log_level="DEBUG",
        typesafe_api_key=SecretStr("test-api-key"),
        typesafe_model="jev-test-model",
    )


@pytest.fixture
def sdk_client() -> MagicMock:
    """Return a deterministic injected TypeSafe SDK client."""
    return MagicMock(spec=TypeSafeClient)


def test_create_jev_dependencies_builds_complete_graph(
    settings: Settings,
    sdk_client: MagicMock,
) -> None:
    """The dependency container should create both client and service."""
    dependencies = create_jev_dependencies(
        settings=settings,
        sdk_client=sdk_client,
    )

    assert isinstance(dependencies, JevDependencies)
    assert isinstance(dependencies.client, JevClient)
    assert isinstance(dependencies.service, JevService)


def test_create_jev_dependencies_uses_injected_sdk_client(
    settings: Settings,
    sdk_client: MagicMock,
) -> None:
    """The injected SDK client should be owned by the Jev client."""
    dependencies = create_jev_dependencies(
        settings=settings,
        sdk_client=sdk_client,
    )

    assert dependencies.client._client is sdk_client


def test_service_uses_composed_client(
    settings: Settings,
    sdk_client: MagicMock,
) -> None:
    """The Jev service should receive the exact composed Jev client."""
    dependencies = create_jev_dependencies(
        settings=settings,
        sdk_client=sdk_client,
    )

    assert dependencies.service._client is dependencies.client


def test_dependency_container_exposes_client_and_service(
    settings: Settings,
    sdk_client: MagicMock,
) -> None:
    """The dependency container should expose its application components."""
    dependencies = JevDependencies.create(
        settings=settings,
        sdk_client=sdk_client,
    )

    assert dependencies.client is not None
    assert dependencies.service is not None


def test_dependency_container_is_open_after_creation(
    settings: Settings,
    sdk_client: MagicMock,
) -> None:
    """A newly created dependency container should not be closed."""
    dependencies = create_jev_dependencies(
        settings=settings,
        sdk_client=sdk_client,
    )

    assert dependencies.is_closed is False
    assert dependencies.client.is_closed is False


def test_close_releases_sdk_resources(
    settings: Settings,
    sdk_client: MagicMock,
) -> None:
    """Closing dependencies should close the underlying SDK client."""
    dependencies = create_jev_dependencies(
        settings=settings,
        sdk_client=sdk_client,
    )

    dependencies.close()

    sdk_client.close.assert_called_once()
    assert dependencies.is_closed is True
    assert dependencies.client.is_closed is True


def test_close_is_idempotent(
    settings: Settings,
    sdk_client: MagicMock,
) -> None:
    """Calling close repeatedly should not close the SDK twice."""
    dependencies = create_jev_dependencies(
        settings=settings,
        sdk_client=sdk_client,
    )

    dependencies.close()
    dependencies.close()

    sdk_client.close.assert_called_once()
    assert dependencies.is_closed is True


def test_context_manager_closes_dependencies(
    settings: Settings,
    sdk_client: MagicMock,
) -> None:
    """Leaving the dependency context should release resources."""
    with create_jev_dependencies(
        settings=settings,
        sdk_client=sdk_client,
    ) as dependencies:
        assert dependencies.is_closed is False
        assert dependencies.client.is_closed is False

    sdk_client.close.assert_called_once()
    assert dependencies.is_closed is True


def test_context_manager_propagates_exceptions(
    settings: Settings,
    sdk_client: MagicMock,
) -> None:
    """Dependency context management should not suppress application errors."""
    error = RuntimeError("application failure")

    with pytest.raises(RuntimeError, match="application failure"):
        with create_jev_dependencies(
            settings=settings,
            sdk_client=sdk_client,
        ):
            raise error

    sdk_client.close.assert_called_once()


def test_cannot_reenter_closed_dependency_container(
    settings: Settings,
    sdk_client: MagicMock,
) -> None:
    """A closed dependency container must not be reusable."""
    dependencies = create_jev_dependencies(
        settings=settings,
        sdk_client=sdk_client,
    )

    dependencies.close()

    with pytest.raises(
        RuntimeError,
        match="Cannot enter a closed Jev dependency container",
    ):
        dependencies.__enter__()


def test_create_function_delegates_to_dependency_factory(
    settings: Settings,
    sdk_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public factory should delegate to JevDependencies.create."""
    expected = MagicMock(spec=JevDependencies)

    def fake_create(
        cls: type[JevDependencies],
        *,
        settings: Settings | None = None,
        sdk_client: TypeSafeClient | None = None,
    ) -> JevDependencies:
        assert settings is settings_fixture
        assert sdk_client is sdk_client_fixture
        return expected

    settings_fixture = settings
    sdk_client_fixture = sdk_client

    monkeypatch.setattr(
        JevDependencies,
        "create",
        classmethod(fake_create),
    )

    result = create_jev_dependencies(
        settings=settings_fixture,
        sdk_client=sdk_client_fixture,
    )

    assert result is expected


def test_create_function_uses_get_settings_when_settings_omitted(
    sdk_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The factory should resolve application settings when omitted."""
    expected_settings = Settings(
        app_name="jev-test",
        app_env="test",
        log_level="DEBUG",
        typesafe_api_key=SecretStr("test-api-key"),
        typesafe_model="jev-test-model",
    )

    captured: dict[str, object] = {}

    def fake_get_settings() -> Settings:
        return expected_settings

    original_create = JevDependencies.create

    def fake_create(
        cls: type[JevDependencies],
        *,
        settings: Settings | None = None,
        sdk_client: TypeSafeClient | None = None,
    ) -> JevDependencies:
        captured["settings"] = settings
        captured["sdk_client"] = sdk_client
        return object.__new__(JevDependencies)

    monkeypatch.setattr(
        "jev_plugin.mcp.dependencies.get_settings",
        fake_get_settings,
    )
    monkeypatch.setattr(
        JevDependencies,
        "create",
        classmethod(fake_create),
    )

    try:
        result = create_jev_dependencies(
            sdk_client=sdk_client,
        )
    finally:
        monkeypatch.setattr(
            JevDependencies,
            "create",
            classmethod(original_create.__func__),
        )

    assert isinstance(result, JevDependencies)
    assert captured["settings"] is None
    assert captured["sdk_client"] is sdk_client


def test_create_cleans_up_client_when_service_creation_fails(
    settings: Settings,
    sdk_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A service-construction failure should not leak the SDK client."""
    service_error = RuntimeError("service construction failed")

    def raise_service_error(client: JevClient) -> JevService:
        assert client is not None
        raise service_error

    monkeypatch.setattr(
        "jev_plugin.mcp.dependencies.JevService",
        raise_service_error,
    )

    with pytest.raises(
        RuntimeError,
        match="service construction failed",
    ):
        JevDependencies.create(
            settings=settings,
            sdk_client=sdk_client,
        )

    sdk_client.close.assert_called_once()

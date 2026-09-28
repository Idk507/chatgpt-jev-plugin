
"""Unit tests for the Jev MCP server lifespan.

These tests verify the lifecycle boundary between the MCP server and the
application-owned Jev dependency container.

Lifecycle under test:

    MCP startup
        |
        v
    create_jev_dependencies()
        |
        v
    JevDependencies
        |
        v
    yield
        |
        v
    MCP request handling
        |
        v
    lifespan exit
        |
        v
    JevDependencies.close()

The tests do not create real TypeSafe SDK clients or perform network calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from mcp.server import MCPServer

from jev_plugin.mcp.dependencies import JevDependencies
from jev_plugin.mcp.lifespan import jev_server_lifespan


@pytest.fixture
def server() -> MCPServer[None]:
    """Return an isolated MCP server instance."""
    return MCPServer(
        name="jev-test",
        version="test",
    )


@pytest.fixture
def dependencies() -> MagicMock:
    """Return a deterministic dependency-container test double."""
    dependency_container = MagicMock(spec=JevDependencies)
    dependency_container.is_closed = False
    return dependency_container


@pytest.mark.anyio
async def test_lifespan_creates_and_yields_dependencies(
    server: MCPServer[None],
    dependencies: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lifespan should create and yield the Jev dependencies."""
    create_mock = MagicMock(return_value=dependencies)

    monkeypatch.setattr(
        "jev_plugin.mcp.lifespan.create_jev_dependencies",
        create_mock,
    )

    async with jev_server_lifespan(server) as yielded_dependencies:
        assert yielded_dependencies is dependencies
        create_mock.assert_called_once_with()
        dependencies.close.assert_not_called()


@pytest.mark.anyio
async def test_lifespan_closes_dependencies_on_normal_exit(
    server: MCPServer[None],
    dependencies: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lifespan should close dependencies after normal shutdown."""
    create_mock = MagicMock(return_value=dependencies)

    monkeypatch.setattr(
        "jev_plugin.mcp.lifespan.create_jev_dependencies",
        create_mock,
    )

    async with jev_server_lifespan(server) as yielded_dependencies:
        assert yielded_dependencies is dependencies

    create_mock.assert_called_once_with()
    dependencies.close.assert_called_once_with()


@pytest.mark.anyio
async def test_lifespan_closes_dependencies_when_body_raises(
    server: MCPServer[None],
    dependencies: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dependency cleanup must happen even when request handling fails."""
    create_mock = MagicMock(return_value=dependencies)

    monkeypatch.setattr(
        "jev_plugin.mcp.lifespan.create_jev_dependencies",
        create_mock,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated request failure",
    ):
        async with jev_server_lifespan(server) as yielded_dependencies:
            assert yielded_dependencies is dependencies
            raise RuntimeError("simulated request failure")

    create_mock.assert_called_once_with()
    dependencies.close.assert_called_once_with()


@pytest.mark.anyio
async def test_lifespan_does_not_close_dependencies_before_exit(
    server: MCPServer[None],
    dependencies: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dependencies must remain open for the entire lifespan body."""
    create_mock = MagicMock(return_value=dependencies)

    monkeypatch.setattr(
        "jev_plugin.mcp.lifespan.create_jev_dependencies",
        create_mock,
    )

    async with jev_server_lifespan(server):
        dependencies.close.assert_not_called()

    dependencies.close.assert_called_once_with()


@pytest.mark.anyio
async def test_lifespan_propagates_dependency_initialization_failure(
    server: MCPServer[None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup errors from dependency creation must not be swallowed."""
    initialization_error = RuntimeError(
        "unable to initialize Jev dependencies",
    )

    create_mock = MagicMock(side_effect=initialization_error)

    monkeypatch.setattr(
        "jev_plugin.mcp.lifespan.create_jev_dependencies",
        create_mock,
    )

    with pytest.raises(
        RuntimeError,
        match="unable to initialize Jev dependencies",
    ):
        async with jev_server_lifespan(server):
            pytest.fail(
                "The lifespan body must not execute when initialization fails.",
            )

    create_mock.assert_called_once_with()


@pytest.mark.anyio
async def test_lifespan_uses_supplied_server_instance(
    server: MCPServer[None],
    dependencies: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lifespan should accept the MCP server instance from the SDK."""
    create_mock = MagicMock(return_value=dependencies)

    monkeypatch.setattr(
        "jev_plugin.mcp.lifespan.create_jev_dependencies",
        create_mock,
    )

    async with jev_server_lifespan(server):
        assert create_mock.call_count == 1

    dependencies.close.assert_called_once_with()


def test_lifespan_is_importable() -> None:
    """The lifespan function should remain a public module-level symbol."""
    assert callable(jev_server_lifespan)

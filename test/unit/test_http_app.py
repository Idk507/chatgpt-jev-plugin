"""Unit tests for the Jev Streamable HTTP MCP application."""

from __future__ import annotations

import httpx2
import pytest
from mcp.server import MCPServer
from pydantic import SecretStr
from starlette.applications import Starlette
from starlette.routing import Route

from jev_plugin.config import Settings
from jev_plugin.mcp.http_app import create_http_app


def _create_test_server() -> MCPServer:
    """Create an isolated MCP server for transport tests."""
    return MCPServer(
        name="test-server",
        version="1.0.0",
    )


def _mcp_route(app: Starlette) -> Route:
    """Return the /mcp route from a Starlette application."""
    for route in app.routes:
        if isinstance(route, Route) and route.path == "/mcp":
            return route

    raise AssertionError("The MCP /mcp route was not registered.")


def _route_paths(app: Starlette) -> list[str]:
    """Return paths exposed directly by the Starlette application."""
    paths: list[str] = []

    for route in app.routes:
        path = getattr(route, "path", None)

        if isinstance(path, str):
            paths.append(path)

    return paths


@pytest.fixture
def anyio_backend() -> str:
    """Run ASGI transport tests with asyncio."""
    return "asyncio"


def test_create_http_app_returns_starlette_application() -> None:
    """create_http_app() should return a Starlette ASGI application."""
    server = _create_test_server()

    app = create_http_app(server)

    assert isinstance(app, Starlette)


def test_create_http_app_registers_mcp_endpoint() -> None:
    """The generated application should expose the /mcp endpoint."""
    server = _create_test_server()

    app = create_http_app(server)

    assert "/mcp" in _route_paths(app)


def test_create_http_app_uses_injected_server() -> None:
    """The factory should build the application from the supplied MCP server."""
    server = MCPServer(
        name="injected-server",
        version="2.0.0",
    )

    app = create_http_app(server)

    assert isinstance(app, Starlette)
    assert "/mcp" in _route_paths(app)


def test_create_http_app_contains_only_mcp_route() -> None:
    """The transport adapter should not add unrelated HTTP routes."""
    server = _create_test_server()

    app = create_http_app(server)

    assert _route_paths(app) == ["/mcp"]


def test_mcp_route_is_starlette_route() -> None:
    """The /mcp endpoint should be represented by a Starlette Route."""
    server = _create_test_server()

    app = create_http_app(server)

    route = _mcp_route(app)

    assert isinstance(route, Route)
    assert route.path == "/mcp"


def test_mcp_route_uses_streamable_http_handler() -> None:
    """The /mcp route should delegate to the MCP Streamable HTTP handler."""
    server = _create_test_server()

    app = create_http_app(server)

    route = _mcp_route(app)

    assert route.name == "StreamableHTTPASGIApp"
    assert callable(route.endpoint)


def test_mcp_route_does_not_depend_on_starlette_method_metadata() -> None:
    """Transport method dispatch should remain owned by the MCP SDK."""
    server = _create_test_server()

    app = create_http_app(server)

    route = _mcp_route(app)

    # StreamableHTTPASGIApp is itself the ASGI endpoint responsible for
    # Streamable HTTP method handling. The current MCP SDK deliberately
    # does not expose GET/POST/DELETE through Starlette's Route.methods.
    #
    # We therefore verify only that the route delegates to the transport
    # handler rather than asserting on Starlette's internal method metadata.
    assert callable(route.endpoint)


def test_create_http_app_preserves_mcp_lifespan() -> None:
    """The generated application should include the MCP session lifespan."""
    server = _create_test_server()

    app = create_http_app(server)

    assert app.router.lifespan_context is not None


def test_create_http_app_accepts_multiple_server_instances() -> None:
    """The factory should work with independent MCPServer instances."""
    servers = (
        MCPServer(
            name="server-one",
            version="1.0.0",
        ),
        MCPServer(
            name="server-two",
            version="2.0.0",
        ),
        MCPServer(
            name="server-three",
            version="3.0.0",
        ),
    )

    for server in servers:
        app = create_http_app(server)

        assert isinstance(app, Starlette)
        assert _route_paths(app) == ["/mcp"]


@pytest.mark.anyio
async def test_create_http_app_rejects_unapproved_host() -> None:
    """Transport security should reject a Host header outside its allowlist."""
    app = create_http_app(
        _create_test_server(),
        settings=Settings(
            typesafe_api_key=SecretStr("test-api-key"),
            mcp_allowed_hosts=["allowed.test"],
            mcp_allowed_origins=["https://allowed.test"],
        ),
    )
    transport = httpx2.ASGITransport(app=app)

    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="http://unapproved.test",
        ) as client:
            response = await client.get("/mcp")

    assert response.status_code == 421


@pytest.mark.anyio
async def test_create_http_app_rejects_unapproved_origin() -> None:
    """Transport security should reject an Origin outside its allowlist."""
    app = create_http_app(
        _create_test_server(),
        settings=Settings(
            typesafe_api_key=SecretStr("test-api-key"),
            mcp_allowed_hosts=["allowed.test"],
            mcp_allowed_origins=["https://allowed.test"],
        ),
    )
    transport = httpx2.ASGITransport(app=app)

    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="http://allowed.test",
        ) as client:
            response = await client.get(
                "/mcp",
                headers={"Origin": "https://unapproved.test"},
            )

    assert response.status_code == 403

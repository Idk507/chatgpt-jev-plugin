
"""Unit tests for the Jev MCP health-check endpoint."""

from __future__ import annotations

import httpx2
import pytest
from mcp.server import MCPServer
from starlette.applications import Starlette
from starlette.routing import Route

from jev_plugin.mcp.health import HEALTH_PATH, register_health_route


BASE_URL = "http://127.0.0.1:8000"


def _create_server() -> MCPServer:
    """Create an isolated MCP server for health-route tests."""
    return MCPServer(
        name="health-test-server",
        version="1.0.0",
    )


def _health_route(app: Starlette) -> Route:
    """Return the registered health route."""
    for route in app.routes:
        if isinstance(route, Route) and route.path == HEALTH_PATH:
            return route

    raise AssertionError(
        f"The {HEALTH_PATH} health route was not registered."
    )


def test_health_path_constant() -> None:
    """The health endpoint should use the expected path."""
    assert HEALTH_PATH == "/health"


def test_register_health_route_adds_health_endpoint() -> None:
    """Registering the health route should add /health to the MCP app."""
    server = _create_server()

    register_health_route(server)

    app = server.streamable_http_app()

    paths = [
        route.path
        for route in app.routes
        if isinstance(route, Route)
    ]

    assert "/mcp" in paths
    assert HEALTH_PATH in paths


def test_health_route_is_a_starlette_route() -> None:
    """The health endpoint should be represented by a Starlette Route."""
    server = _create_server()

    register_health_route(server)

    app = server.streamable_http_app()

    route = _health_route(app)

    assert isinstance(route, Route)
    assert route.path == HEALTH_PATH
    assert callable(route.endpoint)


def test_health_route_allows_get_and_head() -> None:
    """The health endpoint should expose GET and Starlette's automatic HEAD."""
    server = _create_server()

    register_health_route(server)

    app = server.streamable_http_app()

    route = _health_route(app)

    assert route.methods == {"GET", "HEAD"}


@pytest.mark.anyio
async def test_health_endpoint_returns_ok_response() -> None:
    """GET /health should return HTTP 200 and the expected JSON body."""
    server = _create_server()

    register_health_route(server)

    app = server.streamable_http_app()

    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)

        async with httpx2.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as client:
            response = await client.get(HEALTH_PATH)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["content-type"].startswith(
        "application/json"
    )


@pytest.mark.anyio
async def test_health_endpoint_supports_head() -> None:
    """HEAD /health should be handled automatically by Starlette."""
    server = _create_server()

    register_health_route(server)

    app = server.streamable_http_app()

    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)

        async with httpx2.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as client:
            response = await client.head(HEALTH_PATH)

    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.anyio
async def test_health_endpoint_rejects_post() -> None:
    """POST /health should not be accepted by the liveness endpoint."""
    server = _create_server()

    register_health_route(server)

    app = server.streamable_http_app()

    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)

        async with httpx2.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as client:
            response = await client.post(HEALTH_PATH)

    assert response.status_code == 405


@pytest.mark.anyio
async def test_health_endpoint_does_not_require_request_body() -> None:
    """GET /health should work without a request body."""
    server = _create_server()

    register_health_route(server)

    app = server.streamable_http_app()

    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)

        async with httpx2.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as client:
            response = await client.get(HEALTH_PATH)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_health_endpoint_is_independent_of_mcp_tool_execution() -> None:
    """The health endpoint should not require Jev tool execution."""
    server = _create_server()

    register_health_route(server)

    app = server.streamable_http_app()

    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)

        async with httpx2.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as client:
            response = await client.get(HEALTH_PATH)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

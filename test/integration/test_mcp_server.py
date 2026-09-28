"""Integration tests for the production Jev MCP server composition."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server import MCPServer

from jev_plugin.jev import NoulResult
from jev_plugin.mcp.dependencies import JevDependencies
from jev_plugin.mcp.http_app import create_http_app
from jev_plugin.mcp.server import create_mcp_server


BASE_URL = "http://127.0.0.1:8000"
MCP_URL = f"{BASE_URL}/mcp"
HEALTH_URL = f"{BASE_URL}/health"


class FakeJevClient:
    """Deterministic JevClient replacement for integration tests."""

    def __init__(self) -> None:
        self.is_closed = False
        self.close_calls = 0

    def close(self) -> None:
        """Close the fake client idempotently."""
        if self.is_closed:
            return

        self.close_calls += 1
        self.is_closed = True


class FakeJevService:
    """Deterministic Jev service used by the production composition tests."""

    def __init__(
        self,
        *,
        result: NoulResult | None = None,
    ) -> None:
        self.result = result or NoulResult(probability=0.91)
        self.calls: list[dict[str, Any]] = []

    def evaluate_noul(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        criteria: dict[str, Any] | None = None,
    ) -> NoulResult:
        """Record the request and return the configured result."""
        self.calls.append(
            {
                "state": state,
                "question": question,
                "criteria": criteria,
            }
        )

        return self.result


@pytest.fixture
def anyio_backend() -> str:
    """Run integration tests with asyncio."""
    return "asyncio"


@pytest.fixture
def fake_client() -> FakeJevClient:
    """Provide a deterministic fake Jev client."""
    return FakeJevClient()


@pytest.fixture
def fake_service() -> FakeJevService:
    """Provide a deterministic fake Jev service."""
    return FakeJevService()


@pytest.fixture
def dependencies(
    fake_client: FakeJevClient,
    fake_service: FakeJevService,
) -> JevDependencies:
    """Compose deterministic application dependencies."""
    return JevDependencies(
        client=fake_client,  # type: ignore[arg-type]
        service=fake_service,  # type: ignore[arg-type]
    )


@pytest.fixture
def production_server(
    dependencies: JevDependencies,
    monkeypatch: pytest.MonkeyPatch,
) -> MCPServer[Any]:
    """Create the real production MCP server with fake dependencies."""

    @asynccontextmanager
    async def test_lifespan(
        _server: MCPServer[Any],
    ) -> AsyncIterator[JevDependencies]:
        """Provide deterministic dependencies during the server lifetime."""
        try:
            yield dependencies
        finally:
            dependencies.close()

    # create_mcp_server() uses the symbol imported into
    # jev_plugin.mcp.server, so that is the reference that must be patched.
    monkeypatch.setattr(
        "jev_plugin.mcp.server.jev_server_lifespan",
        test_lifespan,
    )

    return create_mcp_server()


@pytest.fixture
def production_app(
    production_server: MCPServer[Any],
) -> Any:
    """Create the real production Streamable HTTP application."""
    return create_http_app(production_server)


@pytest.mark.anyio
async def test_production_server_exposes_all_jev_tools(
    production_app: Any,
) -> None:
    """The production MCP server should expose all supported Jev tools."""
    async with production_app.router.lifespan_context(production_app):
        transport = httpx2.ASGITransport(app=production_app)

        async with httpx2.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as http_client:
            async with Client(
                streamable_http_client(
                    MCP_URL,
                    http_client=http_client,
                )
            ) as client:
                result = await client.list_tools()

    assert [tool.name for tool in result.tools] == [
        "jev_noul",
        "jev_choice",
        "jev_score",
    ]


@pytest.mark.anyio
async def test_production_app_contains_mcp_and_health_routes(
    production_app: Any,
) -> None:
    """The production HTTP app should expose /mcp and /health."""
    paths = [
        getattr(route, "path", None)
        for route in production_app.routes
    ]

    assert "/mcp" in paths
    assert HEALTH_URL.replace(BASE_URL, "") in paths
    assert len(paths) == 2


@pytest.mark.anyio
async def test_production_health_endpoint_returns_ok(
    production_app: Any,
) -> None:
    """GET /health should work through the production application."""
    async with production_app.router.lifespan_context(production_app):
        transport = httpx2.ASGITransport(app=production_app)

        async with httpx2.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["content-type"].startswith(
        "application/json"
    )


@pytest.mark.anyio
async def test_production_health_endpoint_rejects_post(
    production_app: Any,
) -> None:
    """POST /health should not be accepted."""
    async with production_app.router.lifespan_context(production_app):
        transport = httpx2.ASGITransport(app=production_app)

        async with httpx2.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as client:
            response = await client.post("/health")

    assert response.status_code == 405


@pytest.mark.anyio
async def test_production_server_calls_noul_through_http(
    production_app: Any,
    fake_service: FakeJevService,
) -> None:
    """The production composition should execute Noul over Streamable HTTP."""
    state = {
        "production_process": "assembly",
        "connection_type": "screwing",
    }
    question = "Is screwing the required production connection type?"
    criteria = {
        "required": True,
        "domain": "production",
    }

    async with production_app.router.lifespan_context(production_app):
        transport = httpx2.ASGITransport(app=production_app)

        async with httpx2.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as http_client:
            async with Client(
                streamable_http_client(
                    MCP_URL,
                    http_client=http_client,
                )
            ) as client:
                result = await client.call_tool(
                    "jev_noul",
                    {
                        "state": state,
                        "question": question,
                        "criteria": criteria,
                    },
                )

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["probability"] == pytest.approx(
        0.91
    )

    assert fake_service.calls == [
        {
            "state": state,
            "question": question,
            "criteria": criteria,
        }
    ]


@pytest.mark.anyio
async def test_production_dependencies_are_closed_after_application_lifespan(
    production_app: Any,
    fake_client: FakeJevClient,
) -> None:
    """The production Jev dependencies should close after the lifespan."""
    assert fake_client.is_closed is False
    assert fake_client.close_calls == 0

    async with production_app.router.lifespan_context(production_app):
        assert fake_client.is_closed is False
        assert fake_client.close_calls == 0

        transport = httpx2.ASGITransport(app=production_app)

        async with httpx2.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as client:
            response = await client.get("/health")

            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

        # The dependencies must remain alive while the server lifespan
        # is still active.
        assert fake_client.is_closed is False
        assert fake_client.close_calls == 0

    # The production MCP server lifespan must close the application
    # dependencies when the lifespan exits.
    assert fake_client.is_closed is True
    assert fake_client.close_calls == 1

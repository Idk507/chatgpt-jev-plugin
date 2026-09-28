"""Integration tests for the Jev Streamable HTTP MCP application."""

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
from jev_plugin.mcp.jev_tools import register_noul_tool


BASE_URL = "http://127.0.0.1:8000"
MCP_URL = f"{BASE_URL}/mcp"


class FakeJevClient:
    """Deterministic JevClient replacement for lifecycle tests."""

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
    """Deterministic Jev service used by HTTP integration tests."""

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
    """Use asyncio for AnyIO-based integration tests."""
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
def mcp_server(
    dependencies: JevDependencies,
) -> MCPServer[Any]:
    """Create an isolated MCP server with the production Noul tool."""

    @asynccontextmanager
    async def lifespan(
        _server: MCPServer[Any],
    ) -> AsyncIterator[JevDependencies]:
        """Provide and clean up deterministic Jev dependencies."""
        try:
            yield dependencies
        finally:
            dependencies.close()

    server = MCPServer(
        name="jev-http-integration-test",
        version="1.0.0",
        instructions=(
            "Test MCP server for the Jev Streamable HTTP integration."
        ),
        lifespan=lifespan,
    )

    register_noul_tool(server)

    return server


@pytest.fixture
def app(
    mcp_server: MCPServer[Any],
):
    """Create the Streamable HTTP application under test."""
    return create_http_app(mcp_server)


@pytest.mark.anyio
async def test_streamable_http_initialize_and_list_tools(
    app: Any,
) -> None:
    """Initialize a real MCP client over HTTP and list the available tools."""
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)

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

    assert [tool.name for tool in result.tools] == ["jev_noul"]


@pytest.mark.anyio
async def test_streamable_http_calls_noul_tool(
    app: Any,
    fake_service: FakeJevService,
) -> None:
    """Execute the production Noul MCP tool through Streamable HTTP."""
    state = {
        "production_process": "assembly",
        "connection_type": "screwing",
    }
    question = "Is screwing the required production connection type?"
    criteria = {
        "required": True,
        "domain": "production",
    }

    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)

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
    assert result.structured_content["probability"] == pytest.approx(0.91)

    assert fake_service.calls == [
        {
            "state": state,
            "question": question,
            "criteria": criteria,
        }
    ]


@pytest.mark.anyio
async def test_streamable_http_preserves_list_state(
    app: Any,
    fake_service: FakeJevService,
) -> None:
    """Streamable HTTP should preserve list-valued state."""
    state = [
        "glue key part",
        "screw key part",
        "clip key part",
    ]

    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)

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
                        "question": "Is screw key part present?",
                    },
                )

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["probability"] == pytest.approx(0.91)

    assert len(fake_service.calls) == 1
    assert fake_service.calls[0]["state"] == state
    assert fake_service.calls[0]["question"] == (
        "Is screw key part present?"
    )
    assert fake_service.calls[0]["criteria"] is None


@pytest.mark.anyio
async def test_streamable_http_reuses_application_for_multiple_clients(
    app: Any,
    fake_service: FakeJevService,
) -> None:
    """Multiple MCP client sessions should work on one HTTP application."""
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)

        async with httpx2.AsyncClient(
            transport=transport,
            base_url=BASE_URL,
        ) as http_client:
            async with Client(
                streamable_http_client(
                    MCP_URL,
                    http_client=http_client,
                )
            ) as first_client:
                first_result = await first_client.call_tool(
                    "jev_noul",
                    {
                        "state": "first-state",
                        "question": "First request?",
                    },
                )

            async with Client(
                streamable_http_client(
                    MCP_URL,
                    http_client=http_client,
                )
            ) as second_client:
                second_result = await second_client.call_tool(
                    "jev_noul",
                    {
                        "state": "second-state",
                        "question": "Second request?",
                    },
                )

    assert first_result.is_error is False
    assert second_result.is_error is False

    assert first_result.structured_content is not None
    assert second_result.structured_content is not None

    assert first_result.structured_content["probability"] == pytest.approx(
        0.91
    )
    assert second_result.structured_content["probability"] == pytest.approx(
        0.91
    )

    assert len(fake_service.calls) == 2
    assert fake_service.calls[0]["state"] == "first-state"
    assert fake_service.calls[1]["state"] == "second-state"


@pytest.mark.anyio
async def test_streamable_http_closes_dependencies_after_lifespan(
    app: Any,
    fake_client: FakeJevClient,
) -> None:
    """Leaving the application lifespan should close Jev dependencies."""
    assert fake_client.is_closed is False
    assert fake_client.close_calls == 0

    async with app.router.lifespan_context(app):
        assert fake_client.is_closed is False
        assert fake_client.close_calls == 0

        transport = httpx2.ASGITransport(app=app)

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

                assert [tool.name for tool in result.tools] == ["jev_noul"]

        assert fake_client.is_closed is False
        assert fake_client.close_calls == 0

    assert fake_client.is_closed is True
    assert fake_client.close_calls == 1

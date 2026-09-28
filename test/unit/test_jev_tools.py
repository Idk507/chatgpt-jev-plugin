"""Unit tests for the TypeSafe Jev MCP tool adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from mcp import Client
from mcp.server import MCPServer

from jev_plugin.jev import ChoiceResult, NoulResult, ScoreResult
from jev_plugin.mcp.dependencies import JevDependencies
from jev_plugin.mcp.jev_tools import (
    register_choice_tool,
    register_jev_tools,
    register_noul_tool,
    register_score_tool,
)


class FakeJevClient:
    """Deterministic JevClient replacement for MCP tool tests."""

    def __init__(self) -> None:
        self.is_closed = False

    def close(self) -> None:
        """Close the fake client."""
        self.is_closed = True


class FakeJevService:
    """Deterministic JevService replacement for MCP tool tests."""

    def __init__(
        self,
        *,
        noul_result: NoulResult | None = None,
        choice_result: ChoiceResult | None = None,
        score_result: ScoreResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.noul_result = noul_result or NoulResult(probability=0.91)
        self.choice_result = choice_result or ChoiceResult(
            choice="screw",
            confidence=0.88,
            probabilities={
                "glue": 0.07,
                "screw": 0.88,
                "clip": 0.05,
            },
        )
        self.score_result = score_result or ScoreResult(
            score=4.2,
            confidence=0.86,
            legend={
                1: "Very poor",
                2: "Poor",
                3: "Acceptable",
                4: "Good",
                5: "Excellent",
            },
            probabilities={
                1: 0.03,
                2: 0.07,
                3: 0.12,
                4: 0.58,
                5: 0.20,
            },
        )
        self.error = error

        self.noul_calls: list[dict[str, Any]] = []
        self.choice_calls: list[dict[str, Any]] = []
        self.score_calls: list[dict[str, Any]] = []

    def evaluate_noul(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        criteria: dict[str, Any] | None = None,
    ) -> NoulResult:
        """Record and evaluate a Noul request."""
        if self.error is not None:
            raise self.error

        self.noul_calls.append(
            {
                "state": state,
                "question": question,
                "criteria": criteria,
            }
        )

        return self.noul_result

    def evaluate_choice(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        criteria: dict[str, Any],
    ) -> ChoiceResult:
        """Record and evaluate a Choice request."""
        if self.error is not None:
            raise self.error

        self.choice_calls.append(
            {
                "state": state,
                "question": question,
                "criteria": criteria,
            }
        )

        return self.choice_result

    def evaluate_score(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        criteria: list[Any],
    ) -> ScoreResult:
        """Record and evaluate a Score request."""
        if self.error is not None:
            raise self.error

        self.score_calls.append(
            {
                "state": state,
                "question": question,
                "criteria": criteria,
            }
        )

        return self.score_result


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous MCP tests with asyncio."""
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
    """Build deterministic Jev dependencies."""
    return JevDependencies(
        client=fake_client,  # type: ignore[arg-type]
        service=fake_service,  # type: ignore[arg-type]
    )


def _create_server(
    *,
    dependencies: JevDependencies,
) -> MCPServer[Any]:
    """Create an isolated MCP server with deterministic dependencies."""

    @asynccontextmanager
    async def lifespan(
        _server: MCPServer[Any],
    ) -> AsyncIterator[JevDependencies]:
        """Provide dependencies through the MCP server lifespan."""
        try:
            yield dependencies
        finally:
            dependencies.close()

    return MCPServer(
        name="jev-tools-test-server",
        version="1.0.0",
        lifespan=lifespan,
    )


async def _list_tools(
    server: MCPServer[Any],
) -> list[Any]:
    """List tools through the public MCP client interface."""
    async with Client(server) as client:
        result = await client.list_tools()

    return result.tools


def test_register_noul_tool() -> None:
    """Noul registration should add exactly the Noul tool."""
    server = MCPServer(
        name="test-server",
        version="1.0.0",
    )

    register_noul_tool(server)

    tools = server._tool_manager.list_tools()

    assert [tool.name for tool in tools] == ["jev_noul"]


def test_register_choice_tool() -> None:
    """Choice registration should add exactly the Choice tool."""
    server = MCPServer(
        name="test-server",
        version="1.0.0",
    )

    register_choice_tool(server)

    tools = server._tool_manager.list_tools()

    assert [tool.name for tool in tools] == ["jev_choice"]


def test_register_score_tool() -> None:
    """Score registration should add exactly the Score tool."""
    server = MCPServer(
        name="test-server",
        version="1.0.0",
    )

    register_score_tool(server)

    tools = server._tool_manager.list_tools()

    assert [tool.name for tool in tools] == ["jev_score"]


def test_register_jev_tools_registers_all_supported_tools() -> None:
    """The composition helper should register all supported Jev tools."""
    server = MCPServer(
        name="test-server",
        version="1.0.0",
    )

    register_jev_tools(server)

    tools = server._tool_manager.list_tools()

    assert [tool.name for tool in tools] == [
        "jev_noul",
        "jev_choice",
        "jev_score",
    ]


@pytest.mark.anyio
async def test_noul_tool_metadata(
    dependencies: JevDependencies,
) -> None:
    """Noul should expose its metadata, schemas, and annotations."""
    server = _create_server(dependencies=dependencies)

    register_noul_tool(server)

    tools = await _list_tools(server)

    assert len(tools) == 1

    tool = tools[0]

    assert tool.name == "jev_noul"
    assert tool.title == "Evaluate Jev Noul"
    assert tool.description is not None
    assert "proactively for a binary decision" in tool.description

    assert tool.input_schema is not None
    assert tool.output_schema is not None

    annotations = tool.annotations

    assert annotations is not None
    assert annotations.read_only_hint is True
    assert annotations.destructive_hint is False
    assert annotations.idempotent_hint is True
    assert annotations.open_world_hint is False

    properties = tool.input_schema["properties"]

    assert "state" in properties
    assert "question" in properties
    assert "criteria" in properties

    assert (
        properties["state"]["description"]
        == "State or context against which the proposition should be evaluated."
    )
    assert (
        properties["question"]["description"]
        == "A yes/no proposition to evaluate against the state."
    )
    assert (
        properties["criteria"]["description"]
        == (
            "Optional evaluation criteria that provide additional "
            "context for the proposition."
        )
    )

    assert "probability" in tool.output_schema["properties"]


@pytest.mark.anyio
async def test_choice_tool_metadata(
    dependencies: JevDependencies,
) -> None:
    """Choice should expose its metadata, schemas, and annotations."""
    server = _create_server(dependencies=dependencies)

    register_choice_tool(server)

    tools = await _list_tools(server)

    assert len(tools) == 1

    tool = tools[0]

    assert tool.name == "jev_choice"
    assert tool.title == "Evaluate Jev Choice"
    assert tool.description is not None
    assert "proactively when a request requires choosing" in tool.description

    assert tool.input_schema is not None
    assert tool.output_schema is not None

    annotations = tool.annotations

    assert annotations is not None
    assert annotations.read_only_hint is True
    assert annotations.destructive_hint is False
    assert annotations.idempotent_hint is True
    assert annotations.open_world_hint is False

    properties = tool.input_schema["properties"]

    assert "state" in properties
    assert "question" in properties
    assert "criteria" in properties

    assert (
        properties["state"]["description"]
        == (
            "State or context from which the most appropriate "
            "choice should be determined."
        )
    )
    assert (
        properties["question"]["description"]
        == (
            "Question asking which named alternative best fits "
            "the supplied state."
        )
    )
    assert (
        properties["criteria"]["description"]
        == (
            "Mapping of at least two named choices to their "
            "definitions or evaluation criteria."
        )
    )

    assert "choice" in tool.output_schema["properties"]
    assert "confidence" in tool.output_schema["properties"]
    assert "probabilities" in tool.output_schema["properties"]


@pytest.mark.anyio
async def test_score_tool_metadata(
    dependencies: JevDependencies,
) -> None:
    """Score should expose its metadata, schemas, and annotations."""
    server = _create_server(dependencies=dependencies)

    register_score_tool(server)

    tools = await _list_tools(server)

    assert len(tools) == 1

    tool = tools[0]

    assert tool.name == "jev_score"
    assert tool.title == "Evaluate Jev Score"
    assert tool.description is not None
    assert "proactively when a request requires a grounded assessment" in tool.description

    assert tool.input_schema is not None
    assert tool.output_schema is not None

    annotations = tool.annotations

    assert annotations is not None
    assert annotations.read_only_hint is True
    assert annotations.destructive_hint is False
    assert annotations.idempotent_hint is True
    assert annotations.open_world_hint is False

    properties = tool.input_schema["properties"]

    assert "state" in properties
    assert "question" in properties
    assert "criteria" in properties

    assert (
        properties["state"]["description"]
        == (
            "State or context that should be evaluated against "
            "the ordered scoring criteria."
        )
    )
    assert (
        properties["question"]["description"]
        == "Question describing what should be scored."
    )
    assert (
        properties["criteria"]["description"]
        == (
            "Ordered list containing at least two scoring "
            "criteria or score levels."
        )
    )

    assert "score" in tool.output_schema["properties"]
    assert "confidence" in tool.output_schema["properties"]
    assert "legend" in tool.output_schema["properties"]
    assert "probabilities" in tool.output_schema["properties"]


@pytest.mark.anyio
async def test_all_jev_tools_have_consistent_safety_annotations(
    dependencies: JevDependencies,
) -> None:
    """All Jev evaluation tools should advertise the same safety contract."""
    server = _create_server(dependencies=dependencies)

    register_jev_tools(server)

    tools = await _list_tools(server)

    assert len(tools) == 3

    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.idempotent_hint is True
        assert tool.annotations.open_world_hint is False

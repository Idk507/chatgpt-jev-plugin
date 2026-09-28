"""Unit tests for the production Jev MCP server."""

from __future__ import annotations

import pytest
from mcp import Client

from jev_plugin import __version__
from jev_plugin.config import get_settings
from jev_plugin.mcp.server import create_mcp_server, mcp


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio for AnyIO-based MCP tests."""
    return "asyncio"


@pytest.fixture
def client() -> Client:
    """Return an MCP client connected to the production MCP server."""
    return Client(mcp)


@pytest.mark.anyio
async def test_mcp_server_handshake(client: Client) -> None:
    """The production MCP server should negotiate an MCP protocol version."""
    async with client:
        assert client.protocol_version
        assert client.server_info is not None


@pytest.mark.anyio
async def test_mcp_server_identity(client: Client) -> None:
    """The connected MCP client should expose the production server identity."""
    async with client:
        assert client.server_info is not None
        assert client.server_info.name == get_settings().app_name
        assert client.server_info.version == __version__


@pytest.mark.anyio
async def test_mcp_server_description(client: Client) -> None:
    """The production MCP server description should be exposed in server_info."""
    async with client:
        assert client.server_info is not None
        assert (
            client.server_info.description
            == "Decision-evaluation MCP server exposing TypeSafe Jev "
            "for grounded classification, selection, and scoring."
        )


@pytest.mark.anyio
async def test_mcp_server_instructions(client: Client) -> None:
    """The server instructions should be exposed to the MCP client."""
    async with client:
        assert client.instructions is not None

        assert (
            client.instructions
            == "Proactively use Jev when a response requires a judgment grounded "
            "in supplied state: use jev_noul for binary decisions, eligibility, "
            "verification, or classification; use jev_choice to select from "
            "named alternatives; and use jev_score to assess against an ordered "
            "rubric. Use supplied or unambiguously extractable state and criteria; "
            "ask a focused question rather than inventing missing policy, options, "
            "or rubric levels. For Choice, include an other/no-match option when "
            "the supplied alternatives may be incomplete. Treat Noul as the "
            "probability of yes, not a confidence or severity scale. Do not use Jev "
            "for simple factual recall, creative writing, or open-ended advice "
            "without defined decision criteria. Do not claim a Jev evaluation "
            "occurred unless the corresponding tool was called. After each Jev "
            "call, include a compact 'Jev evaluation trace' in the final response "
            "with the exact tool name, evaluated question, and raw typed result "
            "fields. Keep the tool result separate from the model's own rationale "
            "and do not repeat sensitive state unnecessarily."
        )


@pytest.mark.anyio
async def test_mcp_server_has_tools_capability(
    client: Client,
) -> None:
    """The production MCP server should advertise the tools capability."""
    async with client:
        assert client.server_capabilities.tools is not None


@pytest.mark.anyio
async def test_mcp_server_has_all_jev_tools_registered(
    client: Client,
) -> None:
    """The production server should expose all supported Jev MCP tools."""
    async with client:
        result = await client.list_tools()

    assert len(result.tools) == 3

    assert [tool.name for tool in result.tools] == [
        "jev_noul",
        "jev_choice",
        "jev_score",
    ]


@pytest.mark.anyio
async def test_mcp_server_tool_metadata(
    client: Client,
) -> None:
    """The production Jev tools should expose the expected metadata."""
    async with client:
        result = await client.list_tools()

    tools = {tool.name: tool for tool in result.tools}

    assert tools["jev_noul"].title == "Evaluate Jev Noul"
    assert tools["jev_choice"].title == "Evaluate Jev Choice"
    assert tools["jev_score"].title == "Evaluate Jev Score"

    assert "TypeSafe Jev" in tools["jev_noul"].description
    assert "TypeSafe Jev" in tools["jev_choice"].description
    assert "TypeSafe Jev" in tools["jev_score"].description


@pytest.mark.anyio
async def test_mcp_server_metadata_matches_application_configuration(
    client: Client,
) -> None:
    """The MCP metadata should match the application configuration."""
    settings = get_settings()

    async with client:
        assert client.server_info is not None
        assert client.server_info.name == settings.app_name
        assert client.server_info.version == __version__
        assert (
            client.server_info.description
            == "Decision-evaluation MCP server exposing TypeSafe Jev "
            "for grounded classification, selection, and scoring."
        )


def test_mcp_server_is_importable() -> None:
    """The production MCP server module should be importable."""
    assert mcp is not None


def test_mcp_server_factory_returns_configured_server() -> None:
    """The server factory should return a configured MCPServer."""
    server = create_mcp_server()

    assert server is not None

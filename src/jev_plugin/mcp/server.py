"""Production MCP server definition for the Jev ChatGPT plugin.

This module owns the MCP server composition.

Responsibilities:
- Create the application-owned MCPServer instance.
- Configure server metadata.
- Attach the application lifespan.
- Register all supported Jev MCP tools.
- Register non-MCP HTTP routes such as the health endpoint.
- Expose the module-level ``mcp`` object used by MCP tooling and ASGI hosting.

Transport-specific HTTP application construction is intentionally kept in
``jev_plugin.mcp.http_app``.
"""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from jev_plugin import __version__
from jev_plugin.config import get_settings
from jev_plugin.mcp.health import register_health_route
from jev_plugin.mcp.jev_tools import register_jev_tools
from jev_plugin.mcp.lifespan import jev_server_lifespan


def create_mcp_server() -> MCPServer[Any]:
    """Create and configure the production MCP server.

    Returns:
        A fully configured MCPServer instance.

    Notes:
        This function creates the server but does not start a transport.

        The returned server can be used with:
        - the local stdio transport, or
        - the Streamable HTTP ASGI application.
    """
    settings = get_settings()

    server = MCPServer(
        name=settings.app_name,
        version=__version__,
        description=(
            "Decision-evaluation MCP server exposing TypeSafe Jev "
            "for grounded classification, selection, and scoring."
        ),
        instructions=(
            "Proactively use Jev when a response requires a judgment grounded "
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
        ),
        log_level=settings.mcp_log_level,
        lifespan=jev_server_lifespan,
    )

    register_jev_tools(server)
    register_health_route(server)

    return server


mcp = create_mcp_server()


def main() -> None:
    """Run the MCP server using the stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()


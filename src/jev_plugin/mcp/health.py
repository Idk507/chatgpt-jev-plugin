"""Health-check endpoint for the Jev MCP server.

This module provides a lightweight HTTP liveness endpoint for deployment
platforms, load balancers, and container orchestrators.

The endpoint is intentionally independent of Jev application dependencies.
A liveness check should answer whether the HTTP/MCP process is alive without
performing an external TypeSafe API request.

The MCP SDK exposes custom HTTP routes through ``MCPServer.custom_route()``.
When ``streamable_http_app()`` is created, the SDK includes this route in the
resulting Starlette application.
"""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse


HEALTH_PATH = "/health"


def register_health_route(server: MCPServer[Any]) -> None:
    """Register the HTTP health-check endpoint on an MCP server.

    Args:
        server:
            MCP server that should expose the health endpoint.

    Returns:
        None.

    Notes:
        The endpoint is deliberately unauthenticated and contains no
        sensitive application state. This follows the MCP SDK's intended
        use of custom routes for health checks.
    """

    @server.custom_route(
        HEALTH_PATH,
        methods=["GET"],
    )
    async def health_check(_request: Request) -> JSONResponse:
        """Return the current process liveness status."""
        return JSONResponse(
            {
                "status": "ok",
            },
            status_code=200,
        )

"""ASGI application for the Jev MCP server.

This module adapts the application-owned MCPServer to the official
MCP Streamable HTTP transport.

The responsibilities are intentionally limited to:

1. Selecting the production MCPServer instance.
2. Creating the official Streamable HTTP Starlette application.
3. Exposing that application as ``app`` for an ASGI server.

The MCP SDK owns the transport route and Streamable HTTP session-manager
lifespan. This module must not recreate either of them.
"""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from jev_plugin.config import Settings, get_settings
from jev_plugin.mcp.server import mcp


def create_http_app(
    server: MCPServer | None = None,
    *,
    settings: Settings | None = None,
) -> Starlette:
    """Create the Streamable HTTP ASGI application.

    Args:
        server:
            Optional MCPServer instance.

            When omitted, the production MCP server from
            ``jev_plugin.mcp.server`` is used.

            Dependency injection is supported so transport-level tests
            can provide an isolated MCPServer instance without replacing
            the production server.

        settings:
            Optional application configuration. The Streamable HTTP
            allowlists are read from this object when provided; otherwise,
            the process-wide settings are used.

    Returns:
        The Starlette ASGI application created by the official MCP SDK.

    Notes:
        ``streamable_http_app()`` is intentionally used directly.

        The MCP SDK is responsible for:
        - registering the ``/mcp`` endpoint,
        - constructing the Streamable HTTP transport,
        - managing MCP sessions,
        - and attaching the session-manager lifespan.

        We therefore do not manually add Starlette routes or another
        lifespan in this module.
    """
    resolved_server = server if server is not None else mcp
    resolved_settings = settings if settings is not None else get_settings()
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=resolved_settings.mcp_allowed_hosts,
        allowed_origins=resolved_settings.mcp_allowed_origins,
    )

    return resolved_server.streamable_http_app(
        streamable_http_path="/mcp",
        transport_security=transport_security,
    )


# ASGI application entrypoint.
#
# This allows an ASGI server to launch the MCP application directly:
#
#     uvicorn jev_plugin.mcp.http_app:app
#
app = create_http_app()

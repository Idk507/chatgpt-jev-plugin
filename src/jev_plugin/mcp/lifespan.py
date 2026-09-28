
"""MCP server lifespan management for Jev application dependencies.

This module owns the lifecycle boundary between the MCP server and the
application's Jev dependencies.

Lifecycle:

    MCP Server startup
          |
          v
    create_jev_dependencies()
          |
          v
    JevDependencies
          |
          v
    yield to MCP server
          |
          v
    MCP Server shutdown
          |
          v
    JevDependencies.close()

The TypeSafe client is therefore created as part of server startup rather
than during module import.

The yielded ``JevDependencies`` object becomes available as MCP lifespan
context state. The MCP Python SDK exposes that state through the request
context for tools and other handlers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import MCPServer

from jev_plugin.mcp.dependencies import (
    JevDependencies,
    create_jev_dependencies,
)


@asynccontextmanager
async def jev_server_lifespan(
    _server: MCPServer[Any],
) -> AsyncIterator[JevDependencies]:
    """Create and release Jev dependencies for the MCP server lifecycle.

    The dependency container is created when the MCP server enters its
    lifespan and released when the lifespan exits.

    Args:
        _server:
            The MCP server instance entering the lifespan.

            The server object is currently not required for dependency
            composition, but it is part of the MCP SDK lifespan contract.

    Yields:
        The application-owned ``JevDependencies`` container.

    Raises:
        Exception:
            Any dependency initialization error is propagated to the MCP
            server startup sequence. A successfully created dependency
            container is always closed during teardown.
    """
    dependencies = create_jev_dependencies()

    try:
        yield dependencies
    finally:
        dependencies.close()

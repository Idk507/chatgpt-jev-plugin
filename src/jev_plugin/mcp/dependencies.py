"""Application dependency composition for the Jev MCP server.

This module is the composition boundary for Jev application components.

The dependency graph is:

    Settings
        |
        v
    JevClient
        |
        v
    JevService

The MCP protocol layer should not construct the Jev client or service
directly. Instead, the server lifecycle will obtain an application-owned
``JevDependencies`` instance from this module.

This design gives us:

- One place where application dependencies are composed.
- Explicit ownership of the TypeSafe SDK client.
- Deterministic cleanup of external resources.
- Dependency injection for unit tests.
- A clean boundary between infrastructure, application services, and MCP.
- A natural integration point for MCP server lifespan management.
"""

from __future__ import annotations

from dataclasses import dataclass

from typesafe_sdk import TypeSafeClient

from jev_plugin.config import Settings, get_settings
from jev_plugin.jev import JevClient, JevService


@dataclass(slots=True)
class JevDependencies:
    """Application-owned Jev dependency container.

    ``JevDependencies`` owns the ``JevClient`` and the corresponding
    ``JevService`` built from that client.

    The MCP server will eventually use this object as its application
    lifecycle state.

    Attributes:
        client: Application adapter around the official TypeSafe SDK.
        service: Application-level Jev service.
    """

    client: JevClient
    service: JevService

    @classmethod
    def create(
        cls,
        *,
        settings: Settings | None = None,
        sdk_client: TypeSafeClient | None = None,
    ) -> JevDependencies:
        """Create the complete Jev dependency graph.

        Args:
            settings:
                Optional application settings. When omitted, the shared
                application settings instance is loaded through
                ``get_settings()``.

            sdk_client:
                Optional pre-created official TypeSafe SDK client.

                When supplied, ownership of that client is transferred to
                the resulting ``JevDependencies`` instance, which means
                ``close()`` will close it.

        Returns:
            A fully composed Jev dependency container.

        Raises:
            Exception:
                Any exception raised while constructing the Jev client or
                service is propagated after already-created resources are
                cleaned up.
        """
        resolved_settings = settings or get_settings()

        client = JevClient(
            settings=resolved_settings,
            sdk_client=sdk_client,
        )

        try:
            service = JevService(client)
        except Exception:
            client.close()
            raise

        return cls(
            client=client,
            service=service,
        )

    @property
    def is_closed(self) -> bool:
        """Return whether the underlying Jev client has been closed."""
        return self.client.is_closed

    def close(self) -> None:
        """Release all resources owned by this dependency container.

        The underlying ``JevClient.close()`` operation is idempotent, so
        calling this method multiple times is safe.
        """
        self.client.close()

    def __enter__(self) -> JevDependencies:
        """Enter a dependency-management context."""
        if self.is_closed:
            raise RuntimeError(
                "Cannot enter a closed Jev dependency container."
            )

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Release dependencies when leaving the context."""
        self.close()


def create_jev_dependencies(
    *,
    settings: Settings | None = None,
    sdk_client: TypeSafeClient | None = None,
) -> JevDependencies:
    """Create the application's Jev dependency container.

    This function is the public composition entry point used by higher
    application layers.

    Args:
        settings:
            Optional application settings. Defaults to ``get_settings()``.

        sdk_client:
            Optional injected TypeSafe SDK client for deterministic testing.

    Returns:
        A fully initialized ``JevDependencies`` instance.
    """
    return JevDependencies.create(
        settings=settings,
        sdk_client=sdk_client,
    )
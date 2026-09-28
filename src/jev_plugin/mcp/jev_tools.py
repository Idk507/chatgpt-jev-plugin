"""MCP tool adapters for TypeSafe Jev.

This module contains the thin protocol-layer adapters between MCP and the
application-owned JevService.

The module intentionally does not contain TypeSafe SDK construction logic.
That responsibility belongs to JevService.

Currently exposed Jev capabilities:

- ``jev_noul`` -> yes/no probability evaluation.
- ``jev_choice`` -> selection among named alternatives.
- ``jev_score`` -> evaluation against ordered score criteria.

The MCP Context is used to obtain application dependencies from the server
lifespan. This keeps the tool layer independent of global service instances
and makes the production lifecycle explicit.

All three tools are read-only evaluation operations. They do not mutate
external state, access an open-ended public world, or perform destructive
actions. Their MCP safety annotations therefore explicitly describe those
properties.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from jev_plugin.jev import ChoiceResult, NoulResult, ScoreResult
from jev_plugin.mcp.dependencies import JevDependencies


State = str | dict[str, Any] | list[Any]


def _read_only_annotations() -> ToolAnnotations:
    """Create the safety annotations for a Jev evaluation tool.

    Jev evaluation tools only compute results from supplied input. They do
    not mutate application or user state and do not interact with an
    open-ended public environment.

    A repeated invocation does not produce an additional external side
    effect, so the operation is idempotent from a state-change perspective.
    """
    return ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )


def _get_dependencies(
    ctx: Context[JevDependencies] | None,
) -> JevDependencies:
    """Return Jev dependencies from the current MCP request context.

    Args:
        ctx:
            MCP request context populated by the server runtime.

    Returns:
        The application dependency container associated with the request.

    Raises:
        RuntimeError:
            If the tool is invoked without an MCP request context or if the
            server lifespan contains an unexpected context object.
    """
    if ctx is None:
        raise RuntimeError(
            "MCP request context is required for the Jev tool."
        )

    dependencies = ctx.request_context.lifespan_context

    if not isinstance(dependencies, JevDependencies):
        raise RuntimeError(
            "MCP lifespan context does not contain Jev dependencies."
        )

    return dependencies


def register_noul_tool(server: MCPServer[Any]) -> None:
    """Register the Jev Noul MCP tool.

    Noul evaluates a yes/no proposition against supplied state and returns
    the probability that the proposition is true.

    Args:
        server:
            MCP server on which the tool should be registered.
    """

    def jev_noul(
        state: Annotated[
            State,
            Field(
                description=(
                    "State or context against which the proposition "
                    "should be evaluated."
                )
            ),
        ],
        question: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "A yes/no proposition to evaluate against the state."
                ),
            ),
        ],
        criteria: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    "Optional evaluation criteria that provide additional "
                    "context for the proposition."
                )
            ),
        ] = None,
        ctx: Context[JevDependencies] | None = None,
    ) -> NoulResult:
        """Evaluate a yes/no proposition with TypeSafe Jev."""
        dependencies = _get_dependencies(ctx)

        return dependencies.service.evaluate_noul(
            state=state,
            question=question,
            criteria=criteria,
        )

    server.add_tool(
        jev_noul,
        name="jev_noul",
        title="Evaluate Jev Noul",
        description=(
            "Use TypeSafe Jev proactively for a binary decision grounded in "
            "supplied state: eligibility, verification, yes/no classification, "
            "or whether a proposition is supported. Do not use for factual "
            "recall that needs no evaluation. Returns the probability that the "
            "proposition is true."
        ),
        annotations=_read_only_annotations(),
        structured_output=True,
    )


def register_choice_tool(server: MCPServer[Any]) -> None:
    """Register the Jev Choice MCP tool.

    Choice selects one option from a named collection of alternatives and
    returns the selected choice, confidence, and probability distribution.

    Args:
        server:
            MCP server on which the tool should be registered.
    """

    def jev_choice(
        state: Annotated[
            State,
            Field(
                description=(
                    "State or context from which the most appropriate "
                    "choice should be determined."
                )
            ),
        ],
        question: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "Question asking which named alternative best fits "
                    "the supplied state."
                ),
            ),
        ],
        criteria: Annotated[
            dict[str, Any],
            Field(
                min_length=2,
                description=(
                    "Mapping of at least two named choices to their "
                    "definitions or evaluation criteria."
                ),
            ),
        ],
        ctx: Context[JevDependencies] | None = None,
    ) -> ChoiceResult:
        """Select the most appropriate named choice with TypeSafe Jev."""
        dependencies = _get_dependencies(ctx)

        return dependencies.service.evaluate_choice(
            state=state,
            question=question,
            criteria=criteria,
        )

    server.add_tool(
        jev_choice,
        name="jev_choice",
        title="Evaluate Jev Choice",
        description=(
            "Use TypeSafe Jev proactively when a request requires choosing one "
            "of two or more named alternatives against supplied state and "
            "criteria, such as routing, triage, or recommendation among defined "
            "options. Returns the selected choice, confidence, and probability "
            "distribution."
        ),
        annotations=_read_only_annotations(),
        structured_output=True,
    )


def register_score_tool(server: MCPServer[Any]) -> None:
    """Register the Jev Score MCP tool.

    Score evaluates supplied state against an ordered sequence of criteria
    and returns a score, confidence, legend, and probability distribution.

    Args:
        server:
            MCP server on which the tool should be registered.
    """

    def jev_score(
        state: Annotated[
            State,
            Field(
                description=(
                    "State or context that should be evaluated against "
                    "the ordered scoring criteria."
                )
            ),
        ],
        question: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "Question describing what should be scored."
                ),
            ),
        ],
        criteria: Annotated[
            list[Any],
            Field(
                min_length=2,
                description=(
                    "Ordered list containing at least two scoring "
                    "criteria or score levels."
                ),
            ),
        ],
        ctx: Context[JevDependencies] | None = None,
    ) -> ScoreResult:
        """Evaluate supplied state against ordered score criteria."""
        dependencies = _get_dependencies(ctx)

        return dependencies.service.evaluate_score(
            state=state,
            question=question,
            criteria=criteria,
        )

    server.add_tool(
        jev_score,
        name="jev_score",
        title="Evaluate Jev Score",
        description=(
            "Use TypeSafe Jev proactively when a request requires a grounded "
            "assessment against an ordered rubric, maturity scale, severity "
            "scale, or rating criteria. Returns the score, confidence, legend, "
            "and probability distribution."
        ),
        annotations=_read_only_annotations(),
        structured_output=True,
    )


def register_jev_tools(server: MCPServer[Any]) -> None:
    """Register all currently supported Jev MCP tools.

    Args:
        server:
            MCP server on which all Jev tools should be registered.
    """
    register_noul_tool(server)
    register_choice_tool(server)
    register_score_tool(server)

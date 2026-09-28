"""Application domain models for Jev responses.

These models form the application's stable response contract.

The MCP layer and future ChatGPT Skills should consume these models rather
than depending directly on TypeSafe SDK response objects.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NoulResult(BaseModel):
    """Application representation of a Jev Noul result."""

    model_config = ConfigDict(frozen=True)

    probability: float = Field(
        ge=0.0,
        le=1.0,
        description="Probability that the Noul proposition is true.",
    )


class ChoiceResult(BaseModel):
    """Application representation of a Jev Choice result."""

    model_config = ConfigDict(frozen=True)

    choice: str = Field(
        min_length=1,
        description="Selected choice label.",
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence reported by Jev.",
    )

    probabilities: dict[str, float] = Field(
        description="Probability distribution over available choices.",
    )

    def model_post_init(self, __context: Any) -> None:
        """Validate the probability distribution after Pydantic validation."""
        for label, probability in self.probabilities.items():
            if not 0.0 <= probability <= 1.0:
                raise ValueError(
                    f"Choice probability for '{label}' must be between "
                    f"0 and 1."
                )

        if self.choice not in self.probabilities:
            raise ValueError(
                "The selected choice must exist in the probability "
                "distribution."
            )


class ScoreResult(BaseModel):
    """Application representation of a Jev Score result."""

    model_config = ConfigDict(frozen=True)

    score: float = Field(
        ge=0.0,
        description="Expected score returned by Jev.",
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence reported by Jev.",
    )

    legend: dict[int, Any] = Field(
        description="Mapping between score levels and rubric descriptions.",
    )

    probabilities: dict[int, float] = Field(
        description="Probability distribution over score levels.",
    )

    def model_post_init(self, __context: Any) -> None:
        """Validate score probability values."""
        for level, probability in self.probabilities.items():
            if not 0.0 <= probability <= 1.0:
                raise ValueError(
                    f"Score probability for level {level} must be between "
                    f"0 and 1."
                )
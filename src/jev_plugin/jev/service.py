"""Application service layer for TypeSafe Jev.

The service layer translates TypeSafe SDK responses into application-owned
domain models.

Architecture:

    MCP Tool
        |
        v
    JevService
        |
        v
    JevClient
        |
        v
    TypeSafe SDK
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError
from typesafe_sdk import Choice, Noul, NoulCriteria, Score

from jev_plugin.core import JevRequestError, JevResponseError

from .client import JevClient
from .models import ChoiceResult, NoulResult, ScoreResult


class JevService:
    """Provide application-level operations for TypeSafe Jev."""

    def __init__(self, client: JevClient) -> None:
        """Initialize the service.

        Args:
            client: Application-level TypeSafe client adapter.
        """
        self._client = client

    def evaluate_noul(
        self,
        *,
        state: Any,
        question: str,
        criteria: Mapping[str, Any] | None = None,
        question_id: str = "result",
    ) -> NoulResult:
        """Evaluate a yes/no proposition with Jev.

        Args:
            state: Content that Jev should evaluate.
            question: Proposition to evaluate.
            criteria: Optional descriptions for true/false outcomes.
            question_id: Identifier for the question.

        Returns:
            Application-owned NoulResult.
        """
        self._validate_question(question)
        self._validate_question_id(question_id)

        try:
            noul = Noul(
                instructions=question,
                criteria=self._to_noul_criteria(criteria),
            )
        except ValidationError as exc:
            raise JevRequestError(
                "Noul criteria must contain valid JSON content."
            ) from exc

        response = self._client.evaluate(
            state=state,
            questions={question_id: noul},
        )

        answer = self._get_answer(response, question_id)

        probability = getattr(answer, "noul", None)

        if probability is None:
            raise JevResponseError(
                f"Jev returned an invalid Noul answer for '{question_id}'."
            )

        try:
            return NoulResult(
                probability=float(probability),
            )
        except (TypeError, ValueError) as exc:
            raise JevResponseError(
                f"Jev returned an invalid Noul probability for "
                f"'{question_id}'."
            ) from exc

    def evaluate_choice(
        self,
        *,
        state: Any,
        question: str,
        criteria: Mapping[str, Any],
        question_id: str = "result",
    ) -> ChoiceResult:
        """Evaluate a state against a Choice question.

        Args:
            state: Content that Jev should evaluate.
            question: Description of the classification task.
            criteria: Available choice labels and descriptions.
            question_id: Identifier for the question.

        Returns:
            Application-owned ChoiceResult.
        """
        self._validate_question(question)
        self._validate_question_id(question_id)

        if len(criteria) < 2:
            raise JevRequestError(
                "A Choice question requires at least two criteria."
            )

        choice = Choice(
            instructions=question,
            criteria=dict(criteria),
        )

        response = self._client.evaluate(
            state=state,
            questions={question_id: choice},
        )

        answer = self._get_answer(response, question_id)

        selected_choice = getattr(answer, "choice", None)
        confidence = getattr(answer, "confidence", None)
        probabilities = getattr(answer, "probabilities", None)

        if selected_choice is None:
            raise JevResponseError(
                f"Jev returned no selected choice for '{question_id}'."
            )

        if confidence is None:
            raise JevResponseError(
                f"Jev returned no confidence for '{question_id}'."
            )

        if probabilities is None:
            raise JevResponseError(
                f"Jev returned no probability distribution for "
                f"'{question_id}'."
            )

        try:
            return ChoiceResult(
                choice=str(selected_choice),
                confidence=float(confidence),
                probabilities={
                    str(label): float(probability)
                    for label, probability in probabilities.items()
                },
            )
        except (TypeError, ValueError, AttributeError) as exc:
            raise JevResponseError(
                f"Jev returned an invalid Choice answer for "
                f"'{question_id}'."
            ) from exc

    def evaluate_score(
        self,
        *,
        state: Any,
        question: str,
        criteria: list[Any] | tuple[Any, ...],
        question_id: str = "result",
    ) -> ScoreResult:
        """Evaluate a state against an ordered Score rubric.

        Args:
            state: Content that Jev should evaluate.
            question: Description of the scoring task.
            criteria: Ordered rubric levels.
            question_id: Identifier for the question.

        Returns:
            Application-owned ScoreResult.
        """
        self._validate_question(question)
        self._validate_question_id(question_id)

        if len(criteria) < 2:
            raise JevRequestError(
                "A Score question requires at least two criteria."
            )

        score = Score(
            instructions=question,
            criteria=list(criteria),
        )

        response = self._client.evaluate(
            state=state,
            questions={question_id: score},
        )

        answer = self._get_answer(response, question_id)

        score_value = getattr(answer, "score", None)
        confidence = getattr(answer, "confidence", None)
        legend = getattr(answer, "legend", None)
        probabilities = getattr(answer, "probabilities", None)

        if score_value is None:
            raise JevResponseError(
                f"Jev returned no score for '{question_id}'."
            )

        if confidence is None:
            raise JevResponseError(
                f"Jev returned no confidence for '{question_id}'."
            )

        if legend is None:
            raise JevResponseError(
                f"Jev returned no score legend for '{question_id}'."
            )

        if probabilities is None:
            raise JevResponseError(
                f"Jev returned no score probability distribution for "
                f"'{question_id}'."
            )

        try:
            return ScoreResult(
                score=float(score_value),
                confidence=float(confidence),
                legend={
                    int(level): description
                    for level, description in legend.items()
                },
                probabilities={
                    int(level): float(probability)
                    for level, probability in probabilities.items()
                },
            )
        except (TypeError, ValueError, AttributeError) as exc:
            raise JevResponseError(
                f"Jev returned an invalid Score answer for "
                f"'{question_id}'."
            ) from exc

    @staticmethod
    def _validate_question(question: str) -> None:
        """Validate a Jev question."""
        if not isinstance(question, str):
            raise JevRequestError(
                "The Jev question must be a string."
            )

        if not question.strip():
            raise JevRequestError(
                "The Jev question cannot be empty."
            )

    @staticmethod
    def _validate_question_id(question_id: str) -> None:
        """Validate a question identifier."""
        if not isinstance(question_id, str):
            raise JevRequestError(
                "The Jev question ID must be a string."
            )

        if not question_id.strip():
            raise JevRequestError(
                "The Jev question ID cannot be empty."
            )

    @staticmethod
    def _to_noul_criteria(
        criteria: Mapping[str, Any] | None,
    ) -> NoulCriteria | None:
        """Convert application input to the TypeSafe Noul criteria contract."""
        if criteria is None:
            return None

        unsupported_keys = set(criteria).difference({"true", "false"})
        if unsupported_keys:
            raise JevRequestError(
                "Noul criteria may contain only 'true' and 'false' keys."
            )

        noul_criteria: NoulCriteria = {}
        if "true" in criteria:
            noul_criteria["true"] = criteria["true"]
        if "false" in criteria:
            noul_criteria["false"] = criteria["false"]

        return noul_criteria

    @staticmethod
    def _get_answer(
        response: Any,
        question_id: str,
    ) -> Any:
        """Retrieve a named answer from a TypeSafe response."""
        answers = getattr(response, "answers", None)

        if answers is None:
            raise JevResponseError(
                "Jev returned a response without an answers collection."
            )

        try:
            answer = answers[question_id]
        except (KeyError, TypeError, IndexError) as exc:
            raise JevResponseError(
                f"Jev returned no answer for '{question_id}'."
            ) from exc

        if answer is None:
            raise JevResponseError(
                f"Jev returned an empty answer for '{question_id}'."
            )

        return answer

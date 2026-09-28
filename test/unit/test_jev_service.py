"""Unit tests for the Jev application service."""

from typing import Any

import pytest

from jev_plugin.core import JevRequestError, JevResponseError
from jev_plugin.jev import (
    ChoiceResult,
    JevService,
    NoulResult,
    ScoreResult,
)


class FakeJevClient:
    """Fake JevClient used to test the service without network access."""

    def __init__(self, response: Any) -> None:
        self.response = response
        self.received_state: Any = None
        self.received_questions: dict[str, Any] | None = None

    def evaluate(
        self,
        *,
        state: Any,
        questions: dict[str, Any],
    ) -> Any:
        """Capture the request and return the configured response."""
        self.received_state = state
        self.received_questions = questions
        return self.response


class FakeAnswer:
    """Fake TypeSafe answer."""

    def __init__(
        self,
        *,
        noul: float | None = None,
        choice: str | None = None,
        confidence: float | None = None,
        probabilities: dict[Any, float] | None = None,
        score: float | None = None,
        legend: dict[Any, Any] | None = None,
    ) -> None:
        self.noul = noul
        self.choice = choice
        self.confidence = confidence
        self.probabilities = probabilities
        self.score = score
        self.legend = legend


class FakeResponse:
    """Fake TypeSafe response."""

    def __init__(self, answer: Any) -> None:
        self.answers = {
            "result": answer,
        }


def test_evaluate_noul_returns_domain_model() -> None:
    """Noul should be converted into NoulResult."""
    fake_client = FakeJevClient(
        FakeResponse(
            FakeAnswer(noul=0.87),
        )
    )

    service = JevService(fake_client)  # type: ignore[arg-type]

    result = service.evaluate_noul(
        state="This customer requested a refund.",
        question="Does the customer request a refund?",
    )

    assert isinstance(result, NoulResult)
    assert result.probability == 0.87


def test_evaluate_noul_adapts_criteria_to_typesafe_contract() -> None:
    """Noul criteria should use the SDK's true/false structure."""
    fake_client = FakeJevClient(FakeResponse(FakeAnswer(noul=0.87)))
    service = JevService(fake_client)  # type: ignore[arg-type]

    service.evaluate_noul(
        state="This customer requested a refund.",
        question="Does the customer request a refund?",
        criteria={
            "true": "The customer explicitly requests a refund.",
            "false": "The customer does not request a refund.",
        },
    )

    assert fake_client.received_questions is not None
    assert fake_client.received_questions["result"].criteria == {
        "true": "The customer explicitly requests a refund.",
        "false": "The customer does not request a refund.",
    }


def test_evaluate_noul_rejects_unknown_criteria_keys() -> None:
    """Noul criteria should not silently discard unsupported keys."""
    fake_client = FakeJevClient(FakeResponse(FakeAnswer(noul=0.87)))
    service = JevService(fake_client)  # type: ignore[arg-type]

    with pytest.raises(JevRequestError, match="only"):
        service.evaluate_noul(
            state="This customer requested a refund.",
            question="Does the customer request a refund?",
            criteria={"required": True},
        )

    assert fake_client.received_questions is None


def test_evaluate_noul_rejects_empty_question() -> None:
    """Empty Noul questions should fail before reaching the client."""
    fake_client = FakeJevClient(
        FakeResponse(FakeAnswer(noul=0.5)),
    )

    service = JevService(fake_client)  # type: ignore[arg-type]

    with pytest.raises(JevRequestError):
        service.evaluate_noul(
            state="test",
            question="   ",
        )

    assert fake_client.received_questions is None


def test_evaluate_noul_rejects_invalid_probability() -> None:
    """Noul probability must remain inside [0, 1]."""
    fake_client = FakeJevClient(
        FakeResponse(FakeAnswer(noul=1.5)),
    )

    service = JevService(fake_client)  # type: ignore[arg-type]

    with pytest.raises(JevResponseError):
        service.evaluate_noul(
            state="test",
            question="Is this true?",
        )


def test_evaluate_choice_returns_domain_model() -> None:
    """Choice should be converted into ChoiceResult."""
    fake_client = FakeJevClient(
        FakeResponse(
            FakeAnswer(
                choice="billing",
                confidence=0.91,
                probabilities={
                    "billing": 0.91,
                    "technical": 0.06,
                    "other": 0.03,
                },
            )
        )
    )

    service = JevService(fake_client)  # type: ignore[arg-type]

    result = service.evaluate_choice(
        state="Customer asks about a refund.",
        question="Which department should handle this?",
        criteria={
            "billing": "Payments and refunds.",
            "technical": "Technical problems.",
            "other": "Everything else.",
        },
    )

    assert isinstance(result, ChoiceResult)
    assert result.choice == "billing"
    assert result.confidence == 0.91
    assert result.probabilities["billing"] == 0.91


def test_evaluate_choice_requires_two_criteria() -> None:
    """Choice requires at least two possible outcomes."""
    fake_client = FakeJevClient(
        FakeResponse(
            FakeAnswer(
                choice="yes",
                confidence=1.0,
                probabilities={"yes": 1.0},
            )
        )
    )

    service = JevService(fake_client)  # type: ignore[arg-type]

    with pytest.raises(JevRequestError):
        service.evaluate_choice(
            state="test",
            question="What category is this?",
            criteria={"yes": None},
        )

    assert fake_client.received_questions is None


def test_evaluate_score_returns_domain_model() -> None:
    """Score should be converted into ScoreResult."""
    fake_client = FakeJevClient(
        FakeResponse(
            FakeAnswer(
                score=1.4,
                confidence=0.82,
                legend={
                    0: "Low",
                    1: "Medium",
                    2: "High",
                },
                probabilities={
                    0: 0.10,
                    1: 0.40,
                    2: 0.50,
                },
            )
        )
    )

    service = JevService(fake_client)  # type: ignore[arg-type]

    result = service.evaluate_score(
        state="Customer needs this resolved today.",
        question="How urgent is this?",
        criteria=[
            "Low",
            "Medium",
            "High",
        ],
    )

    assert isinstance(result, ScoreResult)
    assert result.score == 1.4
    assert result.confidence == 0.82
    assert result.legend[2] == "High"
    assert result.probabilities[2] == 0.50


def test_evaluate_score_requires_two_criteria() -> None:
    """Score requires at least two rubric levels."""
    fake_client = FakeJevClient(
        FakeResponse(
            FakeAnswer(
                score=0.0,
                confidence=1.0,
                legend={0: "Low"},
                probabilities={0: 1.0},
            )
        )
    )

    service = JevService(fake_client)  # type: ignore[arg-type]

    with pytest.raises(JevRequestError):
        service.evaluate_score(
            state="test",
            question="How urgent is this?",
            criteria=["low"],
        )

    assert fake_client.received_questions is None

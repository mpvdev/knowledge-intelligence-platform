"""The answer contract is enforced in code, not merely requested in the prompt."""

from __future__ import annotations

import pytest

from app.agent import (
    INSUFFICIENT_ANSWER,
    IntelligentResponse,
    PlatformKnowledgeAgent,
    is_refusal,
    public_answer,
)

normalise = PlatformKnowledgeAgent._knowledge_answer


@pytest.mark.parametrize(
    "variant",
    [
        INSUFFICIENT_ANSWER,
        INSUFFICIENT_ANSWER.rstrip("."),
        INSUFFICIENT_ANSWER.upper(),
        f'"{INSUFFICIENT_ANSWER}"',
        "  I don't have   enough information to answer that reliably.  ",
        "I don’t have enough information to answer that reliably.",
    ],
)
def test_refusal_survives_model_drift(variant: str) -> None:
    assert is_refusal(variant)


def test_answer_merely_mentioning_the_phrase_is_not_a_refusal() -> None:
    assert not is_refusal(
        "I don't have enough information to answer that reliably about cost, "
        "but onboarding works like this."
    )


def test_ordinary_answer_is_not_a_refusal() -> None:
    assert not is_refusal("Onboarding starts with a cluster request.")


def test_refusal_cannot_carry_a_diagram_or_buttons() -> None:
    drifted = IntelligentResponse(
        answer=INSUFFICIENT_ANSWER,
        response_type="onboarding",
        visual_nodes=("Request", "Approve", "Deploy"),
        suggested_questions=("How do I start?", "What is EKS?"),
    )
    result = normalise(drifted)
    assert result.answer == INSUFFICIENT_ANSWER
    assert result.visual is None
    assert result.suggested_questions == ()
    assert result.response_type == "general"


def test_drifted_refusal_is_canonicalised() -> None:
    drifted = IntelligentResponse(answer=f'  "{INSUFFICIENT_ANSWER.upper()}" ')
    assert normalise(drifted).answer == INSUFFICIENT_ANSWER


def test_blank_answer_degrades_to_a_refusal() -> None:
    assert normalise(IntelligentResponse(answer="   ")).answer == INSUFFICIENT_ANSWER


def test_follow_up_already_in_the_answer_is_dropped() -> None:
    response = IntelligentResponse(
        answer="Raise a cluster request, then await approval. What happens after approval?",
        suggested_questions=("What happens after approval?", "How long does approval take?"),
    )
    assert normalise(response).suggested_questions == ("How long does approval take?",)


def test_duplicate_follow_ups_collapse() -> None:
    response = IntelligentResponse(
        answer="Onboarding overview.",
        suggested_questions=("What is EKS?", "What is EKS?", "Where is the runbook?"),
    )
    assert normalise(response).suggested_questions == ("What is EKS?", "Where is the runbook?")


def test_a_single_node_is_not_a_flow() -> None:
    assert normalise(IntelligentResponse(answer="x", visual_nodes=("Only step",))).visual is None


def test_repeated_and_blank_nodes_are_cleaned() -> None:
    response = IntelligentResponse(answer="x", visual_nodes=("A", "A", "   ", "B"))
    assert normalise(response).visual == "A\n↓\nB"


def test_source_markers_are_stripped_from_nodes_and_follow_ups() -> None:
    response = IntelligentResponse(
        answer="x",
        visual_nodes=("Request [S1]", "Approve [S2]"),
        suggested_questions=("What next? [S1]",),
    )
    result = normalise(response)
    assert result.visual == "Request\n↓\nApprove"
    assert result.suggested_questions == ("What next?",)


def test_healthy_answer_passes_through_unchanged() -> None:
    response = IntelligentResponse(
        answer="Onboarding starts with a cluster request 🚀",
        response_type="onboarding",
        visual_nodes=("Request", "Approve", "Deploy"),
        suggested_questions=("What happens after approval?",),
    )
    result = normalise(response)
    assert result.answer == response.answer
    assert result.response_type == "onboarding"
    assert result.visual == "Request\n↓\nApprove\n↓\nDeploy"
    assert result.suggested_questions == ("What happens after approval?",)


def test_public_answer_removes_internal_markers() -> None:
    assert public_answer("Do this [S1]. Then that [S2].") == "Do this. Then that."


@pytest.mark.parametrize(
    "preamble",
    [
        "Based on the information provided,",
        "Based on the provided information,",
        "From the available information:",
        "From the information available -",
        "Using the approved TME knowledge available in the conversation,",
    ],
)
def test_public_answer_removes_backend_preamble(preamble: str) -> None:
    assert public_answer(f"{preamble} do this.") == "do this."


def test_public_answer_keeps_ordinary_text() -> None:
    assert public_answer("Based on your question, do this.") == "Based on your question, do this."


def test_instructions_use_the_refusal_constant() -> None:
    from app.agent import INSTRUCTIONS

    assert INSUFFICIENT_ANSWER in INSTRUCTIONS
    assert "{" not in INSTRUCTIONS and "}" not in INSTRUCTIONS

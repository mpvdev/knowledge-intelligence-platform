"""The evaluation harness. Skipped unless the dev extra is installed."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("strands_evals", reason="install the dev extra to run evaluation tests")

from strands_evals.types.evaluation import EvaluationData  # noqa: E402

from app.agent import INSUFFICIENT_ANSWER  # noqa: E402


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("evaluate", "scripts/evaluate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluate = _load_module()


def case(output: str, **metadata: Any) -> EvaluationData[str, str]:
    return EvaluationData[str, str](input="q", actual_output=output, metadata=metadata)


@pytest.mark.parametrize(
    ("output", "expect_refusal", "should_pass"),
    [
        (INSUFFICIENT_ANSWER, True, True),
        ("The cluster is healthy", True, False),
        ("EKS onboarding starts with a request", False, True),
        (INSUFFICIENT_ANSWER, False, False),
    ],
)
def test_refusal_discipline(output: str, expect_refusal: bool, should_pass: bool) -> None:
    result = evaluate.RefusalDiscipline().evaluate(case(output, expect_refusal=expect_refusal))
    assert result[0].test_pass is should_pass


def test_refusal_discipline_tolerates_drift() -> None:
    drifted = "I don’t have enough information to answer that reliably"
    result = evaluate.RefusalDiscipline().evaluate(case(drifted, expect_refusal=True))
    assert result[0].test_pass


@pytest.mark.parametrize("answer", ["The cluster is healthy now", "THE CLUSTER IS HEALTHY"])
def test_forbidden_claims_are_detected(answer: str) -> None:
    result = evaluate.ForbiddenClaims().evaluate(
        case(answer, forbidden_keywords=["cluster is healthy"])
    )
    assert not result[0].test_pass


def test_clean_answer_has_no_forbidden_claims() -> None:
    result = evaluate.ForbiddenClaims().evaluate(
        case("Raise a request", forbidden_keywords=["cluster is healthy"])
    )
    assert result[0].test_pass


def test_expected_coverage_scores_matches() -> None:
    result = evaluate.ExpectedCoverage().evaluate(
        case("Prerequisites for onboarding", expected_keywords=["prerequisite", "onboarding"])
    )
    assert result[0].score == 1.0


def test_expected_coverage_fails_when_absent() -> None:
    result = evaluate.ExpectedCoverage().evaluate(
        case("nothing relevant", expected_keywords=["prerequisite", "onboarding"])
    )
    assert result[0].score == 0.0
    assert not result[0].test_pass


def test_expected_coverage_is_not_applicable_without_keywords() -> None:
    assert evaluate.ExpectedCoverage().evaluate(case("x", expected_keywords=[]))[0].test_pass


@pytest.mark.parametrize(
    "answer", ["Do this [S1]", "Based on the information provided, do this"]
)
def test_internal_wording_leakage_is_caught(answer: str) -> None:
    assert not evaluate.NoInternalLeakage().evaluate(case(answer))[0].test_pass


def test_clean_public_answer_has_no_leakage() -> None:
    answer = "Raise a cluster request, then await approval."
    assert evaluate.NoInternalLeakage().evaluate(case(answer))[0].test_pass


def test_dataset_loads_with_metadata() -> None:
    cases = evaluate.load_cases(Path("evals/datasets"))
    assert cases
    assert all(c.metadata and "category" in c.metadata for c in cases)


def test_missing_dataset_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No evaluation cases"):
        evaluate.load_cases(tmp_path)


def test_report_summarises_by_evaluator_and_category() -> None:
    class StaleShapeReport:
        def to_dict(self) -> dict[str, Any]:
            return {
                "cases": [
                    {
                        "name": "s-1",
                        "evaluator": "refusal-discipline",
                        "metadata": {"category": "supported"},
                    },
                    {
                        "name": "u-1",
                        "evaluator": "refusal-discipline",
                        "metadata": {"category": "unsupported"},
                    },
                ],
                "scores": [1.0, 0.0],
                "test_passes": [True, False],
                "reasons": ["Refusal behaviour matched.", "Expected a refusal."],
            }

    markdown = evaluate.render_report(StaleShapeReport(), judged=False)
    assert "| refusal-discipline |" in markdown
    assert "| supported |" in markdown and "| unsupported |" in markdown
    assert "Expected a refusal." in markdown
    assert "Pass rate: **50%**" in markdown
    assert "deterministic evaluators only" in markdown


class FakeReport:
    """Mirrors the parallel-array shape strands_evals returns from to_dict()."""

    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document

    def to_dict(self) -> dict[str, Any]:
        return self.document


DOCUMENT = {
    "cases": [
        {
            "name": "alpha-001",
            "evaluator": "coverage",
            "metadata": {"category": "supported"},
        },
        {
            "name": "beta-001",
            "evaluator": "coverage",
            "metadata": {"category": "unsupported"},
        },
    ],
    "scores": [1.0, 0.25],
    "test_passes": [True, False],
    "reasons": ["matched 2 of 2", "matched 0 of 2"],
}


def test_scores_are_read_from_the_parallel_arrays() -> None:
    rows = _load_module().collect_rows(FakeReport(DOCUMENT))

    assert [row["score"] for row in rows] == [1.0, 0.25]
    assert [row["test_pass"] for row in rows] == [True, False]
    assert [row["reason"] for row in rows] == ["matched 2 of 2", "matched 0 of 2"]
    assert [row["name"] for row in rows] == ["alpha-001", "beta-001"]


def test_a_passing_case_is_not_reported_as_a_failure() -> None:
    markdown = _load_module().render_report(FakeReport(DOCUMENT), judged=False)

    assert "Pass rate: **50%**" in markdown
    failures = markdown.split("## Failures")[1]
    assert "alpha-001" not in failures
    assert "beta-001" in failures


def test_a_failure_reason_reaches_the_report() -> None:
    markdown = _load_module().render_report(FakeReport(DOCUMENT), judged=False)

    assert "matched 0 of 2" in markdown


def test_missing_outcome_arrays_do_not_crash_the_report() -> None:
    document = {"cases": DOCUMENT["cases"], "scores": [], "test_passes": [], "reasons": []}
    rows = _load_module().collect_rows(FakeReport(document))

    assert [row["score"] for row in rows] == [0.0, 0.0]
    assert all(row["test_pass"] is False for row in rows)

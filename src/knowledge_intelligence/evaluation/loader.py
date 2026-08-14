from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from knowledge_intelligence.evaluation.models import EvaluationCase


class EvaluationDataset(BaseModel):
    """Collection of evaluation cases."""

    model_config = ConfigDict(frozen=True)

    cases: tuple[EvaluationCase, ...]


def load_evaluation_dataset(path: Path) -> EvaluationDataset:
    """Load and validate a YAML evaluation dataset."""

    if not path.exists():
        raise FileNotFoundError(f"Evaluation dataset not found: {path}")

    raw_content = path.read_text(encoding="utf-8")
    payload = yaml.safe_load(raw_content)

    if payload is None:
        raise ValueError(f"Evaluation dataset is empty: {path}")

    return EvaluationDataset.model_validate(payload)

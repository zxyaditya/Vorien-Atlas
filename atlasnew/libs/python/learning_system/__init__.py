"""Atlas Learning System (L5 · sibling to Decision Engine).

Book 1 Ch. 1 places all ML at L5 as a *consumer* of Atlas representations.
The Learning System owns the full ML lifecycle — datasets, labels, splits,
training, evaluation, model registry, experiment tracking, inference —
while Atlas Core (L1..L4) remains mathematically pure.

Design anchors:
  - DEC-017: Learning System is a sibling L5 subsystem to `decision_engine/`.
            Neither imports the other; both consume `atlas_core.*`.
  - DEC-018: Model plug-in contract via `BaseModel` + `MODEL_REGISTRY`.
            No model is privileged by the architecture.

See docs/LEARNING_SYSTEM.md.
"""
from __future__ import annotations

__version__ = "0.13.0"

from learning_system.contracts import (  # noqa: F401
    DatasetSpec, SplitSpec, ModelSpec, ExperimentSpec,
    FoldMetrics, ExperimentResult, InferenceRequest, Prediction,
)
from learning_system.models import MODEL_REGISTRY, register_model, BaseModel  # noqa: F401

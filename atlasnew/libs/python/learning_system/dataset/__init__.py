"""Dataset subsystem — Feature matrix + labels + splits."""
from __future__ import annotations
from learning_system.dataset.feature_matrix import build_feature_matrix  # noqa: F401
from learning_system.dataset.labels import LABEL_KINDS, generate_labels  # noqa: F401
from learning_system.dataset.splits import SPLIT_KINDS, generate_splits  # noqa: F401
from learning_system.dataset.builder import build_dataset, DatasetPreview  # noqa: F401

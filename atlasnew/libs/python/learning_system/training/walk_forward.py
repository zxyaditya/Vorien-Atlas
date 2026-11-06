"""Convenience wrapper around TrainingPipeline for walk-forward runs."""
from __future__ import annotations
from typing import Dict, Optional

import pandas as pd

from learning_system.contracts import (
    DatasetSpec, ExperimentSpec, ModelSpec, SplitSpec,
)
from learning_system.training.pipeline import TrainingPipeline, TrainingResult


def run_walk_forward(df: pd.DataFrame, name: str, feature_ids, model_kind: str,
                     horizon: int = 5, n_folds: int = 5,
                     label_kind: str = "sign",
                     label_params: Optional[dict] = None,
                     hyperparams: Optional[dict] = None,
                     seed: int = 42,
                     context: Optional[Dict[str, pd.DataFrame]] = None,
                     ) -> TrainingResult:
    spec = ExperimentSpec(
        name=name,
        dataset=DatasetSpec(
            feature_ids=list(feature_ids), horizon=horizon,
            label_kind=label_kind, label_params=dict(label_params or {}),
        ),
        split=SplitSpec(kind="walk_forward", n_folds=n_folds),
        model=ModelSpec(kind=model_kind,
                         hyperparams=dict(hyperparams or {}), seed=seed),
    )
    return TrainingPipeline(spec).run(df, context=context)

"""XGBoost model plug-in."""
from __future__ import annotations
from typing import Any, ClassVar, Dict

import numpy as np
import pandas as pd

from learning_system.models.base import BaseModel


def _register(cls):
    from learning_system.models import MODEL_REGISTRY
    kind = cls.kind
    if kind in MODEL_REGISTRY:
        return cls
    MODEL_REGISTRY[kind] = cls
    return cls


@_register
class XGBoostModel(BaseModel):
    kind: ClassVar[str] = "xgboost"
    default_hparams: ClassVar[Dict[str, Any]] = {
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.7,
        "colsample_bytree": 0.3,
        "min_child_weight": 1.0,
        "eval_metric": "logloss",
        "n_jobs": -1,
        "tree_method": "hist",
        "device": "cuda",
    }

    def __init__(self, hyperparams=None, seed: int = 42):
        super().__init__(hyperparams, seed)
        from xgboost import XGBClassifier
        self._model = XGBClassifier(random_state=self.seed, **self.hyperparams)

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        self._feature_names = list(X.columns)
        self._model.fit(X.values, y)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self._model.predict_proba(X[self._feature_names].values)

    def feature_importances(self) -> Dict[str, float]:
        imp = getattr(self._model, "feature_importances_", None)
        if imp is None:
            return {}
        return {name: float(v) for name, v in zip(self._feature_names, imp)}

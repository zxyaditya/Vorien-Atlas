"""BaseModel — the plug-in contract every model must satisfy.

DEC-018. Model-agnostic: the framework never checks the concrete type,
only this interface.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Dict, List

import numpy as np
import pandas as pd


class BaseModel(ABC):
    """Every registered model MUST subclass this and set `kind`."""

    kind: ClassVar[str] = "__abstract__"
    default_hparams: ClassVar[Dict[str, Any]] = {}

    def __init__(self, hyperparams: Dict[str, Any] = None, seed: int = 42):
        merged = dict(self.default_hparams)
        if hyperparams:
            merged.update(hyperparams)
        self.hyperparams = merged
        self.seed = int(seed)
        self._model: Any = None
        self._feature_names: List[str] = []

    # --- fit / predict --------------------------------------------------
    @abstractmethod
    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None: ...

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return shape (n, 2) with P(class=0), P(class=1)."""
        ...

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        proba = self.predict_proba(X)
        return (proba[:, 1] >= threshold).astype(int)

    # --- introspection ---------------------------------------------------
    @abstractmethod
    def feature_importances(self) -> Dict[str, float]: ...

    # --- persistence -----------------------------------------------------
    def to_disk(self, path: Path) -> None:
        import joblib
        payload = {
            "kind": self.kind, "hyperparams": self.hyperparams,
            "seed": self.seed, "feature_names": self._feature_names,
            "model": self._model,
        }
        joblib.dump(payload, path)

    @classmethod
    def from_disk(cls, path: Path) -> "BaseModel":
        import joblib
        payload = joblib.load(path)
        inst = cls(hyperparams=payload["hyperparams"], seed=payload["seed"])
        inst._model = payload["model"]
        inst._feature_names = payload["feature_names"]
        return inst

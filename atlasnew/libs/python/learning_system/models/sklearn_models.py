"""Classical scikit-learn model plug-ins.

Registered kinds: logreg, randomforest, gradientboost.
"""
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


class _SklearnBase(BaseModel):
    """Shared sklearn plumbing."""

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        self._feature_names = list(X.columns)
        self._model.fit(X.values, y)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self._model.predict_proba(X[self._feature_names].values)

    def feature_importances(self) -> Dict[str, float]:
        m = self._model
        imp = None
        
        if hasattr(m, "named_steps"):
            clf = m.named_steps.get("clf")
            if clf is not None:
                if hasattr(clf, "feature_importances_"):
                    imp = clf.feature_importances_
                elif hasattr(clf, "coef_"):
                    imp = np.abs(clf.coef_[0])
        else:
            if hasattr(m, "feature_importances_"):
                imp = m.feature_importances_
            elif hasattr(m, "coef_"):
                imp = np.abs(m.coef_[0])
                
        if imp is None:
            return {}
        return {name: float(v) for name, v in zip(self._feature_names, imp)}


@_register
class LogisticRegressionModel(_SklearnBase):
    kind: ClassVar[str] = "logreg"
    default_hparams: ClassVar[Dict[str, Any]] = {
        "C": 1.0, "max_iter": 500, "solver": "lbfgs",
    }

    def __init__(self, hyperparams=None, seed: int = 42):
        super().__init__(hyperparams, seed)
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.impute import SimpleImputer
        self._model = Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value=0.0)),
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(random_state=self.seed,
                                        **self.hyperparams)),
        ])


@_register
class RandomForestModel(_SklearnBase):
    kind: ClassVar[str] = "randomforest"
    default_hparams: ClassVar[Dict[str, Any]] = {
        "n_estimators": 200, "max_depth": 8, "min_samples_leaf": 5,
        "n_jobs": 1,
    }

    def __init__(self, hyperparams=None, seed: int = 42):
        super().__init__(hyperparams, seed)
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.pipeline import Pipeline
        from sklearn.impute import SimpleImputer
        self._model = Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value=0.0)),
            ("clf", RandomForestClassifier(random_state=self.seed, **self.hyperparams)),
        ])


@_register
class GradientBoostModel(_SklearnBase):
    kind: ClassVar[str] = "gradientboost"
    default_hparams: ClassVar[Dict[str, Any]] = {
        "n_estimators": 150, "max_depth": 3, "learning_rate": 0.05,
    }

    def __init__(self, hyperparams=None, seed: int = 42):
        super().__init__(hyperparams, seed)
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.pipeline import Pipeline
        from sklearn.impute import SimpleImputer
        self._model = Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value=0.0)),
            ("clf", GradientBoostingClassifier(random_state=self.seed, **self.hyperparams)),
        ])

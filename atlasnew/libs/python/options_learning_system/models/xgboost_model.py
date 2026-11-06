"""XGBoost Model for Options.

Implements the multi-output learning (or simple directional) using XGBoost.
"""
from __future__ import annotations
import pandas as pd
import xgboost as xgb
from typing import Dict, Any

from options_learning_system.models.base import OptionsModel

class OptionsXGBoostModel(OptionsModel):
    def __init__(self, params: Dict[str, Any] = None):
        if params is None:
            params = {
                "max_depth": 5,
                "learning_rate": 0.05,
                "n_estimators": 200,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "objective": "binary:logistic",
                "eval_metric": "logloss",
                "random_state": 42
            }
        self.params = params
        self.model = xgb.XGBClassifier(**self.params)
        self._is_trained = False

    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        self.model.fit(X, y)
        self._is_trained = True

    def predict_proba(self, X: pd.DataFrame) -> pd.Series:
        if not self._is_trained:
            raise RuntimeError("Model not trained.")
        preds = self.model.predict_proba(X)[:, 1]
        return pd.Series(preds, index=X.index)

    def get_feature_importance(self) -> Dict[str, float]:
        if not self._is_trained:
            return {}
        importance = self.model.feature_importances_
        return {f: float(imp) for f, imp in zip(self.model.feature_names_in_, importance)}

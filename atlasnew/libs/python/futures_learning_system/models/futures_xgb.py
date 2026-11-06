import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from typing import Dict, Any

class FuturesXGBoostModel:
    def __init__(self, hyperparams: Dict[str, Any] = None):
        hp = {"n_estimators":300,"max_depth":6,"learning_rate":0.03,
              "subsample":0.8,"colsample_bytree":0.7,"eval_metric":"logloss",
              "n_jobs":-1,"random_state":42,"use_label_encoder":False}
        if hyperparams: hp.update(hyperparams)
        self.model = XGBClassifier(**hp)
        self.feature_names = []

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.feature_names = list(X.columns)
        self.model.fit(X, y)

    def predict_proba(self, X: pd.DataFrame) -> pd.Series:
        X_a = X.reindex(columns=self.feature_names).fillna(0.0)
        proba = self.model.predict_proba(X_a)
        return pd.Series(proba[:, 1], index=X.index)

    def feature_importances(self) -> Dict[str, float]:
        imp = getattr(self.model, "feature_importances_", None)
        if imp is None: return {}
        return dict(zip(self.feature_names, imp))

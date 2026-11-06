"""Options Training Pipeline.

Orchestrates the training, evaluation, and saving of options models.
"""
from __future__ import annotations
import os
import joblib
import pandas as pd
from typing import Dict, Any

from options_learning_system.dataset.builder import OptionsDataset
from options_learning_system.models.xgboost_model import OptionsXGBoostModel
from options_learning_system.training.metrics import calculate_metrics

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

class OptionsPipeline:
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.model = OptionsXGBoostModel()
        self.metrics: Dict[str, float] = {}

    def train(self, dataset: OptionsDataset) -> None:
        """Train the model on the full dataset X, y."""
        self.model.train(dataset.X, dataset.y)

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, float]:
        """Evaluate the model on a test set."""
        preds = self.model.predict_proba(X_test)
        self.metrics = calculate_metrics(y_test, preds)
        return self.metrics

    def save(self) -> str:
        """Save the trained model to artifacts."""
        path = os.path.join(ARTIFACTS_DIR, f"{self.model_id}.pkl")
        joblib.dump(self.model, path)
        return path

    @classmethod
    def load(cls, model_id: str) -> "OptionsPipeline":
        """Load a trained pipeline from artifacts."""
        path = os.path.join(ARTIFACTS_DIR, f"{model_id}.pkl")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model artifact not found: {path}")
        
        instance = cls(model_id)
        instance.model = joblib.load(path)
        instance.model._is_trained = True
        return instance

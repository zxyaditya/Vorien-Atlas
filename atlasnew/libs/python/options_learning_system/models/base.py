"""Options ML Models Base Interface."""
from __future__ import annotations
import abc
import pandas as pd
from typing import Any, Dict

class OptionsModel(abc.ABC):
    @abc.abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        pass

    @abc.abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> pd.Series:
        pass
        
    @abc.abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        pass

"""Options Training Metrics.

Options-specific evaluation metrics: Brier score on exercise, IV RMSE, Information Coefficient.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any

def information_coefficient(y_true: pd.Series, y_pred: pd.Series) -> float:
    """Rank correlation between predictions and true labels."""
    if len(y_true) < 2:
        return 0.0
    return float(y_pred.corr(y_true, method="spearman"))

def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Mean squared difference between predicted probability and actual outcome."""
    if len(y_true) == 0:
        return 0.0
    return float(np.mean((y_prob - y_true) ** 2))

def root_mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """RMSE for continuous targets like IV."""
    if len(y_true) == 0:
        return 0.0
    return float(np.sqrt(np.mean((y_pred - y_true) ** 2)))

def calculate_metrics(y_true: pd.Series, y_pred_prob: pd.Series) -> Dict[str, float]:
    """Calculate standard classification metrics."""
    if len(y_true) == 0:
        return {}
        
    y_true_arr = y_true.values
    y_prob_arr = y_pred_prob.values
    y_pred_class = (y_prob_arr > 0.5).astype(int)
    
    acc = float(np.mean(y_pred_class == y_true_arr))
    ic = information_coefficient(y_true, y_pred_prob)
    brier = brier_score(y_true_arr, y_prob_arr)
    
    return {
        "accuracy": acc,
        "information_coefficient": ic,
        "brier_score": brier
    }

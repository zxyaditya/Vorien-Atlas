"""Evaluation metrics — all classical + IC.

Every metric operates on:
  y_true:  np.ndarray[int]   ∈ {0, 1}
  y_prob:  np.ndarray[float] ∈ [0, 1]  (P(class=1))
All returns are finite Python floats.
"""
from __future__ import annotations
import numpy as np
from typing import Dict


def _safe(v):
    v = float(v)
    return v if np.isfinite(v) else 0.0


def accuracy(y_true, y_prob, threshold: float = 0.5) -> float:
    y_hat = (y_prob >= threshold).astype(int)
    return _safe((y_hat == y_true).mean())


def hit_rate(y_true, y_prob, threshold: float = 0.5) -> float:
    """Rate at which the model's directional call agrees with the label."""
    return accuracy(y_true, y_prob, threshold)


def log_loss(y_true, y_prob, eps: float = 1e-6) -> float:
    y_prob = np.clip(y_prob, eps, 1.0 - eps)
    ll = -(y_true * np.log(y_prob) + (1 - y_true) * np.log(1 - y_prob)).mean()
    return _safe(ll)


def brier(y_true, y_prob) -> float:
    return _safe(((y_prob - y_true) ** 2).mean())


def information_coefficient(y_true, y_prob) -> float:
    """Spearman-rank correlation between predicted prob and label."""
    if len(y_true) < 10:
        return 0.0
    from scipy.stats import spearmanr
    try:
        rho, _ = spearmanr(y_prob, y_true)
    except Exception:
        return 0.0
    return _safe(rho)


def edge_rate(y_true, y_prob, threshold: float = 0.55) -> float:
    """Fraction of forecasts with |p - 0.5| >= (threshold - 0.5)."""
    margin = np.abs(y_prob - 0.5)
    return _safe((margin >= (threshold - 0.5)).mean())


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> Dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)
    # Guard against single-class test blocks (metrics that assume balance).
    n_classes = len(np.unique(y_true))
    result = {
        "accuracy": accuracy(y_true, y_prob),
        "hit_rate": hit_rate(y_true, y_prob),
        "log_loss": log_loss(y_true, y_prob),
        "brier": brier(y_true, y_prob),
        "edge_rate": edge_rate(y_true, y_prob),
        "n_classes_in_test": int(n_classes),
    }
    
    y_hat = (y_prob >= 0.5).astype(int)
    tp = int((y_true * y_hat).sum())
    fp = int(((1 - y_true) * y_hat).sum())
    tn = int(((1 - y_true) * (1 - y_hat)).sum())
    fn = int((y_true * (1 - y_hat)).sum())
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    result["precision"] = _safe(precision)
    result["recall"] = _safe(recall)
    result["f1"] = _safe(f1)
    result["confusion_matrix"] = {"tp": tp, "fp": fp, "tn": tn, "fn": fn}

    if n_classes == 2:
        result["information_coefficient"] = information_coefficient(y_true, y_prob)
        try:
            from sklearn.metrics import roc_auc_score
            result["roc_auc"] = _safe(roc_auc_score(y_true, y_prob))
        except Exception:
            result["roc_auc"] = 0.0
    else:
        result["information_coefficient"] = 0.0
        result["roc_auc"] = 0.0
        
    return {k: (round(v, 6) if isinstance(v, float) else v)
            for k, v in result.items()}

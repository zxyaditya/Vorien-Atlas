"""Stand-alone evaluation — take a fitted model + a test slice → metrics.

Used by the Inference Pipeline when the caller wants to score a model
on a fresh out-of-sample slice without kicking off a full training run.
"""
from __future__ import annotations
from typing import Any, Dict

import numpy as np
import pandas as pd

from learning_system.training.metrics import compute_metrics


def evaluate(model, X: pd.DataFrame, y: np.ndarray) -> Dict[str, Any]:
    proba = model.predict_proba(X)
    m = compute_metrics(y, proba[:, 1])
    return {
        "n": int(len(X)),
        "metrics": m,
        "top_features": _top_k(model.feature_importances(), 10),
    }


def _top_k(imp: Dict[str, float], k: int):
    return [{"id": kk, "importance": round(float(v), 6)}
            for kk, v in sorted(imp.items(), key=lambda kv: -kv[1])[:k]]

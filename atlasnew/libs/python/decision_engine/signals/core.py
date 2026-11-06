from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, List

def _last(series):
    if series is None:
        return None
    try:
        v = float(series.iloc[-1] if isinstance(series, pd.Series) else series)
        return v if np.isfinite(v) else None
    except Exception:
        return None

def _get(vals: Dict[str, float], fid: str, default=None):
    v = vals.get(fid)
    return v if v is not None and np.isfinite(v) else default

def _make_signal(name: str, direction: int, strength: float,
                 confidence: float, evidence: List[dict]) -> dict:
    return {
        "name": name,
        "direction": int(direction),           # -1, 0, +1
        "strength": float(max(0.0, min(1.0, strength))),
        "confidence": float(max(0.0, min(1.0, confidence))),
        "evidence": evidence,
    }

def _row(fid: str, val, arg: str, wt: float) -> dict:
    return {"feature_id": fid, "value": val, "argument": arg, "weight": wt}

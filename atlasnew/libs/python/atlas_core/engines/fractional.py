"""Fractional Differencing Engine."""
from __future__ import annotations

import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series

def _get_weights_ffd(d: float, thres: float = 1e-4) -> np.ndarray:
    w, k = [1.0], 1
    while True:
        w_k = -w[-1] * (d - k + 1) / k
        if abs(w_k) < thres:
            break
        w.append(w_k)
        k += 1
    return np.array(w[::-1])

def frac_diff(x: np.ndarray, d: float = 0.4, thres: float = 1e-4) -> pd.Series:
    """Apply fractional differencing to preserve memory and ensure stationarity."""
    s = as_series(x)
    w = _get_weights_ffd(d, thres)
    width = len(w)
    
    # Fast rolling dot product
    def _dot(a):
        # dot product requires matching length
        if len(a) != width:
            return np.nan
        return np.dot(a, w)
        
    res = s.rolling(width).apply(_dot, raw=True)
    return res

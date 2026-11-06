"""Distribution Engine — empirical distribution properties."""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series


def rolling_percentile_rank(x, w: int) -> pd.Series:
    """Percentile rank of the current value within the trailing window ∈ [0,1]."""
    s = as_series(x)
    def _rk(a):
        return float((a[:-1] <= a[-1]).mean())
    return s.rolling(w, min_periods=w).apply(_rk, raw=True)


def rolling_quantile(x, w: int, q: float) -> pd.Series:
    return as_series(x).rolling(w, min_periods=w).quantile(q)


def rolling_ecdf_value(x, w: int, target: float) -> pd.Series:
    """Fraction of values in the window <= target (ECDF at target)."""
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: float((a <= target).mean()), raw=True)

def hill_estimator(x: np.ndarray, w: int = 100, k: int = 10) -> pd.Series:
    """Estimate tail index (Hill estimator) from absolute returns."""
    s = as_series(x)
    
    # Calculate absolute returns
    ret = np.abs(np.diff(s, prepend=s.iloc[0]))
    ret_s = pd.Series(ret, index=s.index)
    
    def _hill(arr):
        # Drop NaNs and sort ascending
        valid = arr[~np.isnan(arr)]
        if len(valid) <= k:
            return 0.0
        valid = np.sort(valid)
        
        # Top k order statistics
        top_k = valid[-k:]
        threshold = valid[-k-1]
        
        # Avoid division by zero or log(<=0)
        if threshold <= 0:
            return 0.0
            
        return np.mean(np.log(top_k / threshold))
        
    res = ret_s.rolling(w).apply(_hill, raw=True)
    return res

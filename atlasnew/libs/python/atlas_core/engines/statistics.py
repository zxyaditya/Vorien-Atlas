"""Statistics Engine — descriptive statistics over rolling windows."""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series


def rolling_mean(x, w: int) -> pd.Series:
    return as_series(x).rolling(w, min_periods=w).mean()


def rolling_std(x, w: int) -> pd.Series:
    return as_series(x).rolling(w, min_periods=w).std(ddof=1)


def rolling_var(x, w: int) -> pd.Series:
    return as_series(x).rolling(w, min_periods=w).var(ddof=1)


def rolling_median(x, w: int) -> pd.Series:
    return as_series(x).rolling(w, min_periods=w).median()


def rolling_mad(x, w: int) -> pd.Series:
    """Median absolute deviation — robust dispersion."""
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: np.median(np.abs(a - np.median(a))), raw=True)


def rolling_skew(x, w: int) -> pd.Series:
    return as_series(x).rolling(w, min_periods=w).skew()


def rolling_kurt(x, w: int) -> pd.Series:
    return as_series(x).rolling(w, min_periods=w).kurt()


def rolling_min(x, w: int) -> pd.Series:
    return as_series(x).rolling(w, min_periods=w).min()


def rolling_max(x, w: int) -> pd.Series:
    return as_series(x).rolling(w, min_periods=w).max()


def rolling_range(x, w: int) -> pd.Series:
    return rolling_max(x, w) - rolling_min(x, w)


def rolling_iqr(x, w: int) -> pd.Series:
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: np.percentile(a, 75) - np.percentile(a, 25), raw=True)


def rolling_entropy(x, w: int, bins: int = 10) -> pd.Series:
    """Shannon entropy of the empirical histogram over the window."""
    s = as_series(x)
    def _ent(a):
        hist, _ = np.histogram(a, bins=bins)
        p = hist / hist.sum() if hist.sum() > 0 else hist
        p = p[p > 0]
        return float(-np.sum(p * np.log(p))) if len(p) else np.nan
    return s.rolling(w, min_periods=w).apply(_ent, raw=True)


def rolling_autocorr(x, w: int, lag: int = 1) -> pd.Series:
    s = as_series(x)
    def _ac(a):
        a1, a2 = a[:-lag], a[lag:]
        if a1.std() == 0 or a2.std() == 0:
            return np.nan
        return float(np.corrcoef(a1, a2)[0, 1])
    return s.rolling(w, min_periods=w).apply(_ac, raw=True)

def garman_klass_volatility(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray, w: int = 20) -> pd.Series:
    """Garman-Klass Volatility: Uses OHLC for efficient variance estimation."""
    o, h, l, c = as_series(open_), as_series(high), as_series(low), as_series(close)
    
    log_hl = np.log(h / l.replace(0, np.nan))
    log_co = np.log(c / o.replace(0, np.nan))
    
    gk_t = 0.5 * (log_hl ** 2) - (2 * np.log(2) - 1) * (log_co ** 2)
    var = gk_t.rolling(w).mean()
    
    # Clip to 0 to avoid sqrt(negative) floating point errors
    return np.sqrt(var.clip(lower=0))

def rogers_satchell_volatility(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray, w: int = 20) -> pd.Series:
    """Rogers-Satchell Volatility: Drift-independent variance estimator."""
    o, h, l, c = as_series(open_), as_series(high), as_series(low), as_series(close)
    
    log_ho = np.log(h / o.replace(0, np.nan))
    log_hc = np.log(h / c.replace(0, np.nan))
    log_lo = np.log(l / o.replace(0, np.nan))
    log_lc = np.log(l / c.replace(0, np.nan))
    
    rs_t = (log_hc * log_ho) + (log_lc * log_lo)
    var = rs_t.rolling(w).mean()
    
    return np.sqrt(var.clip(lower=0))

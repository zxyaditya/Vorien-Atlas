"""Cross-Asset Engine — multi-symbol relationship primitives.

Contract: the module passes in two aligned pd.Series (target, peer)
or a target + a dict of peer series. Alignment is the caller's job
(we simply reindex on the intersection of indices).

Domain-neutral: works on any pair of numeric series.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Iterable
from atlas_core.engines.rolling import as_series


def align(a: pd.Series, b: pd.Series) -> tuple:
    a = as_series(a); b = as_series(b)
    idx = a.index.intersection(b.index)
    return a.reindex(idx), b.reindex(idx)


def ratio(a: pd.Series, b: pd.Series) -> pd.Series:
    a, b = align(a, b)
    return a / b.replace(0, np.nan)


def log_spread(a: pd.Series, b: pd.Series) -> pd.Series:
    a, b = align(a, b)
    return np.log(a) - np.log(b)


def rolling_corr(ra: pd.Series, rb: pd.Series, w: int) -> pd.Series:
    ra, rb = align(ra, rb)
    return ra.rolling(w, min_periods=w).corr(rb)


def rolling_beta(ra: pd.Series, rb: pd.Series, w: int) -> pd.Series:
    """β = cov(a,b) / var(b) over w bars."""
    ra, rb = align(ra, rb)
    cov = ra.rolling(w, min_periods=w).cov(rb)
    var = rb.rolling(w, min_periods=w).var(ddof=1).replace(0, np.nan)
    return cov / var


def relative_strength(pa: pd.Series, pb: pd.Series, w: int) -> pd.Series:
    """Cumulative return of a over b in the last w bars."""
    pa, pb = align(pa, pb)
    return (pa / pa.shift(w)) / (pb / pb.shift(w)).replace(0, np.nan)


def relative_volatility(ra: pd.Series, rb: pd.Series, w: int) -> pd.Series:
    ra, rb = align(ra, rb)
    sa = ra.rolling(w, min_periods=w).std(ddof=1)
    sb = rb.rolling(w, min_periods=w).std(ddof=1).replace(0, np.nan)
    return sa / sb


def lead_lag_corr(ra: pd.Series, rb: pd.Series, w: int, lag: int) -> pd.Series:
    """corr(a_t, b_{t-lag}). lag>0 means peer leads target."""
    ra, rb = align(ra, rb)
    return ra.rolling(w, min_periods=w).corr(rb.shift(lag))


def dispersion_across(peers: Dict[str, pd.Series], w: int) -> pd.Series:
    """Cross-sectional std of peer returns over each bar (proxy for dispersion).
    Returns aligned to the union index; requires >= 2 peers.
    """
    if len(peers) < 2:
        return pd.Series(dtype=float)
    df = pd.concat(peers, axis=1)
    return df.std(axis=1, ddof=1).rolling(w, min_periods=w).mean()


def mean_pairwise_corr(peers: Dict[str, pd.Series], w: int) -> pd.Series:
    """Rolling mean of the pairwise correlation matrix across peers."""
    if len(peers) < 2:
        return pd.Series(dtype=float)
    df = pd.concat(peers, axis=1).dropna(how="all")
    def _mean_corr(block):
        if len(block) < 3:
            return np.nan
        c = block.corr().values
        # off-diagonal mean
        n = c.shape[0]
        mask = ~np.eye(n, dtype=bool)
        vals = c[mask]
        vals = vals[np.isfinite(vals)]
        return float(vals.mean()) if vals.size else np.nan
    out = df.rolling(w, min_periods=w).apply(lambda x: np.nan, raw=False)
    # Fall back to a manual loop (rolling apply on a DataFrame is column-wise)
    idx = df.index
    vals_out = np.full(len(idx), np.nan)
    arr = df.values
    for i in range(w - 1, len(idx)):
        block = pd.DataFrame(arr[i - w + 1: i + 1], columns=df.columns)
        vals_out[i] = _mean_corr(block)
    return pd.Series(vals_out, index=idx)


def leadership(pa: pd.Series, pb: pd.Series, w: int) -> pd.Series:
    """argmax over lag ∈ {-3..+3} of |corr(a_t, b_{t-lag})|.
    Positive result → target leads peer; negative → peer leads target.
    """
    pa, pb = align(pa, pb)
    ra = pa.pct_change(fill_method=None)
    rb = pb.pct_change(fill_method=None)
    lags = list(range(-3, 4))
    best = pd.Series(np.zeros(len(pa)), index=pa.index)
    best_abs = pd.Series(np.full(len(pa), -np.inf), index=pa.index)
    for L in lags:
        c = ra.rolling(w, min_periods=w).corr(rb.shift(L)).abs()
        mask = c > best_abs
        best = best.where(~mask, other=L)
        best_abs = best_abs.where(~mask, other=c)
    return best.astype(float)


def cointegration_residual_std(pa: pd.Series, pb: pd.Series,
                                w: int) -> pd.Series:
    """Rolling std of the OLS residual of ln(a) ~ ln(b). Low std relative to
    input std suggests cointegration-like behaviour (not a formal ADF).
    """
    a, b = align(pa, pb)
    la, lb = np.log(a), np.log(b)
    out = np.full(len(a), np.nan)
    la_arr = la.values; lb_arr = lb.values
    for i in range(w - 1, len(a)):
        y = la_arr[i - w + 1: i + 1]
        x = lb_arr[i - w + 1: i + 1]
        if not (np.isfinite(y).all() and np.isfinite(x).all()):
            continue
        # OLS on constant + x
        X = np.column_stack([np.ones(w), x])
        try:
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            resid = y - X @ beta
            out[i] = float(np.std(resid, ddof=1))
        except Exception:
            pass
    return pd.Series(out, index=a.index)

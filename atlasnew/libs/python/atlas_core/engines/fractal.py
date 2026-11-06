"""Fractal Engine — self-similarity, roughness, long-range dependence."""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series


def _higuchi_fd_1d(x: np.ndarray, kmax: int = 8) -> float:
    """Higuchi fractal dimension of a 1D series."""
    N = len(x)
    if N < 2 * kmax:
        return np.nan
    L = np.zeros(kmax)
    for k in range(1, kmax + 1):
        Lk = 0.0
        for m in range(k):
            idxs = np.arange(m, N, k)
            if len(idxs) < 2:
                continue
            Lmk = np.sum(np.abs(np.diff(x[idxs]))) * (N - 1) / (((N - m - 1) // k) * k)
            Lk += Lmk
        L[k - 1] = Lk / k
    lnL = np.log(L + 1e-12)
    lnk = np.log(1.0 / np.arange(1, kmax + 1))
    slope, _ = np.polyfit(lnk, lnL, 1)
    return float(slope)


def higuchi_fd(x, w: int, kmax: int = 8) -> pd.Series:
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: _higuchi_fd_1d(np.asarray(a, dtype=float), kmax), raw=True)


def _hurst_rs_1d(x: np.ndarray) -> float:
    """Rescaled-range Hurst exponent estimate."""
    N = len(x)
    if N < 10:
        return np.nan
    mean = np.mean(x)
    y = x - mean
    Z = np.cumsum(y)
    R = np.max(Z) - np.min(Z)
    S = np.std(x, ddof=1)
    if S == 0 or R == 0:
        return np.nan
    # single-scale rescaled range; use log(R/S)/log(N) as approx
    return float(np.log(R / S) / np.log(N))


def hurst_rs(x, w: int) -> pd.Series:
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: _hurst_rs_1d(np.asarray(a, dtype=float)), raw=True)


def _dfa_alpha_1d(x: np.ndarray, min_box: int = 4) -> float:
    """Detrended Fluctuation Analysis exponent."""
    N = len(x)
    if N < 4 * min_box:
        return np.nan
    y = np.cumsum(x - np.mean(x))
    scales = np.unique(np.logspace(np.log10(min_box), np.log10(N // 4), 8).astype(int))
    F = []
    for s in scales:
        if s < 2:
            continue
        n_seg = N // s
        if n_seg < 2:
            continue
        rms = []
        for i in range(n_seg):
            seg = y[i * s:(i + 1) * s]
            t = np.arange(s)
            p = np.polyfit(t, seg, 1)
            trend = np.polyval(p, t)
            rms.append(np.sqrt(np.mean((seg - trend) ** 2)))
        F.append(np.mean(rms))
    if len(F) < 3:
        return np.nan
    scales_used = scales[:len(F)]
    logs = np.log(scales_used)
    logF = np.log(np.array(F) + 1e-12)
    slope, _ = np.polyfit(logs, logF, 1)
    return float(slope)


def dfa_alpha(x, w: int) -> pd.Series:
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: _dfa_alpha_1d(np.asarray(a, dtype=float)), raw=True)


def kaufman_efficiency_ratio(x, w: int) -> pd.Series:
    """|net change| / sum(|Δ|). ∈ [0,1]. Distinct from geometric.straightness
    in that it uses SIGNED cumulative displacement, whereas straightness
    uses absolute displacement over the same window — identical when the
    net move dominates but differs when the series reverses."""
    s = as_series(x)
    net = (s - s.shift(w)).abs()
    volm = s.diff().abs().rolling(w, min_periods=w).sum()
    return (net / volm.replace(0, np.nan)).clip(0, 1)


def _boxcount_fd_1d(x: np.ndarray, min_eps: int = 2) -> float:
    """Box-counting fractal dimension (capacity dimension) proxy for 1D time series."""
    N = len(x)
    if N < 4 * min_eps:
        return np.nan
    x_min, x_max = np.min(x), np.max(x)
    if x_min == x_max:
        return np.nan
        
    epsilons = np.unique(np.logspace(np.log10(min_eps), np.log10(N // 4), 6).astype(int))
    counts = []
    
    for eps in epsilons:
        if eps < 1:
            continue
        # number of horizontal boxes is N / eps
        n_h = N // eps
        boxes_this_eps = 0
        for i in range(n_h):
            seg = x[i*eps:(i+1)*eps]
            if len(seg) == 0: continue
            seg_min, seg_max = np.min(seg), np.max(seg)
            # number of vertical boxes required to cover this segment
            # vertical box size is scaled proportionally to horizontal
            v_scale = (x_max - x_min) / n_h
            if v_scale == 0: 
                boxes_this_eps += 1
            else:
                boxes_this_eps += max(1, int(np.ceil((seg_max - seg_min) / v_scale)))
        counts.append(boxes_this_eps)
        
    if len(counts) < 3:
        return np.nan
        
    log_eps = np.log(1.0 / epsilons[:len(counts)])
    log_N = np.log(counts)
    
    slope, _ = np.polyfit(log_eps, log_N, 1)
    return float(slope)


def boxcount_fd(x, w: int) -> pd.Series:
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: _boxcount_fd_1d(np.asarray(a, dtype=float)), raw=True)

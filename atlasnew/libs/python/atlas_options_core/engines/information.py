"""Information Engine — information-theoretic complexity measures."""
from __future__ import annotations
import numpy as np
import pandas as pd
from math import factorial
from atlas_core.engines.rolling import as_series


def _perm_entropy_1d(x: np.ndarray, order: int = 3, delay: int = 1) -> float:
    """Permutation entropy (Bandt-Pompe) — normalized to [0,1]."""
    n = len(x) - (order - 1) * delay
    if n <= 0:
        return np.nan
    perms = {}
    for i in range(n):
        vec = tuple(np.argsort(x[i:i + order * delay:delay]))
        perms[vec] = perms.get(vec, 0) + 1
    counts = np.array(list(perms.values()), dtype=float)
    p = counts / counts.sum()
    H = -np.sum(p * np.log(p))
    return float(H / np.log(factorial(order)))


def permutation_entropy(x, w: int, order: int = 3) -> pd.Series:
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: _perm_entropy_1d(np.asarray(a, dtype=float), order), raw=True)


def _sample_entropy_1d(x: np.ndarray, m: int = 2, r: float = 0.2) -> float:
    N = len(x)
    if N < m + 2:
        return np.nan
    r_ = r * np.std(x, ddof=1)
    if r_ == 0:
        return np.nan

    def _phi(mm):
        templates = np.lib.stride_tricks.sliding_window_view(x, mm)
        diffs = np.max(np.abs(templates[:, None, :] - templates[None, :, :]), axis=2)
        return np.sum(diffs <= r_) - len(templates)  # exclude self

    B = _phi(m)
    A = _phi(m + 1)
    if A == 0 or B == 0:
        return np.nan
    return float(-np.log(A / B))


def sample_entropy(x, w: int, m: int = 2, r: float = 0.2) -> pd.Series:
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: _sample_entropy_1d(np.asarray(a, dtype=float), m, r), raw=True)


def _approx_entropy_1d(x: np.ndarray, m: int = 2, r: float = 0.2) -> float:
    N = len(x)
    if N < m + 2:
        return np.nan
    r_ = r * np.std(x, ddof=1)
    if r_ == 0:
        return np.nan

    def _phi(mm):
        templates = np.lib.stride_tricks.sliding_window_view(x, mm)
        diffs = np.max(np.abs(templates[:, None, :] - templates[None, :, :]), axis=2)
        C = np.sum(diffs <= r_, axis=1) / len(templates)
        return np.mean(np.log(C + 1e-12))

    return float(_phi(m) - _phi(m + 1))


def approximate_entropy(x, w: int, m: int = 2, r: float = 0.2) -> pd.Series:
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: _approx_entropy_1d(np.asarray(a, dtype=float), m, r), raw=True)


def renyi_entropy(x, w: int, alpha: float = 2.0, bins: int = 10) -> pd.Series:
    """Rényi entropy of order α. Reduces to Shannon at α=1."""
    s = as_series(x)
    def _re(a):
        hist, _ = np.histogram(a, bins=bins)
        p = hist / hist.sum() if hist.sum() else hist
        p = p[p > 0]
        if len(p) == 0:
            return np.nan
        if abs(alpha - 1.0) < 1e-9:
            return float(-np.sum(p * np.log(p)))
        return float(np.log(np.sum(p ** alpha)) / (1 - alpha))
    return s.rolling(w, min_periods=w).apply(_re, raw=True)


def tsallis_entropy(x, w: int, q: float = 2.0, bins: int = 10) -> pd.Series:
    """Tsallis entropy of order q — non-additive generalization of Shannon."""
    s = as_series(x)
    def _te(a):
        hist, _ = np.histogram(a, bins=bins)
        p = hist / hist.sum() if hist.sum() else hist
        p = p[p > 0]
        if len(p) == 0 or abs(q - 1.0) < 1e-9:
            return np.nan
        return float((1 - np.sum(p ** q)) / (q - 1))
    return s.rolling(w, min_periods=w).apply(_te, raw=True)


def _lz_complexity_1d(x: np.ndarray) -> float:
    """Lempel-Ziv complexity of the median-binarized series."""
    med = np.median(x)
    s = "".join("1" if v >= med else "0" for v in x)
    n = len(s)
    if n < 4:
        return np.nan
    i, C, u, v, vmax = 0, 1, 1, 1, 1
    while u + v <= n:
        if s[i + v - 1] == s[u + v - 1]:
            v += 1
        else:
            vmax = max(v, vmax)
            i += 1
            if i == u:
                C += 1
                u += vmax
                v = 1
                i = 0
                vmax = 1
            else:
                v = 1
    if v != 1:
        C += 1
    return float(C * (np.log2(n) / n))


def lz_complexity(x, w: int) -> pd.Series:
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: _lz_complexity_1d(np.asarray(a, dtype=float)), raw=True)


def zero_crossings(x, w: int) -> pd.Series:
    """Count of sign changes of the first difference within the window."""
    s = as_series(x)
    d = np.sign(s.diff()).fillna(0)
    flips = (d.diff().abs() > 1).astype(float)
    return flips.rolling(w, min_periods=w).sum()

"""L-moments Engine — probability-weighted moments (Hosking).

L-moments are linear combinations of order statistics; they characterize
a distribution more robustly than product-moments (mean/std/skew/kurt),
especially in heavy-tailed regimes like markets.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series


def _lmoments_1d(x: np.ndarray, k: int = 4) -> tuple:
    """Return (λ1, λ2, τ3, τ4) — first four L-moments and L-skew, L-kurt."""
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n < 4:
        return (np.nan,) * 4
    # b0, b1, b2, b3 (probability weighted moments)
    b = np.zeros(4)
    for r in range(4):
        num = 0.0
        for j in range(r, n):
            coef = 1.0
            for i in range(r):
                coef *= (j - i) / (n - 1 - i)
            num += coef * x[j]
        b[r] = num / n
    l1 = b[0]
    l2 = 2 * b[1] - b[0]
    l3 = 6 * b[2] - 6 * b[1] + b[0]
    l4 = 20 * b[3] - 30 * b[2] + 12 * b[1] - b[0]
    t3 = l3 / l2 if l2 != 0 else np.nan
    t4 = l4 / l2 if l2 != 0 else np.nan
    return (float(l1), float(l2), float(t3), float(t4))


def lmoment(x, w: int, which: int = 1) -> pd.Series:
    """which ∈ {1,2,3,4} → λ1, λ2, τ3 (L-skew), τ4 (L-kurt)."""
    s = as_series(x)
    return s.rolling(w, min_periods=w).apply(
        lambda a: _lmoments_1d(a)[which - 1], raw=True)

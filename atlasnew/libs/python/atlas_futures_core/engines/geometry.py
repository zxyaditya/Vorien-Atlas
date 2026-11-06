"""Geometry Engine — trajectory-level geometric properties.

Treats the price series as a 1D trajectory in time × value space.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series


def path_length(x, w: int) -> pd.Series:
    """Sum of |Δx| over the window — total distance traveled."""
    s = as_series(x)
    d = s.diff().abs()
    return d.rolling(w, min_periods=w).sum()


def displacement(x, w: int) -> pd.Series:
    """Net signed displacement over the window."""
    s = as_series(x)
    return s - s.shift(w)


def straightness(x, w: int) -> pd.Series:
    """|displacement| / path_length ∈ [0,1]. 1 = perfectly straight."""
    disp = displacement(x, w).abs()
    plen = path_length(x, w).replace(0, np.nan)
    return (disp / plen).clip(0, 1)


def curvature(x, w: int = 3) -> pd.Series:
    """Discrete curvature via second finite difference over a symmetric stencil."""
    s = as_series(x)
    return (s - 2.0 * s.shift(1) + s.shift(2))


def angular_change(x) -> pd.Series:
    """Angle between consecutive Δx vectors (radians)."""
    s = as_series(x)
    dx = s.diff()
    prev = dx.shift(1)
    # slope difference converted to angle
    return np.arctan(dx) - np.arctan(prev)


def trajectory_complexity(x, w: int) -> pd.Series:
    """Number of turning points (sign changes of Δx) inside the window."""
    s = as_series(x)
    sign = np.sign(s.diff()).fillna(0)
    flips = (sign.diff().abs() > 1).astype(float)
    return flips.rolling(w, min_periods=w).sum()

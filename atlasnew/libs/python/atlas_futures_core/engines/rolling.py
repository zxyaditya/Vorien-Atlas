"""Rolling Engine — window management, alignment, incremental scans.

All rolling ops return arrays of identical length to the input,
with NaN for warmup positions. This is a load-bearing invariant.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def as_series(x) -> pd.Series:
    if isinstance(x, pd.Series):
        return x
    return pd.Series(np.asarray(x, dtype=float))


def rolling_apply(x, window: int, func):
    """Generic rolling apply. Preserves length. NaN warmup."""
    s = as_series(x)
    return s.rolling(window=window, min_periods=window).apply(func, raw=True)


def rolling_window_view(x: np.ndarray, window: int) -> np.ndarray:
    """Efficient stride-tricks window view (read-only)."""
    x = np.ascontiguousarray(x, dtype=float)
    if len(x) < window:
        return np.empty((0, window))
    from numpy.lib.stride_tricks import sliding_window_view
    return sliding_window_view(x, window_shape=window)

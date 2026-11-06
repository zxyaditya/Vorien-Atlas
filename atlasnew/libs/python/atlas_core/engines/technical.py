"""Technical Primitives — EMA, True Range, ATR, Bollinger, Donchian, Keltner.

These are canonical composite primitives, not indicators-as-decisions.
They exist because many downstream features reuse them.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series
from atlas_core.engines.statistics import rolling_max, rolling_min, rolling_mean, rolling_std


def ema(x, span: int) -> pd.Series:
    """Exponential moving average with span (α = 2/(span+1))."""
    return as_series(x).ewm(span=span, adjust=False, min_periods=span).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr


def atr(df: pd.DataFrame, w: int) -> pd.Series:
    return true_range(df).rolling(w, min_periods=w).mean()


def bollinger_bands(x, w: int, k: float = 2.0):
    m = rolling_mean(x, w)
    s = rolling_std(x, w)
    return m + k * s, m, m - k * s


def bollinger_percent_b(x, w: int, k: float = 2.0) -> pd.Series:
    upper, _, lower = bollinger_bands(x, w, k)
    rng = (upper - lower).replace(0, np.nan)
    return (as_series(x) - lower) / rng


def bollinger_bandwidth(x, w: int, k: float = 2.0) -> pd.Series:
    upper, mid, lower = bollinger_bands(x, w, k)
    return (upper - lower) / mid.replace(0, np.nan)


def donchian_percent(x, w: int) -> pd.Series:
    hi, lo = rolling_max(x, w), rolling_min(x, w)
    rng = (hi - lo).replace(0, np.nan)
    return (as_series(x) - lo) / rng


def keltner_bands(df: pd.DataFrame, w: int, k: float = 1.5):
    mid = ema(df["close"], w)
    a = atr(df, w)
    return mid + k * a, mid, mid - k * a


def keltner_percent(df: pd.DataFrame, w: int, k: float = 1.5) -> pd.Series:
    upper, _, lower = keltner_bands(df, w, k)
    rng = (upper - lower).replace(0, np.nan)
    return (df["close"] - lower) / rng


def keltner_width(df: pd.DataFrame, w: int, k: float = 1.5) -> pd.Series:
    upper, mid, lower = keltner_bands(df, w, k)
    return (upper - lower) / mid.replace(0, np.nan)


def kaufman_ama(x, w: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    """Kaufman Adaptive Moving Average. ER-scaled EMA smoothing."""
    s = as_series(x)
    change = (s - s.shift(w)).abs()
    vol = s.diff().abs().rolling(w, min_periods=w).sum().replace(0, np.nan)
    er = change / vol
    sc = (er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)) ** 2
    ama = s.copy() * np.nan
    for i in range(w, len(s)):
        prev = ama.iloc[i - 1] if not np.isnan(ama.iloc[i - 1]) else s.iloc[i - 1]
        ama.iloc[i] = prev + sc.iloc[i] * (s.iloc[i] - prev)
    return ama


def chande_momentum(x, w: int) -> pd.Series:
    """(sum(+Δ) - sum(-Δ)) / (sum(+Δ) + sum(-Δ)) ∈ [-1,1]."""
    d = as_series(x).diff()
    up = d.clip(lower=0).rolling(w, min_periods=w).sum()
    dn = (-d.clip(upper=0)).rolling(w, min_periods=w).sum()
    total = (up + dn).replace(0, np.nan)
    return (up - dn) / total


def ulcer_index(x, w: int) -> pd.Series:
    """RMS of the drawdown-from-max over the window."""
    s = as_series(x)
    def _u(a):
        peak = np.maximum.accumulate(a)
        dd = (a - peak) / peak
        return float(np.sqrt(np.mean(dd ** 2)))
    return s.rolling(w, min_periods=w).apply(_u, raw=True)


def choppiness_index(df: pd.DataFrame, w: int) -> pd.Series:
    """log10(sum(TR) / range) / log10(w). ∈ [0,1]. High = choppy."""
    tr = true_range(df).rolling(w, min_periods=w).sum()
    rng = (rolling_max(df["high"], w) - rolling_min(df["low"], w)).replace(0, np.nan)
    return np.log10(tr / rng) / np.log10(w)

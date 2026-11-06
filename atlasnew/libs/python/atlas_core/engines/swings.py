"""Swings Engine — pivot/swing detection and structural primitives.

A swing is a local extremum confirmed by k neighbours on each side.
Everything else in Market Structure (HH/HL/LH/LL, BOS, CHoCH, break
strength, swing persistence, structure regime) is derived from these
primitives.

Domain-neutral: works on any numeric series. Does not know 'high' vs
'low' — the module supplies the right series.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series


def pivot_high(high, k: int) -> pd.Series:
    """1.0 where high[i] is the strict maximum of high[i-k .. i+k]; 0 else.
    The result is aligned to bar i (the pivot bar), but is only KNOWN k
    bars later. Callers wanting a causal series should use
    `confirmed_pivot_high` which shifts the flag forward by k.
    """
    h = as_series(high)
    w = 2 * k + 1
    if len(h) < w:
        return pd.Series(np.zeros(len(h)), index=h.index, dtype=float)
    center = h.rolling(w, center=True, min_periods=w).max()
    flag = ((h == center) & h.notna()).astype(float)
    # break ties: only the leftmost peak in a plateau counts
    left_max = h.rolling(k + 1, min_periods=1).max()
    flag = flag * (h >= left_max).astype(float)
    return flag


def pivot_low(low, k: int) -> pd.Series:
    l = as_series(low)
    w = 2 * k + 1
    if len(l) < w:
        return pd.Series(np.zeros(len(l)), index=l.index, dtype=float)
    center = l.rolling(w, center=True, min_periods=w).min()
    flag = ((l == center) & l.notna()).astype(float)
    left_min = l.rolling(k + 1, min_periods=1).min()
    flag = flag * (l <= left_min).astype(float)
    return flag


def confirmed_pivot_high(high, k: int) -> pd.Series:
    """Causal version — the pivot at bar i is only known at bar i+k."""
    return pivot_high(high, k).shift(k)


def confirmed_pivot_low(low, k: int) -> pd.Series:
    return pivot_low(low, k).shift(k)


def last_swing_value(series, pivot_flag) -> pd.Series:
    """Given a series and a 0/1 pivot flag, forward-fill the last pivot value.
    Result at bar t is the most recent value where pivot_flag was 1 (causal).
    """
    s = as_series(series)
    f = as_series(pivot_flag)
    picked = s.where(f > 0.5, np.nan)
    return picked.ffill()


def last_swing_index(pivot_flag) -> pd.Series:
    """Bars-since-last-pivot. NaN before the first pivot occurs."""
    f = as_series(pivot_flag)
    idx = pd.Series(np.arange(len(f), dtype=float), index=f.index)
    picked = idx.where(f > 0.5, np.nan).ffill()
    return idx - picked


def swing_sequence(series, pivot_flag, keep: int = 4) -> pd.DataFrame:
    """Return the last `keep` swing values as columns swing_{-1}..swing_{-keep}.
    Causal — only pivots strictly before / at the current bar.
    """
    s = as_series(series)
    f = as_series(pivot_flag)
    vals = s.where(f > 0.5, np.nan)
    out = {}
    prev = vals.ffill()
    out["swing_1"] = prev
    for i in range(2, keep + 1):
        prev = prev.where(f.shift(sum(1 for _ in range(i-1))) < 0.5, np.nan)
        # Simpler: recover by shifting the non-NaN sequence
    # Simpler correct implementation: compact non-NaN then align
    v = vals.values
    n = len(v)
    hist = np.full((keep, n), np.nan)
    stack = []
    for i in range(n):
        if not np.isnan(v[i]):
            stack.append(v[i])
        for j in range(keep):
            if len(stack) > j:
                hist[j, i] = stack[-1 - j]
    cols = {f"swing_{j+1}": hist[j] for j in range(keep)}
    return pd.DataFrame(cols, index=s.index)


def break_of_structure(close, swing_high_val, swing_low_val) -> pd.Series:
    """+1 when close breaks the last confirmed swing high;
    -1 when close breaks the last confirmed swing low; 0 otherwise."""
    c = as_series(close)
    up = (c > swing_high_val).astype(float)
    dn = (c < swing_low_val).astype(float)
    return up - dn


def break_strength(close, ref_swing, atr) -> pd.Series:
    """(close - ref_swing) / ATR — positive on upside break, negative on downside.
    ref_swing is meant to be last_swing_value of highs (for upside checks) or
    lows (for downside). Caller decides.
    """
    c = as_series(close)
    r = as_series(ref_swing)
    a = as_series(atr).replace(0, np.nan)
    return (c - r) / a


def higher_high(swing_hist: pd.DataFrame) -> pd.Series:
    """1 when swing_1 > swing_2 among highs; 0 otherwise."""
    return (swing_hist["swing_1"] > swing_hist["swing_2"]).astype(float)


def lower_high(swing_hist: pd.DataFrame) -> pd.Series:
    return (swing_hist["swing_1"] < swing_hist["swing_2"]).astype(float)


def higher_low(swing_hist: pd.DataFrame) -> pd.Series:
    return (swing_hist["swing_1"] > swing_hist["swing_2"]).astype(float)


def lower_low(swing_hist: pd.DataFrame) -> pd.Series:
    return (swing_hist["swing_1"] < swing_hist["swing_2"]).astype(float)


def structure_regime(hh: pd.Series, hl: pd.Series,
                     lh: pd.Series, ll: pd.Series) -> pd.Series:
    """+1 bullish structure (HH and HL), -1 bearish (LH and LL), 0 mixed."""
    bull = ((hh > 0.5) & (hl > 0.5)).astype(float)
    bear = ((lh > 0.5) & (ll > 0.5)).astype(float)
    return bull - bear


def change_of_character(regime: pd.Series) -> pd.Series:
    """1 where the structure regime flips sign vs the previous non-zero regime.
    A canonical CHoCH detector.
    """
    r = as_series(regime).replace(0, np.nan).ffill().fillna(0)
    flip = ((r * r.shift(1)) < 0).astype(float)
    return flip


def swing_persistence(pivot_flag, w: int) -> pd.Series:
    """Fraction of the window that has been 'since' the last pivot.
    High values → structure is stale; low values → structure is turning fast.
    """
    since = last_swing_index(pivot_flag)
    return (since.rolling(w, min_periods=1).mean() / max(w, 1)).clip(0, 1)

"""L3 State Kernel — the six primitives that produce every L3 shape.

DEC-015 (v0.8.0):
  These primitives are structural, market-agnostic, and L3-local. They
  are NOT promoted to `atlas_core.engines` until reuse is observed in
  L4 (Book 1 Ch. 10 discovery discipline).

Every L3 feature is one of six shapes:
    score       — pd.Series in [0, 1]
    flag        — pd.Series in {0, 1}
    duration    — pd.Series in ℕ (consecutive-on bar count)
    transition  — pd.Series in {-1, 0, +1} (exit / no-change / entry)
    confidence  — pd.Series in [0, 1]
    active_code — pd.Series in ℤ ≥ 0 (winner-take-all per family)

See docs/L3_MARKET_UNDERSTANDING.md §3 for the grammar.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Iterable, Sequence

EPS = 1e-12


def _to_series(x, index) -> pd.Series:
    if isinstance(x, pd.Series):
        s = x.astype(float)
    else:
        s = pd.Series(np.asarray(x, dtype=float))
    if len(s) == len(index):
        s.index = index
    return s


def weighted_score(evidence: Dict[str, pd.Series],
                   weights: Dict[str, float]) -> pd.Series:
    """Weighted, sign-preserving evidence aggregation → [0, 1].

    Each evidence series is first squashed into [0, 1] via `_to_unit`
    (identity if already unit-scaled and finite, sigmoid otherwise).
    Weights are normalised to sum to 1 across the *finite* evidence
    channels at each bar so a missing channel does not bias the score.
    NaN in an evidence channel is treated as missing (drops from the
    normalisation), not as zero.
    """
    if not evidence:
        return pd.Series(dtype=float)
    keys = list(evidence.keys())
    idx = None
    for k in keys:
        if isinstance(evidence[k], pd.Series):
            idx = evidence[k].index
            break
    if idx is None:
        idx = pd.RangeIndex(len(next(iter(evidence.values()))))

    unit = {k: _to_unit(_to_series(evidence[k], idx)) for k in keys}
    W = np.array([float(weights.get(k, 0.0)) for k in keys], dtype=float)
    if W.sum() <= 0:
        W = np.ones_like(W) / max(len(W), 1)

    M = np.column_stack([unit[k].values for k in keys])  # (T, K)
    mask = np.isfinite(M)
    Wr = np.tile(W, (M.shape[0], 1))
    Wr = np.where(mask, Wr, 0.0)
    Wsum = Wr.sum(axis=1)
    num = np.where(mask, M * Wr, 0.0).sum(axis=1)
    score = np.where(Wsum > EPS, num / np.where(Wsum > EPS, Wsum, 1.0), np.nan)
    return pd.Series(np.clip(score, 0.0, 1.0), index=idx, dtype=float)


def _to_unit(s: pd.Series) -> pd.Series:
    """Squash a series into [0, 1] with light-touch mapping:

    * if already inside [0, 1] almost everywhere (>= 95% of finite
      values in [0, 1]) → passthrough with clip.
    * else if signed (min < 0) → 0.5 + 0.5 * tanh(x)
    * else → x / (1 + x)  (positive-scaled)

    NaN is preserved.
    """
    x = s.values.astype(float)
    finite = np.isfinite(x)
    if not finite.any():
        return s
    xf = x[finite]
    in_unit = float(((xf >= 0.0) & (xf <= 1.0)).mean())
    if in_unit >= 0.95:
        y = np.clip(x, 0.0, 1.0)
        y[~finite] = np.nan
        return pd.Series(y, index=s.index)
    if float(xf.min()) < 0.0:
        y = 0.5 + 0.5 * np.tanh(x)
    else:
        y = x / (1.0 + np.abs(x))
    y = np.where(finite, y, np.nan)
    return pd.Series(y, index=s.index)


def hysteresis_flag(score: pd.Series, on: float, off: float) -> pd.Series:
    """Chatter-free 0/1 flag from a score series.

    Turns on when score >= `on`, stays on until score <= `off`. Requires
    on > off (strict) — asserted. NaN input preserves the previous state
    (does not flip the flag).
    """
    assert on > off, f"hysteresis requires on > off, got on={on} off={off}"
    x = score.values.astype(float)
    n = len(x)
    y = np.zeros(n, dtype=float)
    state = 0
    for i in range(n):
        v = x[i]
        if not np.isfinite(v):
            y[i] = state
            continue
        if state == 0 and v >= on:
            state = 1
        elif state == 1 and v <= off:
            state = 0
        y[i] = state
    return pd.Series(y, index=score.index, dtype=float)


def duration(flag: pd.Series) -> pd.Series:
    """Consecutive-on bar count. 0 while flag=0; increments while flag=1."""
    x = (flag.values > 0.5).astype(int)
    n = len(x)
    y = np.zeros(n, dtype=float)
    run = 0
    for i in range(n):
        run = run + 1 if x[i] == 1 else 0
        y[i] = run
    return pd.Series(y, index=flag.index, dtype=float)


def transition(flag: pd.Series) -> pd.Series:
    """+1 on the bar the flag turns on; -1 on the bar it turns off; else 0."""
    x = (flag.values > 0.5).astype(int)
    n = len(x)
    y = np.zeros(n, dtype=float)
    for i in range(1, n):
        d = x[i] - x[i - 1]
        y[i] = 1.0 if d == 1 else (-1.0 if d == -1 else 0.0)
    return pd.Series(y, index=flag.index, dtype=float)


def agreement_confidence(evidence_signs: Iterable[pd.Series]) -> pd.Series:
    """|mean(sign(evidence))| ∈ [0, 1]. NaN inputs drop from the mean."""
    seq = list(evidence_signs)
    if not seq:
        return pd.Series(dtype=float)
    idx = seq[0].index
    M = np.column_stack([np.sign(np.asarray(s.reindex(idx).values, dtype=float))
                         for s in seq])
    mask = np.isfinite(M)
    ct = mask.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        m = np.where(ct > 0, np.nansum(M * mask.astype(float), axis=1) / np.where(ct > 0, ct, 1), np.nan)
    return pd.Series(np.abs(m), index=idx, dtype=float)


def winner_take_all(scores: Dict[str, pd.Series],
                    priority: Sequence[str] = ()) -> Dict[str, pd.Series]:
    """Exclusive classification across a family of scores.

    Returns a dict with:
      "<state>_flag"   : 0/1 series per state (mutual exclusivity).
      "active_code"    : integer code 1..K for the winner (0 if no score
                         is finite and > 0.5 — i.e. no state clearly
                         holds).

    Ties are broken by ``priority`` order (first listed wins).
    """
    if not scores:
        return {"active_code": pd.Series(dtype=float)}
    names = list(scores.keys())
    idx = scores[names[0]].index
    M = np.column_stack([np.asarray(scores[n].reindex(idx).values, dtype=float)
                         for n in names])
    order = [n for n in priority if n in names] + [n for n in names if n not in priority]
    reorder_idx = [names.index(n) for n in order]
    M_re = M[:, reorder_idx]
    # Argmax per row over reordered priority; ties are broken by earlier position.
    finite = np.isfinite(M_re)
    Msafe = np.where(finite, M_re, -np.inf)
    winner_pos = np.argmax(Msafe, axis=1)
    winner_val = Msafe[np.arange(len(idx)), winner_pos]
    # Only assign a state when the winning score >= 0.5 AND at least one channel finite.
    active = np.where((winner_val >= 0.5) & np.isfinite(winner_val), winner_pos + 1, 0)
    out: Dict[str, pd.Series] = {}
    for i, nm in enumerate(order):
        out[f"{nm}_flag"] = pd.Series((active == (i + 1)).astype(float),
                                       index=idx, dtype=float)
    out["active_code"] = pd.Series(active.astype(float), index=idx, dtype=float)
    # order lookup so DE / tests can decode the code:
    out["_order"] = order  # type: ignore[assignment]
    return out


def zscore_clip(s: pd.Series, lookback: int = 100, clip: float = 3.0) -> pd.Series:
    """Rolling z-score of s clipped to [-clip, clip], then mapped to [0, 1].

    Handles constant windows by returning 0.5 (neutral).
    """
    r = s.rolling(lookback, min_periods=max(5, lookback // 4))
    mu = r.mean()
    sd = r.std(ddof=0)
    z = (s - mu) / sd.replace(0.0, np.nan)
    z = z.clip(-clip, clip)
    return (z / (2.0 * clip) + 0.5).fillna(0.5).astype(float)


def sigmoid(s: pd.Series, gain: float = 1.0) -> pd.Series:
    """Standard logistic squash → [0, 1]. NaN preserved."""
    x = s.values.astype(float)
    y = 1.0 / (1.0 + np.exp(-gain * np.where(np.isfinite(x), x, 0.0)))
    y = np.where(np.isfinite(x), y, np.nan)
    return pd.Series(y, index=s.index, dtype=float)

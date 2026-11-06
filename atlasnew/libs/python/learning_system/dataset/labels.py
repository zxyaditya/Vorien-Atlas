"""Label Generation — four deterministic label kinds.

  - sign            : signum of forward log-return (canonical binary label)
  - quantile        : top / bottom terciles of forward return (drops middle)
  - vol_norm        : forward return normalised by rolling ATR% (±1)
  - triple_barrier  : López de Prado triple barrier (± kσ ATR × horizon)

All functions return `(y, valid_mask)` where `y` is a pandas Series aligned
to `df.index` with dtype int8 (0/1 for binary, -1/+1 for balanced), and
`valid_mask` marks the rows where the label is well-defined (i.e. the last
`horizon` bars are dropped, plus any bars that fail the barrier definition).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Callable, Dict, Tuple, Optional

LABEL_KINDS: Dict[str, Callable] = {}


def _register(name: str):
    def deco(fn):
        LABEL_KINDS[name] = fn
        return fn
    return deco


def _forward_log_return(df: pd.DataFrame, horizon: int) -> np.ndarray:
    close = df["close"].astype(float).values
    fwd = np.log(np.roll(close, -horizon) / close)
    fwd[-horizon:] = np.nan
    return fwd


@_register("sign")
def label_sign(df: pd.DataFrame, horizon: int, **_) -> Tuple[pd.Series, pd.Series]:
    fwd = _forward_log_return(df, horizon)
    y = np.where(fwd > 0, 1, np.where(fwd < 0, 0, 1))  # ties → up
    valid = np.isfinite(fwd)
    return (pd.Series(y.astype(np.int8), index=df.index),
            pd.Series(valid, index=df.index))


@_register("quantile")
def label_quantile(df: pd.DataFrame, horizon: int,
                    q_low: float = 1/3, q_high: float = 2/3, **_
                    ) -> Tuple[pd.Series, pd.Series]:
    """Top / bottom terciles: 1 = top, 0 = bottom, middle = invalid."""
    fwd = _forward_log_return(df, horizon)
    finite = fwd[np.isfinite(fwd)]
    if len(finite) < 30:
        return (pd.Series(np.zeros(len(df), dtype=np.int8), index=df.index),
                pd.Series(np.zeros(len(df), dtype=bool), index=df.index))
    lo = float(np.quantile(finite, q_low))
    hi = float(np.quantile(finite, q_high))
    y = np.zeros_like(fwd, dtype=np.int8)
    valid = np.zeros_like(fwd, dtype=bool)
    top_mask = np.isfinite(fwd) & (fwd >= hi)
    bot_mask = np.isfinite(fwd) & (fwd <= lo)
    y[top_mask] = 1
    y[bot_mask] = 0
    valid[top_mask | bot_mask] = True
    return (pd.Series(y, index=df.index), pd.Series(valid, index=df.index))


def _atr_percent(df: pd.DataFrame, window: int = 14) -> np.ndarray:
    high = df["high"].astype(float).values
    low = df["low"].astype(float).values
    close = df["close"].astype(float).values
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(high - low,
                    np.maximum(np.abs(high - prev_close),
                               np.abs(low - prev_close)))
    atr = pd.Series(tr).rolling(window, min_periods=window).mean().values
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(close > 0, atr / close, np.nan)


@_register("vol_norm")
def label_vol_norm(df: pd.DataFrame, horizon: int,
                    atr_window: int = 14, thresh: float = 0.25, **_
                    ) -> Tuple[pd.Series, pd.Series]:
    """Sign of (fwd_return / rolling ATR%). Threshold to filter noise.

    Row valid iff |fwd / atr%| > `thresh`, so the model only sees
    unambiguous moves.
    """
    fwd = _forward_log_return(df, horizon)
    atrp = _atr_percent(df, atr_window)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(atrp > 0, fwd / atrp, np.nan)
    y = np.where(z > 0, 1, 0).astype(np.int8)
    valid = np.isfinite(z) & (np.abs(z) >= thresh)
    return pd.Series(y, index=df.index), pd.Series(valid, index=df.index)


@_register("triple_barrier")
def label_triple_barrier(df: pd.DataFrame, horizon: int,
                          atr_window: int = 14, k_upper: float = 2.0,
                          k_lower: float = 2.0, **_
                          ) -> Tuple[pd.Series, pd.Series]:
    """López-de-Prado triple barrier.

    From each bar t, define upper = close[t] * (1 + k_upper * ATR%),
    lower = close[t] * (1 - k_lower * ATR%). Walk forward up to `horizon`
    bars. The first barrier hit determines the label. If neither is hit
    within the horizon, label by the sign of the final return.

    Label: 1 = upper first, 0 = lower first, ties broken by close move.
    Bars invalid iff we cannot look forward `horizon` bars OR ATR is NaN.
    """
    close = df["close"].astype(float).values
    high = df["high"].astype(float).values
    low = df["low"].astype(float).values
    atrp = _atr_percent(df, atr_window)
    n = len(df)
    y = np.zeros(n, dtype=np.int8)
    valid = np.zeros(n, dtype=bool)
    for i in range(n - horizon):
        if not np.isfinite(atrp[i]) or atrp[i] <= 0:
            continue
        u = close[i] * (1.0 + k_upper * atrp[i])
        d = close[i] * (1.0 - k_lower * atrp[i])
        stop = min(n, i + horizon + 1)
        hit_up = None
        hit_dn = None
        for j in range(i + 1, stop):
            if hit_up is None and high[j] >= u:
                hit_up = j
            if hit_dn is None and low[j] <= d:
                hit_dn = j
            if hit_up is not None and hit_dn is not None:
                break
        if hit_up is not None and (hit_dn is None or hit_up < hit_dn):
            y[i] = 1
            valid[i] = True
        elif hit_dn is not None and (hit_up is None or hit_dn < hit_up):
            y[i] = 0
            valid[i] = True
        else:
            # Neither barrier hit — vertical (time) barrier: label by sign
            if i + horizon < n:
                end = i + horizon
                y[i] = 1 if close[end] > close[i] else 0
                valid[i] = True
            else:
                valid[i] = False
    return pd.Series(y, index=df.index), pd.Series(valid, index=df.index)


@_register("regime_triple_barrier")
def label_regime_triple_barrier(df: pd.DataFrame, horizon: int,
                                atr_window: int = 14,
                                t_quiet: Optional[pd.Series] = None,
                                t_vol: Optional[pd.Series] = None,
                                t_breakout: Optional[pd.Series] = None,
                                **_) -> Tuple[pd.Series, pd.Series]:
    """Regime-Conditional Triple Barrier.
    
    Dynamically adjusts barrier width and horizon based on L3 regime.
    """
    close = df["close"].astype(float).values
    high = df["high"].astype(float).values
    low = df["low"].astype(float).values
    atrp = _atr_percent(df, atr_window)
    n = len(df)
    y = np.zeros(n, dtype=np.int8)
    valid = np.zeros(n, dtype=bool)
    
    q_arr = t_quiet.values if t_quiet is not None else np.zeros(n)
    v_arr = t_vol.values if t_vol is not None else np.zeros(n)
    b_arr = t_breakout.values if t_breakout is not None else np.zeros(n)
    
    for i in range(n):
        if not np.isfinite(atrp[i]) or atrp[i] <= 0:
            continue
            
        if q_arr[i] == 1:
            k_upper, k_lower, dyn_horizon = 1.2, 1.2, 10
        elif v_arr[i] == 1 or b_arr[i] == 1:
            k_upper, k_lower, dyn_horizon = 2.5, 2.5, 4
        else:
            k_upper, k_lower, dyn_horizon = 2.0, 2.0, horizon
            
        if i >= n - dyn_horizon:
            continue
            
        u = close[i] * (1.0 + k_upper * atrp[i])
        d = close[i] * (1.0 - k_lower * atrp[i])
        stop = min(n, i + dyn_horizon + 1)
        hit_up = None
        hit_dn = None
        for j in range(i + 1, stop):
            if hit_up is None and high[j] >= u:
                hit_up = j
            if hit_dn is None and low[j] <= d:
                hit_dn = j
            if hit_up is not None and hit_dn is not None:
                break
        if hit_up is not None and (hit_dn is None or hit_up < hit_dn):
            y[i] = 1
            valid[i] = True
        elif hit_dn is not None and (hit_up is None or hit_dn < hit_up):
            y[i] = 0
            valid[i] = True
        else:
            if i + dyn_horizon < n:
                end = i + dyn_horizon
                y[i] = 1 if close[end] > close[i] else 0
                valid[i] = True
            else:
                valid[i] = False
    return pd.Series(y, index=df.index), pd.Series(valid, index=df.index)


def generate_labels(df: pd.DataFrame, kind: str, horizon: int,
                     **params) -> Tuple[pd.Series, pd.Series]:
    if kind not in LABEL_KINDS:
        raise ValueError(
            f"unknown label kind {kind!r}; known: {list(LABEL_KINDS)}"
        )
    return LABEL_KINDS[kind](df, horizon=horizon, **params)

"""Options Label Generation.

Defines the target variables for ML options models:
- IV direction (expand/crush)
- Call/Put theoretical PnL
- Expiration probability
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Callable, Dict, Tuple


LABEL_KINDS: Dict[str, Callable] = {}

def _register(name: str):
    def deco(fn):
        LABEL_KINDS[name] = fn
        return fn
    return deco


@_register("iv_direction")
def label_iv_direction(chain_ts_df: pd.DataFrame, horizon: int, **_) -> Tuple[pd.Series, pd.Series]:
    """1 if ATM IV increases over the horizon, 0 otherwise."""
    # Assuming chain_ts_df contains a time-series of extracted features including 'atm_iv'
    if "atm_iv" not in chain_ts_df.columns:
        raise ValueError("atm_iv column required for iv_direction label")
    
    iv = chain_ts_df["atm_iv"].astype(float).values
    fwd_iv_diff = np.roll(iv, -horizon) - iv
    fwd_iv_diff[-horizon:] = np.nan
    
    y = np.where(fwd_iv_diff > 0, 1, 0)
    valid = np.isfinite(fwd_iv_diff)
    return (pd.Series(y.astype(np.int8), index=chain_ts_df.index),
            pd.Series(valid, index=chain_ts_df.index))


@_register("vol_crush")
def label_vol_crush(chain_ts_df: pd.DataFrame, horizon: int, threshold: float = -0.05, **_) -> Tuple[pd.Series, pd.Series]:
    """1 if IV drops by more than `threshold` (e.g. -5% absolute)."""
    if "atm_iv" not in chain_ts_df.columns:
        raise ValueError("atm_iv column required for vol_crush label")
    
    iv = chain_ts_df["atm_iv"].astype(float).values
    fwd_iv_diff = np.roll(iv, -horizon) - iv
    fwd_iv_diff[-horizon:] = np.nan
    
    y = np.where(fwd_iv_diff < threshold, 1, 0)
    valid = np.isfinite(fwd_iv_diff)
    return (pd.Series(y.astype(np.int8), index=chain_ts_df.index),
            pd.Series(valid, index=chain_ts_df.index))


@_register("spot_direction")
def label_spot_direction(spot_close: pd.Series, horizon: int, **_) -> Tuple[pd.Series, pd.Series]:
    """1 if underlying spot price increases over horizon, 0 otherwise."""
    close = spot_close.astype(float).values
    fwd = np.log(np.roll(close, -horizon) / close)
    fwd[-horizon:] = np.nan
    
    y = np.where(fwd > 0, 1, 0)
    valid = np.isfinite(fwd)
    return (pd.Series(y.astype(np.int8), index=spot_close.index),
            pd.Series(valid, index=spot_close.index))


def generate_labels(chain_ts_df: pd.DataFrame, spot_close: pd.Series,
                      kind: str, horizon: int, **params) -> Tuple[pd.Series, pd.Series]:
    """Router for label generation."""
    if kind == "spot_direction":
        return LABEL_KINDS[kind](spot_close, horizon, **params)
    if kind not in LABEL_KINDS:
        raise ValueError(f"Unknown label kind {kind}")
    return LABEL_KINDS[kind](chain_ts_df, horizon, **params)

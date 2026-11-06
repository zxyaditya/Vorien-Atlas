"""Liquidity Engine — Corwin-Schultz Spread Estimator."""
from __future__ import annotations

import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series

def corwin_schultz_spread(high: np.ndarray, low: np.ndarray, w: int = 14) -> pd.Series:
    """Estimate effective bid-ask spread from High/Low prices."""
    h = as_series(high)
    l = as_series(low)
    
    # Single day squared range
    hl_sq = (np.log(h / l) ** 2)
    
    # β_t: sum of 2 consecutive days of hl_sq
    beta_t = hl_sq.rolling(2).sum()
    
    # γ_t: Two period max-min squared range
    h2 = h.rolling(2).max()
    l2 = l.rolling(2).min()
    gamma_t = (np.log(h2 / l2) ** 2)
    
    # α = (sqrt(2β) - sqrt(γ)) / (3 - 2*sqrt(2))
    denom = 3 - 2 * np.sqrt(2)
    alpha = (np.sqrt(2 * beta_t) - np.sqrt(gamma_t)) / denom
    alpha = alpha.clip(lower=0)
    
    # S = 2*(e^alpha - 1)/(1 + e^alpha)
    s = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    
    # Smooth the spread estimate over window w
    return s.rolling(w).mean().fillna(0.0)

def amihud_illiquidity(close: np.ndarray, open_: np.ndarray, volume: np.ndarray, w: int = 14) -> pd.Series:
    """Amihud Illiquidity Ratio: |R| / (V * P)"""
    c = as_series(close)
    o = as_series(open_)
    v = as_series(volume)
    
    r = np.abs(np.log(c / o.replace(0, np.nan)))
    dollar_vol = v * c
    
    illiq = r / dollar_vol.replace(0, np.nan)
    return illiq.rolling(w).mean().fillna(0.0)

def roll_measure(close: np.ndarray, w: int = 20) -> pd.Series:
    """Roll Measure: 2 * -Cov(dP_t, dP_{t-1})."""
    c = as_series(close)
    dp = c.diff()
    dp_prev = dp.shift(1)
    
    cov = dp.rolling(w).cov(dp_prev)
    roll = 2.0 * -cov
    roll[cov >= 0] = 0.0
    return roll.fillna(0.0)

def kyles_lambda(close: np.ndarray, open_: np.ndarray, volume: np.ndarray, w: int = 20) -> pd.Series:
    """Kyle's Lambda: Rolling regression of |R| on SV (Signed Volume)."""
    c = as_series(close)
    o = as_series(open_)
    v = as_series(volume)
    
    abs_r = np.abs(np.log(c / o.replace(0, np.nan)))
    sv = v * np.sign(c - o)
    
    cov = abs_r.rolling(w).cov(sv)
    var = sv.rolling(w).var()
    
    lam = cov / var.replace(0, np.nan)
    return lam.fillna(0.0)

def microstructure_invariant(close: np.ndarray, volume: np.ndarray, w: int = 20) -> pd.Series:
    """Trading Activity Invariant (W) = V * P * sigma."""
    c = as_series(close)
    v = as_series(volume)
    
    ret = np.log(c / c.shift(1).replace(0, np.nan))
    sigma = ret.rolling(w).std()
    
    W = v * c * sigma
    return W.fillna(0.0)

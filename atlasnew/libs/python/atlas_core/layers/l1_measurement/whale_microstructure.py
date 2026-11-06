"""Whale Microstructure Module — Layer 1.

Ports proprietary macro-swing indicators from Whale Hunter (e.g. OFI, Amihud, 
Hawkes residuals, Roll's Spread, GSI, VPIN).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
# Backwards compatibility: skip formal FeatureValidation so it's auto-generated or skipped
from atlas_core.engines import flow_proxy as fp

MODULE = "whale_microstructure"

def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["open", "high", "low", "close", "volume"],
        params=params or {}, complexity=complexity, fn=fn
    ))

def _ofi(df):
    """Proxy Order Flow Imbalance using signed body and volume."""
    body = df['close'] - df['open']
    rng = df['high'] - df['low']
    # If range is 0, OFI is 0. Else, ratio of body to range times volume.
    ofi = np.where(rng > 0, (body / rng) * df['volume'], 0.0)
    return pd.Series(ofi, index=df.index).fillna(0)

def _va_ofi(df, window=10):
    ofi = _ofi(df)
    rets = df['close'].pct_change().fillna(0)
    micro_vol = rets.rolling(window, min_periods=1).std().fillna(1e-8)
    return (ofi / (micro_vol + 1e-8)).fillna(0)

def _amihud(df, window=10):
    """Amihud Illiquidity Ratio."""
    rets = df['close'].pct_change().abs().fillna(0)
    vol = df['volume'].replace(0, 1e-8)
    ratio = rets / vol
    return ratio.rolling(window, min_periods=1).mean().fillna(0)

def _rolls_spread(df, window=10):
    """Roll's Spread Proxy: Serial covariance of returns."""
    rets = df['close'].pct_change().fillna(0)
    rets_lag = rets.shift(1).fillna(0)
    cov = rets.rolling(window, min_periods=1).cov(rets_lag).fillna(0)
    # Roll's Spread = 2 * sqrt(-Cov(R_t, R_{t-1})) for Cov < 0, else 0
    spread = np.where(cov < 0, 2 * np.sqrt(np.clip(-cov, a_min=0, a_max=None)), 0)
    return pd.Series(spread, index=df.index).fillna(0)

def _hurst_proxy(df, window=20):
    """Hurst Exponent Proxy using high/low fractal dimension."""
    c = df['close']
    roll_max = c.rolling(window, min_periods=1).max()
    roll_min = c.rolling(window, min_periods=1).min()
    rng = (roll_max / roll_min).replace(0, 1e-8)
    hurst = np.log(rng) / np.log(window)
    return hurst.fillna(0)


# ══════════════════════════════════════════════════════════════════════
# FEATURE REGISTRATIONS
# ══════════════════════════════════════════════════════════════════════

_reg("whale.microstructure.ofi", "Proxy Order Flow Imbalance (OFI)", "Motion",
     "flow", "Calculates true buying vs selling pressure by weighting price action with volume.", "V * (C-O)/(H-L)",
     "Positive values = Institutional accumulation. Negative values = Institutional distribution.", _ofi)

_reg("whale.microstructure.amihud", "Amihud Illiquidity Ratio (Price Impact)", "Statistics",
     "liquidity", "Measures how easily large market orders move the price.", "SMA(|R|/V, 10)",
     "High values = Illiquid, thin markets (easy to manipulate). Low values = Deep liquidity.", _amihud, params={"window": 10})

_reg("whale.microstructure.rolls_spread", "Roll's Hidden Spread", "Statistics",
     "liquidity", "Detects the true underlying bid-ask spread using price action reversals.", "2 * sqrt(-Cov(R_t, R_{t-1}))",
     "High values mean market makers are widening spreads to protect themselves from toxicity.", _rolls_spread, params={"window": 10})

_reg("whale.microstructure.hurst", "Hurst Exponent (Trend Memory)", "Distribution",
     "memory", "Measures if the market is stuck in a chop zone or entering a directional trend.", "log(Max(C, 20)/Min(C, 20)) / log(20)",
     "Values > 0.5 mean the trend is accelerating. Values < 0.5 mean mean-reversion (chop).", _hurst_proxy, params={"window": 20})

_reg("whale.microstructure.va_ofi", "Volatility-Adjusted OFI (Signal Clarity)", "Relative",
     "flow", "Order Flow Imbalance normalized by recent volatility.", "OFI / Vol(10)",
     "Filters out false breakouts. Shows true order flow intent regardless of market panic.", _va_ofi, params={"window": 10})

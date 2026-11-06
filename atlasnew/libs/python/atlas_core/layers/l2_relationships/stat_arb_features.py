"""Statistical Arbitrage Module — Layer 2.

Ports proprietary pairs-trading and mean-reversion logic from the stat_arb engine,
such as the Kalman Hedge Ratio and Ornstein-Uhlenbeck Z-Scores.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition

MODULE = "stat_arb_features"

def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=2, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["close"],
        params=params or {}, complexity=complexity, fn=fn
    ))

def _kalman_hedge_ratio(df, window=24):
    """
    Simplified proxy for Kalman Hedge Ratio beta without needing pairs.
    In the registry context, we just return a rolling beta against a constant trend,
    as pairs are evaluated at a higher abstraction.
    Since we only have ["close"], we can approximate a rolling beta against time or momentum.
    For registry purposes, we implement a mock "Autoregressive Beta" (beta against its own lag).
    """
    c = df['close']
    c_lag = c.shift(1).fillna(c)
    
    # Calculate rolling covariance and variance
    cov = c.rolling(window, min_periods=1).cov(c_lag)
    var = c_lag.rolling(window, min_periods=1).var().replace(0, 1e-8)
    
    beta = cov / var
    return beta.fillna(1.0)

def _ou_zscore(df, window=24):
    """
    Ornstein-Uhlenbeck (OU) Z-Score proxy.
    Calculates the z-score of the asset's deviation from its exponential moving average,
    scaled by the rolling standard deviation of that deviation.
    """
    c = df['close']
    ema = c.ewm(span=window, min_periods=1).mean()
    spread = c - ema
    spread_mean = spread.rolling(window, min_periods=1).mean()
    spread_std = spread.rolling(window, min_periods=1).std().replace(0, 1e-8)
    
    z_score = (spread - spread_mean) / spread_std
    return z_score.fillna(0.0)


# ══════════════════════════════════════════════════════════════════════
# FEATURE REGISTRATIONS
# ══════════════════════════════════════════════════════════════════════

_reg("stat_arb.ar_beta", "Autoregressive Tracking Beta", "Relative",
     "mean_reversion", "Rolling beta of price against its own lag to detect trending vs tracking efficiency.", "Cov(P_t, P_{t-1}) / Var(P_{t-1})",
     "High values = Strong directional tracking. Low values = Mean-reverting inefficiency.", _kalman_hedge_ratio, params={"window": 24})

_reg("stat_arb.ou_zscore", "Mean Reversion Stretch (Z-Score)", "Statistics",
     "mean_reversion", "Statistically normalizes how far price has deviated from its baseline EMA.", "(Spread - E[Spread]) / Std(Spread)",
     "Values > 3 or < -3 indicate a severe statistical over-extension ripe for a rubber-band snapback.", _ou_zscore, params={"window": 24})

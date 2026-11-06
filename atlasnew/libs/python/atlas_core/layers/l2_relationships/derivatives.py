"""Derivatives Module — Layer 2.

Ports structural market mechanics features from atlas_futures_core and 
atlas_options_core to the core feature registry.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition

MODULE = "derivatives"

def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=2, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["close"],
        params=params or {}, complexity=complexity, fn=fn
    ))

def _funding_rate_proxy(df, window=24):
    """
    Mock proxy for Funding Rate Regimes.
    Since actual funding rates require auxiliary data (binance funding endpoints),
    we create a proxy based on continuous extreme momentum as an analog for
    high funding pressure (over-leveraged long/short).
    """
    c = df['close']
    returns = c.pct_change().fillna(0)
    # High recent returns imply high positive funding (longs pay shorts)
    momentum = returns.rolling(window, min_periods=1).mean()
    vol = returns.rolling(window, min_periods=1).std().replace(0, 1e-8)
    funding_proxy = momentum / vol
    return funding_proxy.fillna(0.0)

def _mock_delta(df, window=20):
    """
    Mock Options Delta proxy based on log returns and volatility.
    Approximates the delta of an ATM straddle dynamically responding to trend.
    """
    c = df['close']
    rets = c.pct_change().fillna(0)
    vol = rets.rolling(window, min_periods=1).std().replace(0, 1e-8)
    
    # Very crude proxy: Delta approaches 1 in strong uptrends, -1 in strong downtrends,
    # scaled by volatility.
    trend = (c - c.rolling(window).mean()) / c.rolling(window).mean()
    delta_proxy = np.tanh(trend / vol)
    return delta_proxy.fillna(0.0)

def _mock_gamma(df, window=20):
    """
    Mock Options Gamma proxy. Gamma is highest when price is near strike (ATM)
    and time is short. As a pure price proxy, Gamma spikes during periods of 
    price compression (low vol) where breakouts cause explosive delta changes.
    """
    rets = df['close'].pct_change().fillna(0)
    vol = rets.rolling(window, min_periods=1).std().replace(0, 1e-8)
    
    # Inverse of volatility, normalized.
    gamma_proxy = 1.0 / (vol * np.sqrt(window))
    # Normalize to a reasonable range [0, 10]
    gamma_proxy = gamma_proxy / gamma_proxy.rolling(window, min_periods=1).max().replace(0, 1e-8)
    return gamma_proxy.fillna(0.0)


# ══════════════════════════════════════════════════════════════════════
# FEATURE REGISTRATIONS
# ══════════════════════════════════════════════════════════════════════

_reg("derivatives.funding.proxy", "Perpetual Funding Rate Pressure", "Regime",
     "mechanics", "Simulates perpetual futures funding rates to detect over-leveraged market conditions.", "E[R] / Std(R)",
     "Extreme positive values = Longs are trapped and paying heavy fees to Shorts. Ripe for a long squeeze.", _funding_rate_proxy, params={"window": 24})

_reg("derivatives.greeks.delta_proxy", "Synthetic Options Delta", "Relative",
     "mechanics", "Approximates the directional exposure of the market as if it were a massive options straddle.", "tanh(Trend / Vol)",
     "Approaches +1 in aggressive bull regimes and -1 in bear regimes.", _mock_delta, params={"window": 20})

_reg("derivatives.greeks.gamma_proxy", "Synthetic Gamma Squeeze Risk", "Distribution",
     "mechanics", "Measures price compression that leads to explosive convexity (Gamma Squeezes).", "1 / (Vol * sqrt(W))",
     "High values indicate extreme price compression; a tiny move could trigger a massive cascade (Gamma Squeeze).", _mock_gamma, params={"window": 20})

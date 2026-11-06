"""Chaos Theory & Fractals Module — Layer 1.

Implements nonlinear dynamic measurements like Detrended Fluctuation Analysis (DFA)
and Lyapunov Exponents.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition

MODULE = "chaos_theory"

def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n log n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["close"],
        params=params or {}, complexity=complexity, fn=fn
    ))

def _dfa_proxy(df, window=50):
    """
    Detrended Fluctuation Analysis (DFA) Proxy.
    Estimates the Hurst exponent via fluctuation scaling.
    We use a fast rolling estimation of variance scaling.
    """
    rets = df['close'].pct_change().fillna(0)
    
    def dfa_fast(x):
        if len(x) < 10:
            return 0.5
        # Cumulative sum (profile)
        y = np.cumsum(x - np.mean(x))
        # Simple scaling law over two scales: N/2 and N/4
        scale1, scale2 = len(x) // 2, len(x) // 4
        if scale2 < 4: return 0.5
        
        # Fluctuation at scale1
        f1 = np.std(y[:scale1]) + np.std(y[-scale1:])
        f2 = np.std(y[:scale2]) + np.std(y[scale2:2*scale2]) + np.std(y[2*scale2:3*scale2]) + np.std(y[-scale2:])
        
        if f2 == 0 or f1 == 0: return 0.5
        alpha = np.log(f1 / f2) / np.log(scale1 / scale2)
        return alpha
        
    res = rets.rolling(window, min_periods=window).apply(dfa_fast, raw=True)
    return res.fillna(0.5)

def _lyapunov_proxy(df, window=30, delay=1):
    """
    Largest Lyapunov Exponent (LLE) Proxy.
    Measures the exponential divergence of nearby trajectories.
    Positive LLE indicates chaos.
    """
    c = df['close']
    
    def lle_calc(x):
        if len(x) < 10:
            return 0.0
        # Phase space embedding (m=2)
        p1 = x[:-delay]
        p2 = x[delay:]
        # Find nearest neighbors (crude O(N^2) search over small window)
        div = []
        for i in range(len(p1)-1):
            dists = np.abs(p1 - p1[i])
            dists[i] = np.inf # ignore self
            j = np.argmin(dists)
            if dists[j] > 0 and j < len(p1)-1:
                # Divergence after 1 step
                d0 = dists[j]
                d1 = np.abs(p1[i+1] - p1[j+1])
                div.append(np.log(d1 / d0))
        if not div: return 0.0
        return np.mean(div)

    res = c.rolling(window, min_periods=window).apply(lle_calc, raw=True)
    return res.fillna(0.0)


# ══════════════════════════════════════════════════════════════════════
# REGISTRATIONS
# ══════════════════════════════════════════════════════════════════════

_reg("chaos.dfa.alpha", "DFA Fractal Memory Exponent", "Fractal",
     "memory", "Detrended Fluctuation Analysis to measure if the market has long-term memory.", "alpha ~ log(F(s))/log(s)",
     "Values > 0.5 mean the trend has memory and will persist. Values < 0.5 mean it is just noise.", _dfa_proxy, params={"window": 50})

_reg("chaos.lyapunov.lle", "Lyapunov Market Chaos Index", "Expansion",
     "chaos", "Measures how fast the market is accelerating into chaotic, unpredictable states.", "lambda = 1/t * ln|dZ(t)/dZ(0)|",
     "High positive values = highly chaotic and unstable. Negative values = returning to stable ranges.", _lyapunov_proxy, params={"window": 30, "delay": 1})

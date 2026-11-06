"""Advanced Entropy Module — Layer 1.

Implements complex information-theoretic measurements like Permutation Entropy,
Tsallis Entropy, and proxies for Approximate/Sample Entropy.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import entropy

from atlas_core.registry.registry import registry, FeatureDefinition

MODULE = "advanced_entropy"

def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n log n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["close"],
        params=params or {}, complexity=complexity, fn=fn
    ))

def _permutation_entropy(df, window=20, m=3, delay=1):
    """
    Permutation Entropy (PE) of log returns.
    Measures the complexity of a time series by analyzing the ordinal patterns.
    """
    rets = df['close'].pct_change().fillna(0)
    
    def pe_calc(x):
        if len(x) < m * delay:
            return 0.0
        # Create embedding matrix
        n = len(x) - (m - 1) * delay
        emb = np.array([x[i : i + m * delay : delay] for i in range(n)])
        # Get ordinal patterns (argsort of argsort gives ranks)
        patterns = np.apply_along_axis(lambda arr: tuple(np.argsort(arr)), 1, emb)
        # Count frequencies
        unique_patterns, counts = np.unique(patterns, axis=0, return_counts=True)
        p = counts / counts.sum()
        return entropy(p, base=2)
        
    res = rets.rolling(window, min_periods=window).apply(pe_calc, raw=True)
    return res.fillna(0.0)

def _tsallis_entropy(df, window=20, q=1.5, bins=10):
    """
    Tsallis Entropy (Non-extensive entropy).
    q-parameter models heavy tails. q=1 reduces to Shannon entropy.
    Formula: S_q = (1 - sum(p_i^q)) / (q - 1)
    """
    rets = df['close'].pct_change().fillna(0)
    
    def tsallis_calc(x):
        hist, _ = np.histogram(x, bins=bins, density=False)
        p = hist[hist > 0] / len(x)
        if q == 1.0:
            return entropy(p, base=2)
        return (1.0 - np.sum(p ** q)) / (q - 1.0)
        
    res = rets.rolling(window, min_periods=window).apply(tsallis_calc, raw=True)
    return res.fillna(0.0)

def _approximate_entropy_proxy(df, window=20, m=2):
    """
    Proxy for Approximate Entropy (ApEn).
    Instead of full O(N^2) ApEn which is too slow for rolling windows,
    we use the ratio of standard deviation of differences.
    """
    rets = df['close'].pct_change().fillna(0)
    
    # A crude proxy: log of variance of m-th difference over variance
    var_x = rets.rolling(window, min_periods=window).var().replace(0, 1e-8)
    diff = rets.diff(m).fillna(0)
    var_diff = diff.rolling(window, min_periods=window).var().replace(0, 1e-8)
    
    proxy = np.log(var_diff / var_x)
    return proxy.fillna(0.0)

# ══════════════════════════════════════════════════════════════════════
# REGISTRATIONS
# ══════════════════════════════════════════════════════════════════════

_reg("entropy.permutation", "Permutation Entropy (Market Predictability)", "Entropy",
     "complexity", "Measures how chaotic or predictable the price action is based on ordinal patterns.", "H_{PE} = -sum(p * log2(p))",
     "High values = Random noise. Low values = Algorithmic or predictable market structure.", _permutation_entropy, params={"window": 20, "m": 3, "delay": 1})

_reg("entropy.tsallis", "Tsallis Entropy (Tail Risk Measure)", "Entropy",
     "complexity", "Advanced entropy that accounts for extreme market events (black swans).", "S_q = (1 - sum(p^q))/(q-1)",
     "High values warn of unstable, fat-tailed market conditions with elevated crash risk.", _tsallis_entropy, params={"window": 20, "q": 1.5, "bins": 10})

_reg("entropy.apen_proxy", "Approximate Entropy (Trend Complexity)", "Entropy",
     "complexity", "Fast proxy to detect the complexity and hidden memory in price trends.", "log(Var(diff_m) / Var(x))",
     "Helps distinguish between genuine trends and choppy mean-reverting noise.", _approximate_entropy_proxy, params={"window": 20, "m": 2})

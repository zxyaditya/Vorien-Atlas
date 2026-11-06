"""Advanced Econometrics Module — Layer 1.

Implements complex econometric proxies such as Extreme Value Theory (EVT) estimators,
Jump Diffusion intensity, GARCH volatility, and Mahalanobis distances.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition

MODULE = "econometrics"

def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["open", "high", "low", "close", "volume"],
        params=params or {}, complexity=complexity, fn=fn
    ))

def _hill_estimator(df, window=100, tail_fraction=0.10):
    """
    Hill Estimator for the tail index (alpha) of the return distribution.
    Measures the thickness of the tails (EVT).
    """
    rets = df['close'].pct_change().abs().fillna(0)
    
    def hill_calc(x):
        k = max(int(len(x) * tail_fraction), 2)
        sorted_x = np.sort(x)
        tail = sorted_x[-k:]
        threshold = sorted_x[-k - 1]
        if threshold <= 0: return 0.0
        # Hill estimator
        gamma = np.mean(np.log(tail / threshold))
        return 1.0 / gamma if gamma > 0 else 0.0
        
    res = rets.rolling(window, min_periods=window//2).apply(hill_calc, raw=True)
    return res.fillna(0.0)

def _jump_intensity_proxy(df, window=50, threshold_sigma=3.0):
    """
    Proxy for Poisson Jump intensity (lambda) in a jump-diffusion process.
    Counts the frequency of returns exceeding local N-sigma.
    """
    rets = df['close'].pct_change().fillna(0)
    roll_std = rets.rolling(window, min_periods=1).std().replace(0, 1e-8)
    # Identify jumps
    is_jump = (rets.abs() > (threshold_sigma * roll_std)).astype(int)
    # Jump intensity (lambda) is the moving average of jump occurrences
    intensity = is_jump.rolling(window, min_periods=1).mean()
    return intensity.fillna(0.0)

def _garch_proxy(df, window=20, alpha=0.1, beta=0.8):
    """
    GARCH(1,1) Volatility Proxy without MLE optimization.
    Var_t = omega + alpha * r_{t-1}^2 + beta * Var_{t-1}
    We use an EWMA variant to closely approximate GARCH variance.
    """
    rets = df['close'].pct_change().fillna(0)
    rets_sq = rets ** 2
    # EWMA is a special case of IGARCH where alpha + beta = 1
    # We use a span corresponding to standard GARCH decay
    span = (1 + beta) / (1 - beta)
    garch_var = rets_sq.ewm(span=span, min_periods=1).mean()
    return np.sqrt(garch_var).fillna(0.0)

def _mahalanobis_distance(df, window=30):
    """
    Mahalanobis Distance of the current [Returns, LogVolume, Range] vector
    relative to the rolling historical covariance. Detects multi-dimensional anomalies.
    """
    rets = df['close'].pct_change().fillna(0)
    vol = np.log(df['volume'] + 1).replace([np.inf, -np.inf], 0)
    rng = ((df['high'] - df['low']) / df['close']).fillna(0)
    
    mat = pd.DataFrame({'R': rets, 'V': vol, 'H': rng})
    
    def m_dist(x):
        if len(x) < 10: return 0.0
        mean = np.mean(x, axis=0)
        cov = np.cov(x, rowvar=False)
        try:
            inv_cov = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            return 0.0
        diff = x[-1] - mean
        return np.sqrt(np.dot(np.dot(diff, inv_cov), diff.T))
        
    res = mat.rolling(window, min_periods=window).apply(lambda row: 0, raw=True) # pandas rolling apply on multi-column is tricky
    
    # Vectorized loop for multi-column rolling
    m_dists = np.zeros(len(df))
    vals = mat.values
    for i in range(window, len(df)):
        window_data = vals[i-window:i]
        mean = np.mean(window_data, axis=0)
        cov = np.cov(window_data, rowvar=False)
        try:
            inv_cov = np.linalg.inv(cov)
            diff = vals[i] - mean
            m_dists[i] = np.sqrt(np.dot(np.dot(diff, inv_cov), diff.T))
        except np.linalg.LinAlgError:
            m_dists[i] = 0.0
            
    return pd.Series(m_dists, index=df.index).fillna(0.0)

# ══════════════════════════════════════════════════════════════════════
# REGISTRATIONS
# ══════════════════════════════════════════════════════════════════════

_reg("econometrics.tail.hill", "Hill Estimator (Black Swan Risk)", "Distribution",
     "tail_risk", "Measures the mathematical thickness of the tail (probability of extreme outlier events).", "alpha = 1 / mean(ln(X / X_threshold))",
     "Lower values = Fat tails. The market is prone to sudden, violent crashes or spikes.", _hill_estimator, params={"window": 100})

_reg("econometrics.jumps.intensity", "Jump Diffusion Intensity (Shock Rate)", "Statistics",
     "tail_risk", "Measures the underlying frequency of sudden >3 sigma price shocks.", "lambda = E[1_{|R| > 3*sigma}]",
     "High values indicate a highly unstable market prone to continuous gap-ups and gap-downs.", _jump_intensity_proxy, params={"window": 50})

_reg("econometrics.vol.garch", "GARCH(1,1) Volatility", "Statistics",
     "volatility", "Advanced volatility model that captures volatility clustering (storms breed storms).", "sqrt(EWMA(R^2))",
     "More responsive than standard standard-deviation. High values mean you are in a high-risk volatility regime.", _garch_proxy, params={"window": 20})

_reg("econometrics.anomaly.mahalanobis", "Mahalanobis Distance (Market Anomaly)", "Geometry",
     "anomaly", "Measures how abnormal the current price/volume action is compared to recent history in 3D space.", "sqrt( (x-u)^T * Cov^-1 * (x-u) )",
     "Detects structural breaks. High values mean the 'character' of the market has fundamentally shifted.", _mahalanobis_distance, params={"window": 30})

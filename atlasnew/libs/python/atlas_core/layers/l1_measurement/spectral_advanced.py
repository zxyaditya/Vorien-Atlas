"""Advanced Spectral Module — Layer 1.

Implements complex spectral processing and instantaneous frequency measures
such as Hilbert Transform analytic phases.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.signal import hilbert

from atlas_core.registry.registry import registry, FeatureDefinition

MODULE = "spectral_advanced"

def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n log n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["close"],
        params=params or {}, complexity=complexity, fn=fn
    ))

def _hilbert_instantaneous_freq(df, window=50):
    """
    Hilbert Transform Instantaneous Frequency.
    Calculates the analytic signal, extracts the unwrapped phase, and derives
    the instantaneous frequency (rate of change of phase).
    """
    c = df['close']
    
    def hilbert_if_calc(x):
        if len(x) < 10:
            return 0.0
        # Detrend
        x_detrend = x - np.mean(x)
        # Analytic signal
        analytic_signal = hilbert(x_detrend)
        # Instantaneous phase
        inst_phase = np.unwrap(np.angle(analytic_signal))
        # Instantaneous frequency is the derivative of phase
        inst_freq = np.diff(inst_phase) / (2.0 * np.pi)
        if len(inst_freq) == 0: return 0.0
        # Return the latest frequency
        return inst_freq[-1]
        
    res = c.rolling(window, min_periods=window).apply(hilbert_if_calc, raw=True)
    return res.fillna(0.0)

# ══════════════════════════════════════════════════════════════════════
# REGISTRATIONS
# ══════════════════════════════════════════════════════════════════════

_reg("spectral.hilbert.freq", "Hilbert Market Cycle Speed", "Motion",
     "cycles", "Calculates the instantaneous speed of the market's dominant cycle using the Hilbert Transform.", "d(Phase)/dt",
     "Fast way to detect if the market is speeding up or slowing down its cyclical oscillations.", _hilbert_instantaneous_freq, params={"window": 50})

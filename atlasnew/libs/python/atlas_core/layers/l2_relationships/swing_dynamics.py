"""Swing Dynamics — Layer 2.

Once swings exist (see market_structure), the DYNAMICS between successive
swings become measurable relationships: amplitudes, intervals, cadence.
Book 1 lists Swing Dynamics explicitly as an L2 example.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.engines import swings as sw, statistics as st
from atlas_core.layers.l2_relationships._l1_bridge import l1_series

MODULE = "swing_dynamics"


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=2, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["L1:price.magnitude.high", "L1:price.magnitude.low"],
        params=params or {}, complexity=complexity, fn=fn,
    ))


def _high(df): return l1_series(df, "price.magnitude.high")
def _low(df):  return l1_series(df, "price.magnitude.low")


for k in [3, 5]:
    def _swing_amp(df, k_=k):
        h = sw.swing_sequence(_high(df), sw.confirmed_pivot_high(_high(df), k_))
        l = sw.swing_sequence(_low(df),  sw.confirmed_pivot_low(_low(df),  k_))
        return (h["swing_1"] - l["swing_1"]).abs()
    _reg(f"swing_dynamics.magnitude.amplitude_k{k}",
         f"Swing Amplitude (k={k})", "Magnitude", "amplitude",
         "|last swing high - last swing low|.",
         "|swingH_1 - swingL_1|", "Size of the last full swing.",
         (lambda k_: (lambda df: _swing_amp(df, k_)))(k), params={"k": k})

    def _interval_h(df, k_=k):
        return sw.last_swing_index(sw.confirmed_pivot_high(_high(df), k_))
    def _interval_l(df, k_=k):
        return sw.last_swing_index(sw.confirmed_pivot_low(_low(df), k_))
    _reg(f"swing_dynamics.motion.bars_since_high_k{k}",
         f"Bars Since Last Swing High (k={k})", "Motion", "interval",
         "Bars elapsed since the last confirmed swing high.",
         "t - t*_H", "Recency of last upper pivot.",
         (lambda k_: (lambda df: _interval_h(df, k_)))(k), params={"k": k})
    _reg(f"swing_dynamics.motion.bars_since_low_k{k}",
         f"Bars Since Last Swing Low (k={k})", "Motion", "interval",
         "Bars elapsed since the last confirmed swing low.",
         "t - t*_L", "Recency of last lower pivot.",
         (lambda k_: (lambda df: _interval_l(df, k_)))(k), params={"k": k})

    def _cadence(df, k_=k):
        """Fraction of the last 50 bars that were pivots (either side)."""
        p = (sw.confirmed_pivot_high(_high(df), k_) +
             sw.confirmed_pivot_low(_low(df), k_))
        return p.clip(0, 1).rolling(50, min_periods=50).mean()
    _reg(f"swing_dynamics.statistics.pivot_cadence_k{k}_w50",
         f"Pivot Cadence (k={k}, w=50)", "Statistics", "cadence",
         "Fraction of bars in the last 50 that are confirmed pivots.",
         "mean_50(pivot_H + pivot_L)",
         "Structural busyness — more pivots = less persistent structure.",
         (lambda k_: (lambda df: _cadence(df, k_)))(k), params={"k": k})

    def _amp_ratio(df, k_=k):
        a = _swing_amp(df, k_)
        return a / a.rolling(50, min_periods=50).mean().replace(0, np.nan)
    _reg(f"swing_dynamics.expansion.amplitude_ratio_k{k}_w50",
         f"Amplitude Expansion Ratio (k={k}, w=50)", "Expansion", "amplitude_ratio",
         "Swing amplitude divided by its own rolling mean.",
         "amp / MA_50(amp)",
         "Whether swings are getting larger or smaller.",
         (lambda k_: (lambda df: _amp_ratio(df, k_)))(k), params={"k": k})

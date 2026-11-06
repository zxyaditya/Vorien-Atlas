"""Compression & Expansion — Layer 2 (Book 1 Ch. 5 example).

Measures the RELATIONSHIP between short-horizon and long-horizon
volatility/range measurements. Consumes L1 through the bridge only.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.engines import statistics as st
from atlas_core.layers.l2_relationships._l1_bridge import l1_series

MODULE = "compression_expansion"


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=2, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["L1:volatility.magnitude.*", "L1:price.magnitude.atr_*"],
        params=params or {}, complexity=complexity, fn=fn,
    ))


# Vol expansion: short-window Yang-Zhang vs long-window
for pair in [(10, 50), (20, 100)]:
    sw_, lw_ = pair
    def _vol_ratio(df, s_=sw_, l_=lw_):
        vs = l1_series(df, f"volatility.magnitude.yz_{s_}") if registry.contains(
            f"volatility.magnitude.yz_{s_}") else l1_series(df, f"volatility.magnitude.cc_{s_}")
        vl = l1_series(df, f"volatility.magnitude.yz_{l_}") if registry.contains(
            f"volatility.magnitude.yz_{l_}") else l1_series(df, f"volatility.magnitude.cc_{l_}")
        return vs / vl.replace(0, np.nan)
    _reg(f"compression_expansion.expansion.vol_ratio_{sw_}_{lw_}",
         f"σ Short/Long Ratio ({sw_}/{lw_})", "Expansion", "volatility_ratio",
         f"Short-window vol divided by long-window vol.",
         f"σ_{sw_} / σ_{lw_}",
         "<1 = compression; >1 = expansion.",
         (lambda s_, l_: (lambda df: _vol_ratio(df, s_, l_)))(sw_, lw_),
         params={"short": sw_, "long": lw_})


# ATR ratio
for pair in [(14, 30), (14, 60)]:
    a_, b_ = pair
    def _atr_ratio(df, a=a_, b=b_):
        aa = l1_series(df, f"price.magnitude.atr_{a}")
        bb = l1_series(df, f"price.magnitude.atr_{b}") if registry.contains(
            f"price.magnitude.atr_{b}") else l1_series(df, f"price.magnitude.atr_14")
        return aa / bb.replace(0, np.nan)
    _reg(f"compression_expansion.expansion.atr_ratio_{a_}_{b_}",
         f"ATR Ratio ({a_}/{b_})", "Expansion", "atr_ratio",
         "Short-window ATR over long-window ATR.",
         f"ATR_{a_} / ATR_{b_}",
         "Range-based expansion measurement.",
         (lambda a=a_, b=b_: (lambda df: _atr_ratio(df, a, b)))(),
         params={"a": a_, "b": b_})


# Bollinger bandwidth ratio (existing L1 feature) percentile rank
for w in [50, 100]:
    def _bw_rank(df, w_=w):
        bw = l1_series(df, "price.expansion.bb_width_20_k2")
        return bw.rolling(w_, min_periods=w_).rank(pct=True)
    _reg(f"compression_expansion.position.bb_width_pct_rank_{w}",
         f"BB Width Percentile Rank ({w})", "Position", "pct_rank",
         f"Percentile rank of Bollinger bandwidth over the last {w} bars.",
         "rank_pct(bb_width, w)",
         "Low = squeeze; high = expansion.",
         (lambda w_: (lambda df: _bw_rank(df, w_)))(w), params={"window": w})


# Squeeze regime flag: vol_ratio < 0.75 AND bb_width in bottom quintile
def _squeeze_flag(df):
    vr = l1_series(df, "volatility.expansion.short_long_ratio") if registry.contains(
        "volatility.expansion.short_long_ratio") else pd.Series(
            np.ones(len(df)), index=df.index)
    bw = l1_series(df, "price.expansion.bb_width_20_k2")
    bw_rank = bw.rolling(100, min_periods=100).rank(pct=True)
    return ((vr < 0.75) & (bw_rank < 0.2)).astype(float)

_reg("compression_expansion.regime.squeeze_flag",
     "Compression / Squeeze Flag", "Regime", "squeeze",
     "1 when short/long vol ratio < 0.75 AND BB width rank < 20%.",
     "1[σ_sl<0.75 ∧ bw_rank<0.2]",
     "Structural compression — measured, not interpreted.",
     _squeeze_flag)

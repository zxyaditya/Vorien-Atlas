"""Multi-scale representations — Layer 4.

Book 1 Ch. 5 exemplar: multi-scale representations. Same primitive
summarised across ≥ 3 scales. See docs/L4_REPRESENTATION.md §6.4.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l4_representation._layer_bridge import (
    l1_series, l2_series,
)

MODULE = "multi_scale_representations"


def _reg(id_, name, perspective, family, definition, formula, interp,
         fn, inputs, params=None, complexity="O(n)", scales=None):
    p = {} if scales is None else {"scales": list(scales)}
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=4, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=p, complexity=complexity, fn=fn,
    ))


# --- Multi-window Hurst summary (already have h_32, h_64, h_128 at L1 or via fractal_relationships) ---
def _hurst_scales(df):
    return pd.DataFrame({
        32: l1_series(df, "price.geometry.hurst_32"),
        64: l1_series(df, "price.geometry.hurst_64"),
        128: l1_series(df, "price.geometry.hurst_128"),
    }, index=df.index)

_reg(f"{MODULE}.geometry.hurst_multi_scale_mean_32_64_128",
     "Hurst mean across 32/64/128", "Geometry", "multi_scale_hurst",
     "Mean of Hurst exponent across the three canonical windows.",
     "mean(hurst_32, hurst_64, hurst_128)",
     "Overall persistence level across scales.",
     lambda df: _hurst_scales(df).mean(axis=1).astype(float),
     inputs=["L1:price.geometry.hurst_{32,64,128}"], scales=(32, 64, 128))

_reg(f"{MODULE}.statistics.hurst_multi_scale_std_32_64_128",
     "Hurst std across 32/64/128", "Statistics", "multi_scale_hurst",
     "Std of Hurst across the three canonical windows.",
     "std(hurst_32, hurst_64, hurst_128)",
     "Cross-scale disagreement about persistence.",
     lambda df: _hurst_scales(df).std(axis=1, ddof=0).astype(float),
     inputs=["L1:price.geometry.hurst_{32,64,128}"], scales=(32, 64, 128))

_reg(f"{MODULE}.geometry.hurst_multi_scale_range_32_64_128",
     "Hurst range across 32/64/128", "Geometry", "multi_scale_hurst",
     "max - min of Hurst across the three canonical windows.",
     "max(H) - min(H)", "Scale-heterogeneity of persistence.",
     lambda df: (_hurst_scales(df).max(axis=1) - _hurst_scales(df).min(axis=1)).astype(float),
     inputs=["L1:price.geometry.hurst_{32,64,128}"], scales=(32, 64, 128))

# --- Multi-window slope (already have lr_slope_20, 50, 100) ---
def _slope_scales(df):
    return pd.DataFrame({
        20: l1_series(df, "price.motion.lr_slope_20"),
        50: l1_series(df, "price.motion.lr_slope_50"),
        # No lr_slope_100 in registry — approximate by 50-bar slope with lag.
        100: l1_series(df, "price.motion.lr_slope_50").rolling(50, min_periods=10).mean(),
    }, index=df.index)

_reg(f"{MODULE}.motion.slope_multi_scale_sign_agreement_20_50_100",
     "Slope sign agreement 20/50/100", "Motion", "multi_scale_slope",
     "Fraction of slope windows with the same sign as the majority.",
     "|sum(sign(slope_i))| / 3",
     "How coherent trend direction is across three windows.",
     lambda df: (np.abs(np.sign(_slope_scales(df).values).sum(axis=1)) / 3.0).astype(float),
     inputs=["L1:price.motion.lr_slope_{20,50}"], scales=(20, 50, 100))

def _slope_dominant(df):
    S = _slope_scales(df)
    absmax_idx = S.abs().values.argmax(axis=1)
    scales = np.array([20, 50, 100])
    return pd.Series(scales[absmax_idx].astype(float), index=df.index)
_reg(f"{MODULE}.clustering.slope_dominant_scale_20_50_100",
     "Slope dominant scale (argmax |slope|)", "Clustering", "multi_scale_slope",
     "Window (20/50/100) whose slope has the largest magnitude.",
     "scale[argmax_i |slope_i|]", "Which timescale is driving trend right now.",
     _slope_dominant,
     inputs=["L1:price.motion.lr_slope_{20,50}"], scales=(20, 50, 100))

# --- Multi-window RS ---
def _rs_scales(df):
    return pd.DataFrame({
        20: l2_series(df, "relative_strength.magnitude.rs_20"),
        50: l2_series(df, "relative_strength.magnitude.rs_50"),
        100: l2_series(df, "relative_strength.magnitude.rs_100"),
    }, index=df.index)

_reg(f"{MODULE}.geometry.rs_multi_scale_mean_20_50_100",
     "RS mean across 20/50/100", "Geometry", "multi_scale_rs",
     "Mean of relative-strength ratio across three windows.",
     "mean(rs_20, rs_50, rs_100)", "Multi-horizon relative strength level.",
     lambda df: _rs_scales(df).mean(axis=1).astype(float),
     inputs=["L2:relative_strength.magnitude.rs_{20,50,100}"], scales=(20, 50, 100))

_reg(f"{MODULE}.statistics.rs_multi_scale_std_20_50_100",
     "RS std across 20/50/100", "Statistics", "multi_scale_rs",
     "Std of relative-strength ratio across three windows.",
     "std(rs_20, rs_50, rs_100)", "Cross-horizon RS instability.",
     lambda df: _rs_scales(df).std(axis=1, ddof=0).astype(float),
     inputs=["L2:relative_strength.magnitude.rs_{20,50,100}"], scales=(20, 50, 100))

# --- Multi-window volatility ---
def _vol_scales(df):
    return pd.DataFrame({
        10: l1_series(df, "volatility.statistics.std_20").rolling(10, min_periods=3).mean(),  # proxy for std_10
        20: l1_series(df, "volatility.statistics.std_20"),
        50: l1_series(df, "volatility.statistics.std_50"),
    }, index=df.index)

_reg(f"{MODULE}.geometry.volatility_multi_scale_mean_10_20_50",
     "Volatility mean across 10/20/50", "Geometry", "multi_scale_vol",
     "Mean of return-std across three windows.",
     "mean(std_10, std_20, std_50)", "Baseline volatility across scales.",
     lambda df: _vol_scales(df).mean(axis=1).astype(float),
     inputs=["L1:volatility.statistics.std_{20,50}"], scales=(10, 20, 50))

def _vol_ratio_1050(df):
    V = _vol_scales(df)
    denom = V[50].replace(0.0, np.nan)
    return (V[10] / denom).astype(float)
_reg(f"{MODULE}.relative.volatility_short_long_ratio_10_50",
     "Volatility 10/50 ratio", "Relative", "multi_scale_vol",
     "std_10 / std_50.", "std_10 / std_50", "Short-vs-long volatility regime.",
     _vol_ratio_1050,
     inputs=["L1:volatility.statistics.std_{20,50}"], scales=(10, 20, 50))

# --- Multi-window consensus ---
def _consensus_10_20_50(df):
    # trend_relationships only publishes _20; approximate 10/50 via rolling
    # of the same series (safe because consensus is bounded and stationary-ish).
    c = l2_series(df, "trend_relationships.regime.directional_consensus_score_20")
    return pd.DataFrame({
        10: c.rolling(10, min_periods=3).mean(),
        20: c.rolling(20, min_periods=5).mean(),
        50: c.rolling(50, min_periods=15).mean(),
    }, index=df.index)

_reg(f"{MODULE}.geometry.consensus_multi_scale_mean_10_20_50",
     "Consensus mean across 10/20/50", "Geometry", "multi_scale_consensus",
     "Mean of rolling consensus at 3 window sizes.",
     "mean(cons_ma_{10,20,50})", "Multi-horizon L2 trend agreement.",
     lambda df: _consensus_10_20_50(df).mean(axis=1).astype(float),
     inputs=["L2:trend_relationships.regime.directional_consensus_score_20"],
     scales=(10, 20, 50))

_reg(f"{MODULE}.statistics.consensus_multi_scale_std_10_20_50",
     "Consensus std across 10/20/50", "Statistics", "multi_scale_consensus",
     "Std of rolling consensus at 3 window sizes.",
     "std(cons_ma_{10,20,50})", "Cross-horizon L2 disagreement.",
     lambda df: _consensus_10_20_50(df).std(axis=1, ddof=0).astype(float),
     inputs=["L2:trend_relationships.regime.directional_consensus_score_20"],
     scales=(10, 20, 50))

_reg(f"{MODULE}.motion.slope_multi_scale_dot_20_50_100",
     "Slope dot-magnitude 20/50/100", "Motion", "multi_scale_slope",
     "Sum of signed slopes across 3 windows.",
     "slope_20 + slope_50 + slope_100",
     "Cumulative signed trend intensity across horizons.",
     lambda df: _slope_scales(df).sum(axis=1).astype(float),
     inputs=["L1:price.motion.lr_slope_{20,50}"], scales=(20, 50, 100))

_reg(f"{MODULE}.geometry.hurst_median_32_64_128",
     "Hurst median 32/64/128", "Geometry", "multi_scale_hurst",
     "Median of Hurst exponent across 3 windows.",
     "median(H_32, H_64, H_128)",
     "Robust central persistence estimate.",
     lambda df: _hurst_scales(df).median(axis=1).astype(float),
     inputs=["L1:price.geometry.hurst_{32,64,128}"], scales=(32, 64, 128))

_reg(f"{MODULE}.statistics.volatility_multi_scale_std_10_20_50",
     "Volatility std across 10/20/50", "Statistics", "multi_scale_vol",
     "Cross-window std of return-std.",
     "std(std_10, std_20, std_50)",
     "How much volatility varies across timescales.",
     lambda df: _vol_scales(df).std(axis=1, ddof=0).astype(float),
     inputs=["L1:volatility.statistics.std_{20,50}"], scales=(10, 20, 50))

"""Cross-module Interactions — Layer 4.

Book 1 Ch. 5 exemplar: cross-module interactions. Products, ratios,
sign-agreements across L1/L2/L3 module boundaries. See
docs/L4_REPRESENTATION.md §6.1.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l4_representation._layer_bridge import (
    l1_series, l2_series, l3_series,
)
from atlas_core.layers.l4_representation._representation_kernel import (
    interaction, rolling_zscore,
)

MODULE = "cross_module_interactions"


def _reg(id_, name, perspective, family, definition, formula, interp,
         fn, inputs, params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=4, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=params or {}, complexity=complexity, fn=fn,
    ))


# Compact cache-free evidence readers (bridge caches downstream).
def _slope(df):    return l1_series(df, "price.motion.lr_slope_50")
def _vol_signed(df): return l1_series(df, "volume.regime.signed_ema_20")
def _adx(df):     return l1_series(df, "price.regime.adx_14")
def _liq_ter(df): return l1_series(df, "liquidity.regime.tercile_200")
def _vol_ter(df): return l1_series(df, "volatility.regime.tercile_200")
def _bos(df):     return l2_series(df, "market_structure.motion.bos_k5")
def _slope_vel(df): return l2_series(df, "momentum_of_trend.motion.lr_slope_20_velocity_20")
def _mr_conf(df): return l3_series(df, "market_regime.statistics.active_state_confidence")
def _ts_conf(df): return l3_series(df, "trend_state.statistics.active_state_confidence")
def _ps_conf(df): return l3_series(df, "participation_state.statistics.active_state_confidence")
def _mr_code(df): return l3_series(df, "market_regime.regime.active_state_code")
def _consensus_sign(df): return l2_series(df, "trend_relationships.regime.directional_consensus_sign_20")


# --- L1 x L1 (trend x volume; regime x liquidity) ---
_reg(f"{MODULE}.motion.trend_x_volume_signed_20",
     "Trend x Volume (signed)", "Motion", "trend_volume",
     "Product of z-scored slope and signed volume EMA.",
     "z(slope_50) * volume.signed_ema_20",
     "Positive when trend and volume agree in direction.",
     lambda df: interaction(rolling_zscore(_slope(df), 100), _vol_signed(df), "product"),
     inputs=["L1:price.motion.lr_slope_50", "L1:volume.regime.signed_ema_20"])

_reg(f"{MODULE}.motion.trend_x_volume_sign_agree_20",
     "Trend x Volume (sign agreement)", "Motion", "trend_volume",
     "Sign agreement: +1 same sign, -1 opposite, 0 either zero.",
     "sign_agree(slope_50, volume.signed_ema_20)",
     "+1 = trend and volume aligned; -1 = divergence.",
     lambda df: interaction(_slope(df), _vol_signed(df), "sign_agree"),
     inputs=["L1:price.motion.lr_slope_50", "L1:volume.regime.signed_ema_20"])

_reg(f"{MODULE}.relative.regime_x_liquidity_20",
     "Regime x Liquidity", "Relative", "regime_liquidity",
     "Product of ADX and liquidity tercile.",
     "adx_14 * liquidity.tercile_200",
     "High trending * high liquidity ⇒ large-cap trend.",
     lambda df: interaction(_adx(df), _liq_ter(df), "product"),
     inputs=["L1:price.regime.adx_14", "L1:liquidity.regime.tercile_200"])

_reg(f"{MODULE}.relative.regime_x_volatility_20",
     "Regime x Volatility", "Relative", "regime_volatility",
     "ADX * volatility tercile.", "adx_14 * volatility.tercile_200",
     "Trending & volatile ⇒ large-move regime.",
     lambda df: interaction(_adx(df), _vol_ter(df), "product"),
     inputs=["L1:price.regime.adx_14", "L1:volatility.regime.tercile_200"])

# --- L2 x L2 (structure x momentum) ---
_reg(f"{MODULE}.motion.structure_x_momentum_agree_20",
     "Structure x Momentum (agreement)", "Motion", "structure_momentum",
     "Sign agreement between BOS and slope-velocity.",
     "sign_agree(BOS_k5, slope_vel_20)",
     "+1 = structural break aligned with acceleration.",
     lambda df: interaction(_bos(df), _slope_vel(df), "sign_agree"),
     inputs=["L2:market_structure.motion.bos_k5",
             "L2:momentum_of_trend.motion.lr_slope_20_velocity_20"])

_reg(f"{MODULE}.motion.structure_x_momentum_product_20",
     "Structure x Momentum (product)", "Motion", "structure_momentum",
     "Product of BOS and z-scored slope-velocity.",
     "BOS_k5 * z(slope_vel_20)",
     "Magnitude-weighted structural-momentum alignment.",
     lambda df: interaction(_bos(df), rolling_zscore(_slope_vel(df), 100), "product"),
     inputs=["L2:market_structure.motion.bos_k5",
             "L2:momentum_of_trend.motion.lr_slope_20_velocity_20"])

# --- L3 x L1 (state x volatility, state x liquidity) ---
_reg(f"{MODULE}.geometry.regime_state_x_volatility",
     "Regime state x Volatility", "Geometry", "state_volatility",
     "L3 market_regime confidence * volatility tercile.",
     "mr_confidence * volatility.tercile_200",
     "How much of the market regime lives in the volatile bucket.",
     lambda df: interaction(_mr_conf(df), _vol_ter(df), "product"),
     inputs=["L3:market_regime.statistics.active_state_confidence",
             "L1:volatility.regime.tercile_200"])

_reg(f"{MODULE}.geometry.trend_state_x_liquidity",
     "Trend state x Liquidity", "Geometry", "state_liquidity",
     "L3 trend_state confidence * liquidity tercile.",
     "ts_confidence * liquidity.tercile_200",
     "Trend-state conviction weighted by liquidity depth.",
     lambda df: interaction(_ts_conf(df), _liq_ter(df), "product"),
     inputs=["L3:trend_state.statistics.active_state_confidence",
             "L1:liquidity.regime.tercile_200"])

# --- L3 x L3 (state x state) ---
_reg(f"{MODULE}.relative.trend_state_x_participation_state",
     "Trend state x Participation state (signed)", "Relative", "state_state",
     "Trend-state confidence * participation-state confidence, sign from consensus.",
     "ts_conf * ps_conf * consensus_sign",
     "Combined trend + participation conviction, signed by consensus.",
     lambda df: interaction(interaction(_ts_conf(df), _ps_conf(df), "product"),
                            _consensus_sign(df), "product"),
     inputs=["L3:trend_state.*", "L3:participation_state.*",
             "L2:trend_relationships.regime.directional_consensus_sign_20"])

_reg(f"{MODULE}.relative.state_confidence_min",
     "State confidence (min across families)", "Relative", "state_state",
     "Minimum of the L3 family confidences.",
     "min(ts_conf, mr_conf, ps_conf)",
     "Weakest-link state conviction across families.",
     lambda df: interaction(interaction(_ts_conf(df), _mr_conf(df), "min"), _ps_conf(df), "min"),
     inputs=["L3:*.statistics.active_state_confidence"])

_reg(f"{MODULE}.relative.state_confidence_max",
     "State confidence (max across families)", "Relative", "state_state",
     "Maximum of the L3 family confidences.",
     "max(ts_conf, mr_conf, ps_conf)",
     "Strongest state conviction across families.",
     lambda df: interaction(interaction(_ts_conf(df), _mr_conf(df), "max"), _ps_conf(df), "max"),
     inputs=["L3:*.statistics.active_state_confidence"])

# --- Absolute-difference features (divergence detectors) ---
_reg(f"{MODULE}.motion.trend_vs_regime_absdiff",
     "Trend vs Regime (absdiff)", "Motion", "divergence",
     "|z(slope_50) - adx_14/60|.", "|z(slope) - adx/60|",
     "Divergence between trend direction and trend strength.",
     lambda df: interaction(rolling_zscore(_slope(df), 100), _adx(df) / 60.0, "absdiff"),
     inputs=["L1:price.motion.lr_slope_50", "L1:price.regime.adx_14"])

_reg(f"{MODULE}.motion.bos_vs_slopevel_absdiff",
     "BOS vs SlopeVel (absdiff)", "Motion", "divergence",
     "|BOS_k5 - z(slope_vel_20)|.", "|BOS - z(slope_vel)|",
     "Structural-momentum divergence magnitude.",
     lambda df: interaction(_bos(df), rolling_zscore(_slope_vel(df), 100), "absdiff"),
     inputs=["L2:market_structure.motion.bos_k5",
             "L2:momentum_of_trend.motion.lr_slope_20_velocity_20"])

# --- Ratio-based interactions ---
_reg(f"{MODULE}.relative.confidence_ratio_ts_mr",
     "Confidence ratio (trend / regime)", "Relative", "state_state",
     "trend_state confidence / market_regime confidence.",
     "ts_conf / mr_conf", "Trend conviction relative to regime conviction.",
     lambda df: interaction(_ts_conf(df), _mr_conf(df) + 1e-3, "ratio"),
     inputs=["L3:trend_state.*", "L3:market_regime.*"])

_reg(f"{MODULE}.relative.confidence_ratio_ps_mr",
     "Confidence ratio (participation / regime)", "Relative", "state_state",
     "participation_state confidence / market_regime confidence.",
     "ps_conf / mr_conf", "Participation conviction relative to regime conviction.",
     lambda df: interaction(_ps_conf(df), _mr_conf(df) + 1e-3, "ratio"),
     inputs=["L3:participation_state.*", "L3:market_regime.*"])

# --- L3 code x L1 magnitude (categorical x continuous) ---
_reg(f"{MODULE}.geometry.regime_code_x_zscore_slope",
     "Regime code x z(slope)", "Geometry", "regime_zscore",
     "active_state_code * z-scored 50-bar slope.",
     "mr.active_code * z(slope_50)",
     "Trend intensity conditional on the discrete market regime.",
     lambda df: interaction(_mr_code(df), rolling_zscore(_slope(df), 100), "product"),
     inputs=["L3:market_regime.regime.active_state_code",
             "L1:price.motion.lr_slope_50"])

_reg(f"{MODULE}.geometry.regime_code_x_bos",
     "Regime code x BOS", "Geometry", "regime_structure",
     "active_state_code * BOS_k5.",
     "mr.active_code * BOS_k5",
     "Structural break intensity conditional on the market regime.",
     lambda df: interaction(_mr_code(df), _bos(df), "product"),
     inputs=["L3:market_regime.regime.active_state_code",
             "L2:market_structure.motion.bos_k5"])

_reg(f"{MODULE}.motion.consensus_x_slopevel",
     "Consensus x SlopeVel", "Motion", "trend_momentum",
     "Directional consensus sign * slope velocity.",
     "consensus_sign * slope_vel",
     "Trend-alignment-modulated acceleration.",
     lambda df: interaction(_consensus_sign(df), _slope_vel(df), "product"),
     inputs=["L2:trend_relationships.regime.directional_consensus_sign_20",
             "L2:momentum_of_trend.motion.lr_slope_20_velocity_20"])

_reg(f"{MODULE}.motion.mr_conf_x_slopevel",
     "MR confidence x SlopeVel", "Motion", "state_momentum",
     "L3 regime confidence * slope velocity.", "mr_conf * slope_vel",
     "Acceleration weighted by regime confidence.",
     lambda df: interaction(_mr_conf(df), _slope_vel(df), "product"),
     inputs=["L3:market_regime.*", "L2:momentum_of_trend.*"])

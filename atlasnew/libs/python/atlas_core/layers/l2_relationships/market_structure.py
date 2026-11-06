"""Market Structure — Layer 2.

Book 1 places Market Structure explicitly in Layer 2 (Relationships).
Swings, HH/HL/LH/LL, BOS, CHoCH, structure regime, internal/external/
fractal structure and break strength are RELATIONSHIPS between local
extrema of already-measured price. They are not L1 measurements.

Data contract: L2 consumes L1 via the l1_bridge only. This module never
touches raw OHLCV directly except to source high/low/close via the
Registry (price.magnitude.*).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.engines import swings as sw, statistics as st
from atlas_core.layers.l2_relationships._l1_bridge import l1_series

MODULE = "market_structure"


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=2, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["L1:price.magnitude.high", "L1:price.magnitude.low",
                "L1:price.magnitude.close"],
        params=params or {}, complexity=complexity, fn=fn,
    ))


def _high(df):  return l1_series(df, "price.magnitude.high")
def _low(df):   return l1_series(df, "price.magnitude.low")
def _close(df): return l1_series(df, "price.magnitude.close")
def _atr(df):   return l1_series(df, "price.magnitude.atr_14")


# ══════════════════════════════════════════════════════════════════════
# MAGNITUDE — swing values (levels of the last confirmed pivots)
# ══════════════════════════════════════════════════════════════════════
for k in [3, 5, 10]:
    def _pivot_high_flag_fn(df, k_=k):
        return sw.confirmed_pivot_high(_high(df), k_)

    def _pivot_low_flag_fn(df, k_=k):
        return sw.confirmed_pivot_low(_low(df), k_)

    def _last_swing_high_fn(df, k_=k):
        return sw.last_swing_value(_high(df),
                                    sw.confirmed_pivot_high(_high(df), k_))

    def _last_swing_low_fn(df, k_=k):
        return sw.last_swing_value(_low(df),
                                    sw.confirmed_pivot_low(_low(df), k_))

    _reg(f"market_structure.regime.pivot_high_flag_k{k}",
         f"Pivot-High Flag (k={k})", "Regime", "pivot_flag",
         f"1 at bars where a swing high of neighbourhood {k} is confirmed.",
         "1[H_i > max(H_{i-k..i+k})]", "Local-extremum confirmation flag.",
         (lambda k_: (lambda df: _pivot_high_flag_fn(df, k_)))(k),
         params={"k": k})

    _reg(f"market_structure.regime.pivot_low_flag_k{k}",
         f"Pivot-Low Flag (k={k})", "Regime", "pivot_flag",
         f"1 at bars where a swing low of neighbourhood {k} is confirmed.",
         "1[L_i < min(L_{i-k..i+k})]", "Local-extremum confirmation flag.",
         (lambda k_: (lambda df: _pivot_low_flag_fn(df, k_)))(k),
         params={"k": k})

    _reg(f"market_structure.magnitude.last_swing_high_k{k}",
         f"Last Swing High (k={k})", "Magnitude", "swing_level",
         f"Value of the most recent confirmed swing high (k={k}).",
         "forward-fill of H at pivot_high", "Price level of last upper pivot.",
         (lambda k_: (lambda df: _last_swing_high_fn(df, k_)))(k),
         params={"k": k})

    _reg(f"market_structure.magnitude.last_swing_low_k{k}",
         f"Last Swing Low (k={k})", "Magnitude", "swing_level",
         f"Value of the most recent confirmed swing low (k={k}).",
         "forward-fill of L at pivot_low", "Price level of last lower pivot.",
         (lambda k_: (lambda df: _last_swing_low_fn(df, k_)))(k),
         params={"k": k})


# ══════════════════════════════════════════════════════════════════════
# REGIME — structural direction (HH, HL, LH, LL) and structure regime
# ══════════════════════════════════════════════════════════════════════
def _swing_hist(df, k, side="high", keep=4):
    if side == "high":
        return sw.swing_sequence(_high(df),
                                  sw.confirmed_pivot_high(_high(df), k), keep=keep)
    return sw.swing_sequence(_low(df),
                              sw.confirmed_pivot_low(_low(df), k), keep=keep)


for k in [3, 5]:
    def _hh(df, k_=k):
        h = _swing_hist(df, k_, "high")
        return (h["swing_1"] > h["swing_2"]).astype(float)
    def _lh(df, k_=k):
        h = _swing_hist(df, k_, "high")
        return (h["swing_1"] < h["swing_2"]).astype(float)
    def _hl(df, k_=k):
        h = _swing_hist(df, k_, "low")
        return (h["swing_1"] > h["swing_2"]).astype(float)
    def _ll(df, k_=k):
        h = _swing_hist(df, k_, "low")
        return (h["swing_1"] < h["swing_2"]).astype(float)

    _reg(f"market_structure.regime.hh_flag_k{k}", f"Higher-High Flag (k={k})",
         "Regime", "structural_flag",
         "1 when last swing high > previous swing high.",
         "swingH_1 > swingH_2", "Structural upside progression.",
         (lambda k_: (lambda df: _hh(df, k_)))(k), params={"k": k})
    _reg(f"market_structure.regime.lh_flag_k{k}", f"Lower-High Flag (k={k})",
         "Regime", "structural_flag",
         "1 when last swing high < previous swing high.",
         "swingH_1 < swingH_2", "Structural upside failure.",
         (lambda k_: (lambda df: _lh(df, k_)))(k), params={"k": k})
    _reg(f"market_structure.regime.hl_flag_k{k}", f"Higher-Low Flag (k={k})",
         "Regime", "structural_flag",
         "1 when last swing low > previous swing low.",
         "swingL_1 > swingL_2", "Structural downside protection.",
         (lambda k_: (lambda df: _hl(df, k_)))(k), params={"k": k})
    _reg(f"market_structure.regime.ll_flag_k{k}", f"Lower-Low Flag (k={k})",
         "Regime", "structural_flag",
         "1 when last swing low < previous swing low.",
         "swingL_1 < swingL_2", "Structural downside progression.",
         (lambda k_: (lambda df: _ll(df, k_)))(k), params={"k": k})

    def _regime(df, k_=k):
        return sw.structure_regime(_hh(df, k_), _hl(df, k_),
                                    _lh(df, k_), _ll(df, k_))
    _reg(f"market_structure.regime.structure_regime_k{k}",
         f"Structure Regime (k={k})", "Regime", "regime",
         "+1 bullish structure (HH ∧ HL), −1 bearish (LH ∧ LL), 0 mixed.",
         "sgn(bull) - sgn(bear)",
         "Composite structural regime from HH/HL/LH/LL.",
         (lambda k_: (lambda df: _regime(df, k_)))(k), params={"k": k})

    def _choch(df, k_=k):
        return sw.change_of_character(_regime(df, k_))
    _reg(f"market_structure.regime.choch_flag_k{k}",
         f"Change-of-Character Flag (k={k})", "Regime", "transition",
         "1 where the structure regime flips sign vs the previous non-zero regime.",
         "regime_t · regime_{t-1} < 0", "Structural direction reversal.",
         (lambda k_: (lambda df: _choch(df, k_)))(k), params={"k": k})


# ══════════════════════════════════════════════════════════════════════
# MOTION — break-of-structure signal (BOS)
# ══════════════════════════════════════════════════════════════════════
for k in [3, 5]:
    def _bos(df, k_=k):
        return sw.break_of_structure(
            _close(df),
            sw.last_swing_value(_high(df),
                                sw.confirmed_pivot_high(_high(df), k_)),
            sw.last_swing_value(_low(df),
                                sw.confirmed_pivot_low(_low(df), k_)),
        )
    _reg(f"market_structure.motion.bos_k{k}",
         f"Break-of-Structure Signal (k={k})", "Motion", "break_signal",
         "+1 if close > last swing high; −1 if close < last swing low; 0 else.",
         "sgn(C - swingH) - sgn(swingL - C)",
         "Structural break in the direction of the trend.",
         (lambda k_: (lambda df: _bos(df, k_)))(k), params={"k": k})


# ══════════════════════════════════════════════════════════════════════
# RELATIVE — break strength in ATR units
# ══════════════════════════════════════════════════════════════════════
for k in [3, 5]:
    def _bstr_up(df, k_=k):
        return sw.break_strength(
            _close(df),
            sw.last_swing_value(_high(df),
                                sw.confirmed_pivot_high(_high(df), k_)),
            _atr(df))
    def _bstr_dn(df, k_=k):
        return sw.break_strength(
            _close(df),
            sw.last_swing_value(_low(df),
                                sw.confirmed_pivot_low(_low(df), k_)),
            _atr(df))
    _reg(f"market_structure.relative.break_strength_up_k{k}",
         f"Upside Break Strength (k={k}, ATR-normalised)",
         "Relative", "break_strength",
         "(close - last_swing_high) / ATR14 — ATR-units of upside break.",
         "(C - swingH) / ATR_14",
         "Positive when trading above the last swing high.",
         (lambda k_: (lambda df: _bstr_up(df, k_)))(k), params={"k": k})
    _reg(f"market_structure.relative.break_strength_dn_k{k}",
         f"Downside Break Strength (k={k}, ATR-normalised)",
         "Relative", "break_strength",
         "(close - last_swing_low) / ATR14 — negative when below.",
         "(C - swingL) / ATR_14",
         "Negative when trading below the last swing low.",
         (lambda k_: (lambda df: _bstr_dn(df, k_)))(k), params={"k": k})


# ══════════════════════════════════════════════════════════════════════
# POSITION — close position between last swing high and last swing low
# ══════════════════════════════════════════════════════════════════════
for k in [3, 5]:
    def _pos(df, k_=k):
        sh = sw.last_swing_value(_high(df),
                                  sw.confirmed_pivot_high(_high(df), k_))
        sl = sw.last_swing_value(_low(df),
                                  sw.confirmed_pivot_low(_low(df), k_))
        rng = (sh - sl).replace(0, np.nan)
        return ((_close(df) - sl) / rng).clip(0, 1)
    _reg(f"market_structure.position.range_position_k{k}",
         f"Structural Range Position (k={k})", "Position", "range_position",
         "(close - last_swing_low) / (last_swing_high - last_swing_low) ∈ [0,1].",
         "(C - swingL) / (swingH - swingL)",
         "Where the close sits inside the last confirmed structural range.",
         (lambda k_: (lambda df: _pos(df, k_)))(k), params={"k": k})


# ══════════════════════════════════════════════════════════════════════
# GEOMETRY — fractal/internal/external structure via multi-k agreement
# ══════════════════════════════════════════════════════════════════════
def _internal_structure(df):
    r_small = _regime_k(df, 3)
    return r_small

def _external_structure(df):
    r_large = _regime_k(df, 10)
    return r_large

def _fractal_agreement(df):
    r3 = _regime_k(df, 3); r5 = _regime_k(df, 5); r10 = _regime_k(df, 10)
    # 1 when all three agree on non-zero direction; 0 otherwise
    agree = ((np.sign(r3) == np.sign(r5)) & (np.sign(r5) == np.sign(r10)) &
             (r3 != 0)).astype(float)
    return agree

def _regime_k(df, k):
    h = _swing_hist(df, k, "high"); l = _swing_hist(df, k, "low")
    hh = (h["swing_1"] > h["swing_2"]).astype(float)
    hl = (l["swing_1"] > l["swing_2"]).astype(float)
    lh = (h["swing_1"] < h["swing_2"]).astype(float)
    ll = (l["swing_1"] < l["swing_2"]).astype(float)
    return sw.structure_regime(hh, hl, lh, ll)

_reg("market_structure.geometry.internal_structure", "Internal Structure",
     "Geometry", "scale_structure",
     "Structure regime at the shortest neighbourhood (k=3).",
     "structure_regime_k3", "Fine-scale structural direction.",
     _internal_structure)

_reg("market_structure.geometry.external_structure", "External Structure",
     "Geometry", "scale_structure",
     "Structure regime at the longest neighbourhood (k=10).",
     "structure_regime_k10", "Coarse-scale structural direction.",
     _external_structure)

_reg("market_structure.geometry.fractal_agreement",
     "Fractal Structure Agreement", "Geometry", "scale_agreement",
     "1 when structure regimes at k=3, 5, 10 agree on non-zero direction.",
     "1[sgn(r3)=sgn(r5)=sgn(r10)≠0]",
     "Multi-scale structural alignment measurement.",
     _fractal_agreement)


# ══════════════════════════════════════════════════════════════════════
# STATISTICS — structure persistence: rolling frequency of same-sign regime
# ══════════════════════════════════════════════════════════════════════
for k in [3, 5]:
    for w in [20, 50]:
        def _persist(df, k_=k, w_=w):
            r = _regime_k(df, k_)
            return r.rolling(w_, min_periods=w_).mean()
        _reg(f"market_structure.statistics.regime_mean_k{k}_w{w}",
             f"Structure Regime Mean (k={k}, w={w})", "Statistics", "persistence",
             f"Rolling mean of structure_regime_k{k} over {w} bars ∈ [-1,+1].",
             "mean_w(structure_regime)",
             "Structural persistence — how consistently one side dominates.",
             (lambda k_, w_: (lambda df: _persist(df, k_, w_)))(k, w),
             params={"k": k, "window": w})


# ══════════════════════════════════════════════════════════════════════
# EXPANSION — structural range width vs its own history
# ══════════════════════════════════════════════════════════════════════
for k in [3, 5]:
    def _srange(df, k_=k):
        sh = sw.last_swing_value(_high(df),
                                  sw.confirmed_pivot_high(_high(df), k_))
        sl = sw.last_swing_value(_low(df),
                                  sw.confirmed_pivot_low(_low(df), k_))
        return sh - sl
    def _srange_ratio(df, k_=k):
        r = _srange(df, k_)
        return (r / r.rolling(50, min_periods=50).mean()).replace([np.inf, -np.inf], np.nan)
    _reg(f"market_structure.expansion.range_ratio_k{k}",
         f"Structural Range Ratio (k={k})", "Expansion", "range_ratio",
         "(swingH - swingL) / rolling mean.",
         "(swingH-swingL) / MA_50(·)",
         "Whether the structural range is widening or narrowing.",
         (lambda k_: (lambda df: _srange_ratio(df, k_)))(k), params={"k": k})


# ══════════════════════════════════════════════════════════════════════
# CLUSTERING — autocorrelation of the structure regime
# ══════════════════════════════════════════════════════════════════════
_reg("market_structure.clustering.regime_acf_lag1_50",
     "Structure Regime ACF (lag=1, w=50)", "Clustering", "autocorrelation",
     "Rolling lag-1 autocorrelation of structure_regime_k3.",
     "corr(r_t, r_{t-1}, 50)",
     "Persistence of structural direction from one bar to the next.",
     lambda df: st.rolling_autocorr(_regime_k(df, 3), 50, lag=1),
     params={"lag": 1, "window": 50})


# ══════════════════════════════════════════════════════════════════════
# DISTRIBUTION — fraction of bars flagged as BOS in the window (either side)
# ══════════════════════════════════════════════════════════════════════
_reg("market_structure.distribution.bos_frequency_50",
     "BOS Frequency (50)", "Distribution", "event_frequency",
     "Fraction of bars in the last 50 where BOS_k3 != 0.",
     "mean_50(|BOS| > 0)",
     "How eventful the structure has been recently.",
     lambda df: (sw.break_of_structure(
         _close(df),
         sw.last_swing_value(_high(df), sw.confirmed_pivot_high(_high(df), 3)),
         sw.last_swing_value(_low(df),  sw.confirmed_pivot_low(_low(df),  3))
     ).abs() > 0.5).astype(float).rolling(50, min_periods=50).mean(),
     params={"window": 50})


# ══════════════════════════════════════════════════════════════════════
# ENTROPY — Shannon entropy of the sequence of last-4 swing directions
# ══════════════════════════════════════════════════════════════════════
_reg("market_structure.entropy.regime_shannon_50",
     "Structure Regime Entropy (50)", "Entropy", "shannon",
     "Shannon entropy of the structure_regime_k3 histogram over 50 bars.",
     "H(regime, 3 bins)",
     "Structural predictability — lower = more directional.",
     lambda df: st.rolling_entropy(_regime_k(df, 3), 50, bins=3),
     params={"window": 50})

"""Meta features — Layer 4.

Book 1 Ch. 5 exemplar: meta features. Statistics of statistics.
See docs/L4_REPRESENTATION.md §6.2.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l4_representation._layer_bridge import (
    l1_series, l2_series, l3_series,
)
from atlas_core.layers.l4_representation._representation_kernel import (
    rolling_entropy, rolling_dispersion,
)

MODULE = "meta_features"


def _reg(id_, name, perspective, family, definition, formula, interp,
         fn, inputs, params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=4, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=params or {}, complexity=complexity, fn=fn,
    ))


L3_MODULES = ("trend_state", "range_state", "participation_state",
              "liquidity_state", "market_regime")


def _l3_confidences(df: pd.DataFrame) -> pd.DataFrame:
    cols = {m: l3_series(df, f"{m}.statistics.active_state_confidence")
            for m in L3_MODULES}
    return pd.DataFrame(cols, index=df.index)


def _l3_codes(df: pd.DataFrame) -> pd.DataFrame:
    cols = {m: l3_series(df, f"{m}.regime.active_state_code")
            for m in L3_MODULES}
    return pd.DataFrame(cols, index=df.index)


# --- Aggregate L3 confidences ---
def _conf_mean(df):
    C = _l3_confidences(df)
    return C.mean(axis=1).astype(float)
_reg(f"{MODULE}.statistics.l3_confidence_mean",
     "L3 confidence mean", "Statistics", "l3_agg",
     "Mean of L3 active_state_confidence across all 5 modules.",
     "mean(ts_conf, rs_conf, ps_conf, ls_conf, mr_conf)",
     "Overall L3 conviction level.",
     _conf_mean, inputs=["L3:*.statistics.active_state_confidence"])

def _conf_std(df):
    C = _l3_confidences(df)
    return C.std(axis=1, ddof=0).astype(float)
_reg(f"{MODULE}.statistics.l3_confidence_std",
     "L3 confidence std", "Statistics", "l3_agg",
     "Std of L3 active_state_confidence across 5 modules.",
     "std(l3_confidences)",
     "Divergence of conviction across L3 state families.",
     _conf_std, inputs=["L3:*.statistics.active_state_confidence"])

def _conf_min(df): return _l3_confidences(df).min(axis=1).astype(float)
_reg(f"{MODULE}.statistics.l3_confidence_min",
     "L3 confidence min", "Statistics", "l3_agg",
     "Weakest-family L3 confidence at each bar.", "min(l3_confidences)",
     "Weakest state conviction across families.",
     _conf_min, inputs=["L3:*.statistics.active_state_confidence"])

def _conf_max(df): return _l3_confidences(df).max(axis=1).astype(float)
_reg(f"{MODULE}.statistics.l3_confidence_max",
     "L3 confidence max", "Statistics", "l3_agg",
     "Strongest-family L3 confidence at each bar.", "max(l3_confidences)",
     "Strongest state conviction across families.",
     _conf_max, inputs=["L3:*.statistics.active_state_confidence"])

# --- Rolling statistics of confidence mean ---
def _mean_ma_20(df):
    return _conf_mean(df).rolling(20, min_periods=5).mean().astype(float)
_reg(f"{MODULE}.statistics.l3_confidence_mean_ma_20",
     "L3 confidence mean (20-MA)", "Statistics", "l3_agg",
     "20-bar moving average of L3 confidence mean.",
     "MA_20(mean(l3_confidences))", "Smoothed L3 conviction.",
     _mean_ma_20, inputs=[f"L4:{MODULE}.statistics.l3_confidence_mean"])

def _mean_std_20(df):
    return _conf_mean(df).rolling(20, min_periods=5).std(ddof=0).astype(float)
_reg(f"{MODULE}.statistics.l3_confidence_mean_std_20",
     "L3 confidence mean (20-bar std)", "Statistics", "l3_agg",
     "20-bar std of the L3 confidence mean series.",
     "std_20(mean(l3_confidences))",
     "Stability of overall L3 conviction across 20 bars.",
     _mean_std_20, inputs=[f"L4:{MODULE}.statistics.l3_confidence_mean"])

# --- Entropy of L3 code distribution ---
def _flag_entropy(df):
    codes = _l3_codes(df)
    # Combine into a single categorical: dot product against a modulus vector.
    # Distinct combos across 20 bars; use rolling_entropy over the code sums.
    combo = (codes.fillna(0.0) * np.array([1, 6, 36, 216, 1296])).sum(axis=1)
    return rolling_entropy(combo, window=20, bins=8).astype(float)
_reg(f"{MODULE}.entropy.l3_flag_entropy_20",
     "L3 flag entropy (20-bar)", "Entropy", "l3_diversity",
     "Shannon entropy of the joint L3 active-state code over 20 bars.",
     "H(joint_code_20)",
     "How diverse the L3 state history has been across the window.",
     _flag_entropy, inputs=["L3:*.regime.active_state_code"])

# --- Cross-family direction agreement ---
def _family_agreement(df):
    codes = _l3_codes(df)
    # Direction interpretation: trend_state code 1 = continuation (+),
    # code 2/3 = exhaustion/reversal (-); participation code 1 = accum (+),
    # code 2 = distribution (-); liquidity 1 = sweep_up (-), 2 = sweep_down (+).
    def _dir_ts(c): return np.where(c == 1, 1, np.where((c == 2) | (c == 3), -1, 0))
    def _dir_ps(c): return np.where(c == 1, 1, np.where(c == 2, -1, 0))
    def _dir_ls(c): return np.where(c == 2, 1, np.where(c == 1, -1, 0))
    ts_dir = _dir_ts(codes["trend_state"].values)
    ps_dir = _dir_ps(codes["participation_state"].values)
    ls_dir = _dir_ls(codes["liquidity_state"].values)
    M = np.column_stack([ts_dir, ps_dir, ls_dir]).astype(float)
    finite = M != 0
    ct = finite.sum(axis=1)
    net = np.abs(M.sum(axis=1))
    score = np.divide(net, ct, out=np.zeros_like(net), where=ct>0)
    return pd.Series(score, index=df.index, dtype=float)
_reg(f"{MODULE}.regime.l3_family_agreement_score",
     "L3 family agreement score", "Regime", "l3_agree",
     "|net direction| / #signed families across directional L3 families.",
     "|sum(sign_families)| / count(sign≠0)",
     "How coherent the direction-bearing L3 families are.",
     _family_agreement, inputs=["L3:*.regime.active_state_code"])

# --- L2 consensus meta ---
def _consensus_score(df): return l2_series(df, "trend_relationships.regime.directional_consensus_score_20")

def _cons_mean_50(df):
    return _consensus_score(df).rolling(50, min_periods=10).mean().astype(float)
_reg(f"{MODULE}.statistics.l2_consensus_mean_50",
     "L2 consensus mean (50-bar)", "Statistics", "l2_agg",
     "50-bar mean of directional consensus score.",
     "MA_50(consensus_score_20)", "Persistent L2 trend agreement.",
     _cons_mean_50,
     inputs=["L2:trend_relationships.regime.directional_consensus_score_20"])

def _cons_disp_50(df):
    return rolling_dispersion(_consensus_score(df), 50).astype(float)
_reg(f"{MODULE}.statistics.l2_consensus_dispersion_50",
     "L2 consensus dispersion (50-bar CV)", "Statistics", "l2_agg",
     "Coefficient of variation of consensus_score over 50 bars.",
     "CV_50(consensus_score_20)", "Instability of L2 trend agreement.",
     _cons_disp_50,
     inputs=["L2:trend_relationships.regime.directional_consensus_score_20"])

# --- Confidence rank over 100 bars ---
def _conf_mean_rank_100(df):
    m = _conf_mean(df)
    # Rank of last value in trailing window.
    return m.rolling(100, min_periods=20).apply(
        lambda w: float((w <= w[-1]).sum()) / float(len(w)), raw=True)
_reg(f"{MODULE}.position.l3_confidence_mean_rank_100",
     "L3 confidence mean (100-bar rank)", "Position", "l3_agg",
     "Percentile rank of the L3 confidence mean over 100 bars.",
     "rank_100(mean(l3_confidences))",
     "Whether current L3 conviction is historically high or low.",
     _conf_mean_rank_100,
     inputs=[f"L4:{MODULE}.statistics.l3_confidence_mean"])

# --- Range of confidences (spread) ---
def _conf_range(df):
    C = _l3_confidences(df)
    return (C.max(axis=1) - C.min(axis=1)).astype(float)
_reg(f"{MODULE}.statistics.l3_confidence_range",
     "L3 confidence range", "Statistics", "l3_agg",
     "max - min of L3 confidences at each bar.",
     "max(l3_confidences) - min(l3_confidences)",
     "Spread of conviction across the L3 families.",
     _conf_range, inputs=["L3:*.statistics.active_state_confidence"])

# --- Fraction of L3 families with non-none active state ---
def _active_fraction(df):
    codes = _l3_codes(df)
    active = (codes > 0).sum(axis=1).astype(float)
    return (active / float(len(L3_MODULES))).astype(float)
_reg(f"{MODULE}.position.l3_active_family_fraction",
     "L3 active family fraction", "Position", "l3_diversity",
     "Fraction of L3 families with a non-zero active_state_code.",
     "count(code>0) / 5",
     "How many L3 families have declared a state at this bar.",
     _active_fraction, inputs=["L3:*.regime.active_state_code"])

# --- Confidence z-score of the mean ---
def _conf_mean_z_100(df):
    m = _conf_mean(df)
    from atlas_core.layers.l4_representation._representation_kernel import rolling_zscore
    return rolling_zscore(m, 100).astype(float)
_reg(f"{MODULE}.statistics.l3_confidence_mean_z_100",
     "L3 confidence mean (100-bar z)", "Statistics", "l3_agg",
     "100-bar z-score of the L3 confidence mean.",
     "z_100(mean(l3_confidences))",
     "How anomalous current L3 conviction is vs the last 100 bars.",
     _conf_mean_z_100,
     inputs=[f"L4:{MODULE}.statistics.l3_confidence_mean"])

# --- Confidence agreement momentum (change in agreement over 5 bars) ---
def _agreement_delta_5(df):
    a = _family_agreement(df)
    return (a - a.shift(5)).astype(float)
_reg(f"{MODULE}.motion.l3_family_agreement_delta_5",
     "L3 family agreement delta (5-bar)", "Motion", "l3_agree",
     "5-bar change in L3 family agreement score.",
     "agreement_t - agreement_{t-5}",
     "Whether the market is becoming more or less coherent across L3.",
     _agreement_delta_5,
     inputs=[f"L4:{MODULE}.regime.l3_family_agreement_score"])

from typing import Dict, Any, List
from .l1_primitive import *
from .l2_cross_feature import *
from .l3_state import *
import pandas as pd
import numpy as np
from atlas_core.compute import compute_features
from .core import _get, _make_signal, _row
from .l3_state import _l3_signal

def range_state_signal(v: Dict[str, float]) -> dict:
    """L3 `range_state`. Direction-neutral by design (Book 1 Ch. 5)."""
    labels = {0: "none", 1: "range_formation",
              2: "breakout_environment", 3: "range_expansion"}
    return _l3_signal("RangeState", "range_state",
                      {0: 0, 1: 0, 2: 0, 3: 0}, labels, v)


def participation_state_signal(v: Dict[str, float]) -> dict:
    """L3 `participation_state`. Accumulation=+1, Distribution=-1,
    MeanReversion=0 (fades are direction-neutral at signal level)."""
    labels = {0: "none", 1: "accumulation", 2: "distribution", 3: "mean_reversion"}
    return _l3_signal("ParticipationState", "participation_state",
                      {0: 0, 1: +1, 2: -1, 3: 0}, labels, v)


def regime_state_signal(v: Dict[str, float]) -> dict:
    """L3 `market_regime`. Four-way regime classification is direction-neutral;
    used by the DE as a context signal — voters can be regime-conditioned in v0.9+."""
    labels = {0: "none", 1: "trending_quiet", 2: "trending_volatile",
              3: "ranging_quiet", 4: "ranging_volatile"}
    return _l3_signal("RegimeState", "market_regime",
                      {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}, labels, v)


def crossflow_signal(v: Dict[str, float]) -> dict:
    """L4 `cross_module_interactions`. Combines trend×volume and
    structure×momentum interactions into a single directional signal.
    Direction = sign of the dominant interaction; strength = |mean of
    magnitudes|; confidence = fraction of interactions with the same sign."""
    ev = []
    tv_signed = _get(v, "cross_module_interactions.motion.trend_x_volume_signed_20")
    tv_agree = _get(v, "cross_module_interactions.motion.trend_x_volume_sign_agree_20")
    sm_signed = _get(v, "cross_module_interactions.motion.structure_x_momentum_product_20")
    sm_agree = _get(v, "cross_module_interactions.motion.structure_x_momentum_agree_20")
    cons_x_vel = _get(v, "cross_module_interactions.motion.consensus_x_slopevel")
    mr_x_vel = _get(v, "cross_module_interactions.motion.mr_conf_x_slopevel")

    signed_evidence = [x for x in (tv_signed, sm_signed, cons_x_vel, mr_x_vel)
                       if x is not None]
    if not signed_evidence:
        return _make_signal("CrossFlow", 0, 0.0, 0.3,
                            [{"note": "no cross-module evidence available"}])
    net = sum(signed_evidence)
    mag = sum(abs(x) for x in signed_evidence) / len(signed_evidence)
    direction = 1 if net > 1e-6 else (-1 if net < -1e-6 else 0)
    signs = [1 if x > 0 else (-1 if x < 0 else 0) for x in signed_evidence]
    non_zero = [s for s in signs if s != 0]
    agree = (abs(sum(non_zero)) / len(non_zero)) if non_zero else 0.0
    strength = max(0.0, min(1.0, mag / (1.0 + mag)))

    for fid, val in (("cross_module_interactions.motion.trend_x_volume_signed_20", tv_signed),
                      ("cross_module_interactions.motion.trend_x_volume_sign_agree_20", tv_agree),
                      ("cross_module_interactions.motion.structure_x_momentum_product_20", sm_signed),
                      ("cross_module_interactions.motion.structure_x_momentum_agree_20", sm_agree),
                      ("cross_module_interactions.motion.consensus_x_slopevel", cons_x_vel),
                      ("cross_module_interactions.motion.mr_conf_x_slopevel", mr_x_vel)):
        if val is not None:
            ev.append(_row(fid, val, f"interaction={val:+.3f}", 1.0 / 6))
    return _make_signal("CrossFlow", direction, strength, agree, ev)


def meta_confidence_signal(v: Dict[str, float]) -> dict:
    """L4 `meta_features`. Direction-neutral. Strength = L3-family
    agreement score; confidence = 1 - L3 confidence std (higher when
    families agree in magnitude too)."""
    ev = []
    agree = _get(v, "meta_features.regime.l3_family_agreement_score")
    conf_std = _get(v, "meta_features.statistics.l3_confidence_std")
    conf_mean = _get(v, "meta_features.statistics.l3_confidence_mean")
    if agree is None:
        return _make_signal("MetaConfidence", 0, 0.0, 0.3,
                            [{"note": "meta_features not in snapshot"}])
    strength = max(0.0, min(1.0, float(agree)))
    if conf_std is not None:
        confidence = max(0.0, min(1.0, 1.0 - float(conf_std)))
    else:
        confidence = 0.5
    ev.append(_row("meta_features.regime.l3_family_agreement_score", agree,
                   f"L3-family direction agreement = {agree:.2f}", 0.5))
    if conf_std is not None:
        ev.append(_row("meta_features.statistics.l3_confidence_std", conf_std,
                       f"L3-confidence dispersion = {conf_std:.2f}", 0.3))
    if conf_mean is not None:
        ev.append(_row("meta_features.statistics.l3_confidence_mean", conf_mean,
                       f"L3-confidence mean = {conf_mean:.2f}", 0.2))
    return _make_signal("MetaConfidence", 0, strength, confidence, ev)


# Registry of signals
SIGNAL_FUNCS = [
    ("Trend", trend_signal),
    ("Momentum", momentum_signal),
    ("TrendMomentum", trend_momentum_signal),     # v0.7   (L2 · momentum_of_trend)
    ("TrendAlignment", trend_alignment_signal),   # v0.7.1 (L2 · trend_relationships)
    ("FractalCoherence", fractal_coherence_signal), # v0.7.2 (L2 · fractal_relationships)
    ("RelativeStrength", relative_strength_signal), # v0.7.3 (L2 · relative_strength)
    ("Regime", regime_signal),
    ("Structure", structure_signal),
    ("MeanReversion", meanrev_signal),
    ("Volatility", volatility_signal),
    ("Volume", volume_signal),
    ("Liquidity", liquidity_signal),
    ("Microstructure", microstructure_signal),   # v0.6 (L1)
    ("MarketStructure", market_structure_signal), # v0.6 (L2)
    ("Entropy", entropy_signal),
    # ─── v0.8.0 · Layer-3 state signals ─────────────────────────────
    ("TrendState", trend_state_signal),               # v0.8.0 (L3 · trend_state)
    ("RangeState", range_state_signal),               # v0.8.0 (L3 · range_state)
    ("ParticipationState", participation_state_signal), # v0.8.0 (L3 · participation_state)
    ("LiquidityState", liquidity_state_signal),       # v0.8.0 (L3 · liquidity_state)
    ("RegimeState", regime_state_signal),             # v0.8.0 (L3 · market_regime)
    # ─── v0.9.0 · Layer-4 derived signals ────────────────────────────
    ("CrossFlow", crossflow_signal),                  # v0.9.0 (L4 · cross_module_interactions)
    ("MetaConfidence", meta_confidence_signal),       # v0.9.0 (L4 · meta_features)
]

# Feature IDs required by the signals — reads from proper modules per Book 1.
SIGNAL_FEATURE_IDS = sorted({
    # Price-driven signals
    "price.regime.above_sma_200", "price.regime.ma50_above_ma200",
    "price.motion.lr_slope_50", "price.geometry.lr_r2_50",
    "price.geometry.straightness_50",
    "price.motion.log_return_10", "price.motion.log_return_20",
    "price.motion.ema_diff_5_20", "price.motion.ema_diff_20_50",
    "price.regime.chande_momentum_14",
    "price.geometry.hurst_64", "price.regime.choppiness_14",
    "price.geometry.higuchi_fd_50",
    "price.entropy.perm_o3_w30", "price.entropy.spectral_60",
    "price.entropy.sample_60",
    "price.position.bb_percent_b_20_k2", "price.position.fisher_20",
    "price.statistics.zscore_20",
    "price.regime.aroon_up_14", "price.regime.aroon_dn_14",
    "price.regime.vortex_up_14", "price.regime.vortex_dn_14",
    "price.regime.adx_14",
    # Volatility-driven signal reads from volatility module
    "volatility.regime.tercile_200",
    "volatility.expansion.short_long_ratio",
    "volatility.regime.abs_ret_persistence_60",
    "volatility.magnitude.semi_ratio_20",
    # Volume-driven signal reads from volume module
    "volume.regime.pv_confirmation_20",
    "volume.regime.signed_ema_20",
    "volume.position.pct_rank_100",
    "volume.relative.price_vs_vwap_20",
    # Liquidity-driven signal reads from liquidity module
    "liquidity.regime.tercile_200",
    "liquidity.expansion.short_long_ratio",
    "liquidity.regime.kyle_above_ma_50",
    "liquidity.magnitude.turnover_20",
    # Microstructure (L1) — v0.6
    "microstructure.expansion.execution_imbalance_20",
    "microstructure.expansion.range_covered_20",
    "microstructure.geometry.wick_difference_ratio",
    "microstructure.regime.high_participation_flag_20",
    # Market Structure (L2) — v0.6
    "market_structure.motion.bos_k5",
    "market_structure.regime.structure_regime_k5",
    "market_structure.geometry.fractal_agreement",
    "market_structure.regime.choch_flag_k5",
    # Momentum of Trend (L2) — v0.7
    "momentum_of_trend.motion.lr_slope_20_velocity_20",
    "momentum_of_trend.motion.adx_14_velocity_20",
    "momentum_of_trend.relative.velocity_sign_agreement_20",
    "momentum_of_trend.regime.lr_slope_20_direction_persistence_20",
    # Trend Relationships (L2) — v0.7.1
    "trend_relationships.regime.directional_consensus_sign_20",
    "trend_relationships.regime.directional_consensus_score_20",
    "trend_relationships.regime.all_sources_agree_flag_20",
    "trend_relationships.geometry.ema_cascade_signed_10_20_50_100",
    "trend_relationships.geometry.ema_cascade_score_10_20_50_100",
    # Fractal Relationships (L2) — v0.7.2
    "fractal_relationships.regime.self_similarity_score",
    "fractal_relationships.regime.self_similarity_flag",
    "fractal_relationships.geometry.variance_scaling_exponent_2_64",
    "fractal_relationships.statistics.multifractal_spread_h1_minus_h3_2_32",
    "fractal_relationships.distribution.variance_ratio_max_deviation_from_unity_2_16",
    # Relative Strength (L2) — v0.7.3 (direction-neutral signal)
    "relative_strength.magnitude.rs_20",
    "relative_strength.magnitude.rs_50",
    "relative_strength.statistics.corr_50",
    "relative_strength.expansion.relvol_50",
    "relative_strength.entropy.cointegration_resid_std_100",
    # ─── L3 · v0.8.0 · state-family compact reads ────────────────────
    # Each module needs only its active_state_code + confidence for the
    # DE signal; the underlying score/flag features are still computed
    # inside compute_features via the L3 orchestration, so the snapshot
    # remains a single call.
    "trend_state.regime.active_state_code",
    "trend_state.statistics.active_state_confidence",
    "range_state.regime.active_state_code",
    "range_state.statistics.active_state_confidence",
    "participation_state.regime.active_state_code",
    "participation_state.statistics.active_state_confidence",
    "liquidity_state.regime.active_state_code",
    "liquidity_state.statistics.active_state_confidence",
    "market_regime.regime.active_state_code",
    "market_regime.statistics.active_state_confidence",
    # ─── L4 · v0.9.0 · signal feeds ─────────────────────────────────
    # CrossFlow reads six cross_module_interactions.motion.* features.
    "cross_module_interactions.motion.trend_x_volume_signed_20",
    "cross_module_interactions.motion.trend_x_volume_sign_agree_20",
    "cross_module_interactions.motion.structure_x_momentum_product_20",
    "cross_module_interactions.motion.structure_x_momentum_agree_20",
    "cross_module_interactions.motion.consensus_x_slopevel",
    "cross_module_interactions.motion.mr_conf_x_slopevel",
    # MetaConfidence reads three meta_features.*
    "meta_features.regime.l3_family_agreement_score",
    "meta_features.statistics.l3_confidence_std",
    "meta_features.statistics.l3_confidence_mean",
})


def compute_all_signals(df: pd.DataFrame,
                        context: Dict[str, pd.DataFrame] = None) -> Dict[str, Any]:
    """Compute the small feature snapshot then evaluate every signal.

    context: optional dict of aux DataFrames (e.g. {"peer": peer_df}) forwarded
    to compute_features. When present, cross-symbol L2 features
    (relative_strength.*) populate; when absent, they return NaN and their
    consumer signal degrades gracefully. DEC-007 pathway.
    """
    X = compute_features(df, SIGNAL_FEATURE_IDS, context=context)
    last = X.iloc[-1].to_dict() if len(X) else {}
    # sanitize NaN
    last = {k: (float(v) if v is not None and np.isfinite(v) else None)
            for k, v in last.items()}
    signals = []
    for name, fn in SIGNAL_FUNCS:
        try:
            signals.append(fn(last))
        except Exception as e:
            signals.append(_make_signal(name, 0, 0.0, 0.0,
                                        [{"error": str(e)}]))
    return {"signals": signals, "feature_snapshot": last}

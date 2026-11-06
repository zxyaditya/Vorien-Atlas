"""Trend Relationships — Layer 2 (Book 1 Ch. 5, named exemplar).

Full mathematical specification: /app/docs/L2_SPECS/TREND_RELATIONSHIPS.md

Purpose
-------
Measure how *multiple independent trend measurements* agree, disagree,
reinforce or contradict each other across different methodologies
(LR-slope, EMA-slope, Aroon oscillator, ADX, LR-R²) and timescales
(20-bar vs 50-bar, EMA cascade 10 → 20 → 50 → 100).

This module is COMPLEMENTARY to `momentum_of_trend`.  It never measures
how a trend changes over time — that is momentum_of_trend's exclusive
axis.  It only measures cross-source and cross-scale coherence.

Registered features (20 total, 5 Perspectives)
---------------------------------------------
Relative (7): cross-scale + cross-methodology sign products; ratios; span.
Geometry (4): EMA-cascade ordering (score, signed, span).
Regime   (3): consensus score, consensus sign, all-agree flag.
Statistics (3): rolling correlation and rolling stats of consensus.
Position (3): rolling percentile ranks.

Every input is a Registry lookup via `_l1_bridge.l1_series`.  No direct
OHLCV read.  Enforced by pytest.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l2_relationships._l1_bridge import l1_series

MODULE = "trend_relationships"
EPS = 1e-12


# ── Registered-source aliases (kept in one place so the DE review + tests
#    can cross-reference exactly what this module consumes) ────────────────
SRC = {
    "slope_20":     "price.motion.lr_slope_20",
    "slope_50":     "price.motion.lr_slope_50",
    "ema_slope_20": "price.motion.ema_slope_20",
    "aroon_14":     "price.regime.aroon_osc_14",
    "adx_14":       "price.regime.adx_14",
    "r2_20":        "price.geometry.lr_r2_20",
    "ema_10":       "price.motion.ema_10",
    "ema_20":       "price.motion.ema_20",
    "ema_50":       "price.motion.ema_50",
    "ema_100":      "price.motion.ema_100",
}

# Signed trend sources used across the module (consensus, agreement, ...).
SIGNED_SOURCES_20 = ["slope_20", "ema_slope_20", "aroon_14"]


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         inputs, params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=2, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=params or {}, complexity=complexity, fn=fn,
    ))


def _sign(s: pd.Series) -> pd.Series:
    """Signed indicator; NaN → 0 so downstream sign-products propagate as
    'no direction' rather than NaN."""
    return np.sign(s.fillna(0.0)).astype(int)


def _safe_div(a: pd.Series, b: pd.Series, clip: float = 10.0) -> pd.Series:
    """Element-wise a / b with |b|<ε protected and result clipped to
    [-clip, +clip] so extreme ratios can't hijack downstream statistics."""
    denom = b.copy()
    denom = denom.where(denom.abs() > EPS, np.sign(denom).replace(0, 1) * EPS)
    r = a / denom
    return r.clip(-clip, clip)


# ─── Section 4.1 · Relative (cross-scale + cross-methodology) ─────────────

def _slope_cross_scale_agreement(df) -> pd.Series:
    return _sign(l1_series(df, SRC["slope_20"])) * _sign(l1_series(df, SRC["slope_50"]))


def _slope_lr_ema_agreement(df) -> pd.Series:
    return _sign(l1_series(df, SRC["slope_20"])) * _sign(l1_series(df, SRC["ema_slope_20"]))


def _slope_aroon_agreement(df) -> pd.Series:
    return _sign(l1_series(df, SRC["slope_20"])) * _sign(l1_series(df, SRC["aroon_14"]))


def _slope_ratio_20_50(df) -> pd.Series:
    return _safe_div(l1_series(df, SRC["slope_20"]), l1_series(df, SRC["slope_50"]), clip=10.0)


def _slope_divergence_20_50(df) -> pd.Series:
    s20 = l1_series(df, SRC["slope_20"])
    s50 = l1_series(df, SRC["slope_50"])
    denom = s50.abs() + EPS
    return (s20 - s50) / denom


def _short_long_slope_sign_diff(df) -> pd.Series:
    return _sign(l1_series(df, SRC["slope_20"])) - _sign(l1_series(df, SRC["slope_50"]))


def _methodology_sign_span_20(df) -> pd.Series:
    """max(sign_i) - min(sign_i) across the three signed sources; equals 0
    iff all three sources agree on sign at bar t."""
    S = pd.concat(
        [_sign(l1_series(df, SRC[k])) for k in SIGNED_SOURCES_20],
        axis=1,
    )
    return (S.max(axis=1) - S.min(axis=1)).astype(float)


_reg(f"{MODULE}.relative.slope_cross_scale_agreement_20_50",
     "Slope Cross-Scale Sign Agreement (20 vs 50)",
     "Relative", "cross_scale_sign_product",
     "Sign product of the 20-bar and 50-bar LR-slopes.",
     "sign(lr_slope_20) · sign(lr_slope_50) ∈ {-1, 0, +1}",
     "+1 short- and long-term trends agree; -1 they oppose; 0 flat.",
     _slope_cross_scale_agreement,
     inputs=[f"L1:{SRC['slope_20']}", f"L1:{SRC['slope_50']}"])

_reg(f"{MODULE}.relative.slope_lr_ema_agreement_20",
     "Slope LR↔EMA Methodology Sign Agreement (20)",
     "Relative", "cross_methodology_sign_product",
     "Sign product of the two 20-bar slope methodologies (LR and EMA).",
     "sign(lr_slope_20) · sign(ema_slope_20)",
     "+1 both methodologies agree; -1 they oppose; 0 either flat.",
     _slope_lr_ema_agreement,
     inputs=[f"L1:{SRC['slope_20']}", f"L1:{SRC['ema_slope_20']}"])

_reg(f"{MODULE}.relative.slope_aroon_agreement_20_14",
     "Slope↔Aroon Methodology Sign Agreement (20 vs 14)",
     "Relative", "cross_methodology_sign_product",
     "Sign product of lr_slope_20 and aroon_osc_14.",
     "sign(lr_slope_20) · sign(aroon_osc_14)",
     "+1 slope and Aroon agree; -1 they oppose; 0 either flat.",
     _slope_aroon_agreement,
     inputs=[f"L1:{SRC['slope_20']}", f"L1:{SRC['aroon_14']}"])

_reg(f"{MODULE}.relative.slope_ratio_20_50",
     "Slope Cross-Scale Ratio (20/50)",
     "Relative", "cross_scale_ratio",
     "20-bar slope divided by 50-bar slope; safe-divided and clipped to [-10, +10].",
     "clip(lr_slope_20 / lr_slope_50, [-10, +10])",
     "> 1 short-term stronger than long-term; < 0 short-term reversing.",
     _slope_ratio_20_50,
     inputs=[f"L1:{SRC['slope_20']}", f"L1:{SRC['slope_50']}"],
     params={"clip": 10.0})

_reg(f"{MODULE}.relative.slope_divergence_20_50",
     "Slope Cross-Scale Divergence (20 vs 50)",
     "Relative", "cross_scale_divergence",
     "Signed relative divergence of the short-scale slope from the long-scale slope.",
     "(lr_slope_20 − lr_slope_50) / (|lr_slope_50| + ε)",
     "Positive short is above long-term slope; negative reversal underway.",
     _slope_divergence_20_50,
     inputs=[f"L1:{SRC['slope_20']}", f"L1:{SRC['slope_50']}"])

_reg(f"{MODULE}.relative.short_long_slope_sign_diff_20_50",
     "Short/Long Slope-Sign Difference (20 − 50)",
     "Relative", "cross_scale_sign_diff",
     "Difference of the sign of the 20-bar slope and the sign of the 50-bar slope.",
     "sign(lr_slope_20) − sign(lr_slope_50) ∈ {−2, −1, 0, +1, +2}",
     "0 aligned or both flat; ±2 fully-opposite regimes at the two scales.",
     _short_long_slope_sign_diff,
     inputs=[f"L1:{SRC['slope_20']}", f"L1:{SRC['slope_50']}"])

_reg(f"{MODULE}.relative.methodology_sign_span_20",
     "Cross-Methodology Sign Span (20)",
     "Relative", "cross_methodology_span",
     "Span (max − min) of signs across {lr_slope_20, ema_slope_20, aroon_osc_14}.",
     "max_i sign(T_i) − min_i sign(T_i) ∈ {0, 1, 2}",
     "0 all three methodologies agree; 2 at least one methodology fully opposes.",
     _methodology_sign_span_20,
     inputs=[f"L1:{SRC[k]}" for k in SIGNED_SOURCES_20])


# ─── Section 4.2 · Geometry (EMA cascade ordering) ────────────────────────

def _cascade_score_up(emas: list[pd.Series]) -> pd.Series:
    """Fraction of adjacent pairs (fast > slow) — up-cascade score in [0, 1]."""
    n = len(emas) - 1
    if n <= 0:
        return pd.Series(np.nan, index=emas[0].index)
    hits = sum((emas[i] > emas[i + 1]).astype(int) for i in range(n))
    return hits / n


def _cascade_signed(emas: list[pd.Series]) -> pd.Series:
    """Signed cascade: +1 all up-ordered, -1 all down-ordered, else
    (up_pairs − down_pairs)/n_pairs in [-1, +1]."""
    n = len(emas) - 1
    if n <= 0:
        return pd.Series(np.nan, index=emas[0].index)
    up = sum((emas[i] > emas[i + 1]).astype(int) for i in range(n))
    dn = sum((emas[i] < emas[i + 1]).astype(int) for i in range(n))
    return (up - dn) / n


def _cascade4(df) -> pd.Series:
    emas = [l1_series(df, SRC[k]) for k in ("ema_10", "ema_20", "ema_50", "ema_100")]
    return _cascade_score_up(emas)


def _cascade4_signed(df) -> pd.Series:
    emas = [l1_series(df, SRC[k]) for k in ("ema_10", "ema_20", "ema_50", "ema_100")]
    return _cascade_signed(emas)


def _cascade3(df) -> pd.Series:
    emas = [l1_series(df, SRC[k]) for k in ("ema_10", "ema_20", "ema_50")]
    return _cascade_score_up(emas)


def _ema_span_normalized(df) -> pd.Series:
    ema10 = l1_series(df, SRC["ema_10"])
    ema100 = l1_series(df, SRC["ema_100"])
    return (ema10 - ema100) / (ema100.abs() + EPS)


_reg(f"{MODULE}.geometry.ema_cascade_score_10_20_50_100",
     "EMA Cascade Score (10 → 20 → 50 → 100)",
     "Geometry", "ema_cascade",
     "Fraction of adjacent pairs in (EMA10, EMA20, EMA50, EMA100) that are ordered fast > slow.",
     "mean 1[EMA_i > EMA_{i+1}] over i = 1..3",
     "1 fully-up cascade; 0 fully-down cascade; ∼0.5 broken cascade.",
     _cascade4,
     inputs=[f"L1:{SRC[k]}" for k in ("ema_10", "ema_20", "ema_50", "ema_100")])

_reg(f"{MODULE}.geometry.ema_cascade_signed_10_20_50_100",
     "EMA Cascade Signed (10 → 20 → 50 → 100)",
     "Geometry", "ema_cascade",
     "Signed cascade: +1 fully up-ordered, -1 fully down-ordered, fractional otherwise.",
     "(up_pairs − down_pairs) / 3 ∈ [-1, +1]",
     "+1 clean up-cascade; -1 clean down-cascade; near 0 ambiguous.",
     _cascade4_signed,
     inputs=[f"L1:{SRC[k]}" for k in ("ema_10", "ema_20", "ema_50", "ema_100")])

_reg(f"{MODULE}.geometry.ema_cascade_score_10_20_50",
     "EMA Cascade Score (10 → 20 → 50)",
     "Geometry", "ema_cascade",
     "Fraction of adjacent pairs in (EMA10, EMA20, EMA50) that are ordered fast > slow.",
     "mean 1[EMA_i > EMA_{i+1}] over i = 1..2",
     "1 fully-up 3-EMA cascade; 0 fully-down; 0.5 broken.",
     _cascade3,
     inputs=[f"L1:{SRC[k]}" for k in ("ema_10", "ema_20", "ema_50")])

_reg(f"{MODULE}.geometry.ema_span_normalized_10_100",
     "EMA Span Normalized (10 minus 100 over 100)",
     "Geometry", "ema_cascade_span",
     "Signed magnitude of the EMA cascade span, normalised by EMA100.",
     "(EMA10 − EMA100) / (|EMA100| + ε)",
     "Positive fast > slow (up-cascade magnitude); negative down-cascade.",
     _ema_span_normalized,
     inputs=[f"L1:{SRC['ema_10']}", f"L1:{SRC['ema_100']}"])


# ─── Section 4.3 · Regime (directional consensus across signed sources) ───

def _signed_matrix(df) -> pd.DataFrame:
    return pd.concat(
        [_sign(l1_series(df, SRC[k])).rename(k) for k in SIGNED_SOURCES_20],
        axis=1,
    )


def _consensus_score(df) -> pd.Series:
    S = _signed_matrix(df)
    modal = S.apply(lambda r: (1 if (r > 0).sum() > (r < 0).sum()
                               else (-1 if (r < 0).sum() > (r > 0).sum() else 0)),
                    axis=1)
    match = S.eq(modal, axis=0).sum(axis=1) / max(1, S.shape[1])
    return match


def _consensus_sign(df) -> pd.Series:
    S = _signed_matrix(df)
    return S.apply(lambda r: (1 if (r > 0).sum() > (r < 0).sum()
                              else (-1 if (r < 0).sum() > (r > 0).sum() else 0)),
                   axis=1).astype(float)


def _all_agree_flag(df) -> pd.Series:
    S = _signed_matrix(df)
    # All non-zero and identical → flag 1.
    all_pos = (S > 0).all(axis=1)
    all_neg = (S < 0).all(axis=1)
    return (all_pos | all_neg).astype(float)


_reg(f"{MODULE}.regime.directional_consensus_score_20",
     "Directional Consensus Score (20)",
     "Regime", "consensus_score",
     "Fraction of {lr_slope_20, ema_slope_20, aroon_osc_14} whose sign matches the modal sign at bar t.",
     "mean_i 1[sign(T_i) == mode(sign)] ∈ [1/3, 1]",
     "1 all three agree; 1/3 fully split (no majority).",
     _consensus_score,
     inputs=[f"L1:{SRC[k]}" for k in SIGNED_SOURCES_20])

_reg(f"{MODULE}.regime.directional_consensus_sign_20",
     "Directional Consensus Sign (20)",
     "Regime", "consensus_sign",
     "The modal sign of {lr_slope_20, ema_slope_20, aroon_osc_14} at bar t.",
     "mode(sign_i) ∈ {-1, 0, +1}",
     "+1 majority up-trend; -1 majority down-trend; 0 no majority.",
     _consensus_sign,
     inputs=[f"L1:{SRC[k]}" for k in SIGNED_SOURCES_20])

_reg(f"{MODULE}.regime.all_sources_agree_flag_20",
     "All Sources Agree Flag (20)",
     "Regime", "consensus_flag",
     "1 if every signed source has the same non-zero sign at bar t, else 0.",
     "1[all sign_i > 0 or all sign_i < 0]",
     "1 unanimous non-zero direction; 0 any disagreement or flat.",
     _all_agree_flag,
     inputs=[f"L1:{SRC[k]}" for k in SIGNED_SOURCES_20])


# ─── Section 4.4 · Statistics (rolling cross-methodology stats) ───────────

def _adx_r2_agreement_60(df) -> pd.Series:
    return l1_series(df, SRC["adx_14"]).rolling(60, min_periods=30).corr(
        l1_series(df, SRC["r2_20"]))


def _consensus_rolling_mean_60(df) -> pd.Series:
    return _consensus_score(df).rolling(60, min_periods=30).mean()


def _consensus_rolling_std_60(df) -> pd.Series:
    return _consensus_score(df).rolling(60, min_periods=30).std()


_reg(f"{MODULE}.statistics.adx_r2_agreement_60",
     "ADX↔R² Strength-Methodology Rolling Correlation (60)",
     "Statistics", "cross_methodology_correlation",
     "60-bar rolling Pearson correlation of ADX(14) and lr_r2_20.",
     "corr_{k=60}(ADX_14, lr_r2_20) ∈ [-1, +1]",
     "High positive both strength methodologies co-move; near 0 they disagree on strength dynamics.",
     _adx_r2_agreement_60,
     inputs=[f"L1:{SRC['adx_14']}", f"L1:{SRC['r2_20']}"],
     complexity="O(n·60)")

_reg(f"{MODULE}.statistics.consensus_score_rolling_mean_60",
     "Consensus Score Rolling Mean (60)",
     "Statistics", "consensus_rolling_stat",
     "60-bar rolling mean of the directional_consensus_score_20 series.",
     "mean_{k=60}(directional_consensus_score_20)",
     "High trend has been clear/agreed over the recent 60 bars.",
     _consensus_rolling_mean_60,
     inputs=[f"L1:{SRC[k]}" for k in SIGNED_SOURCES_20],
     complexity="O(n·60)")

_reg(f"{MODULE}.statistics.consensus_score_rolling_std_60",
     "Consensus Score Rolling Std (60)",
     "Statistics", "consensus_rolling_stat",
     "60-bar rolling standard deviation of directional_consensus_score_20.",
     "std_{k=60}(directional_consensus_score_20)",
     "Low consensus is stable; high consensus is oscillating.",
     _consensus_rolling_std_60,
     inputs=[f"L1:{SRC[k]}" for k in SIGNED_SOURCES_20],
     complexity="O(n·60)")


# ─── Section 4.5 · Position (rolling percentile ranks) ────────────────────

def _rank_pct(s: pd.Series, w: int) -> pd.Series:
    return s.rolling(w, min_periods=max(2, w // 2)).rank(pct=True)


def _consensus_score_rank_60(df) -> pd.Series:
    return _rank_pct(_consensus_score(df), 60)


def _cascade_score_rank_60(df) -> pd.Series:
    return _rank_pct(_cascade4(df), 60)


def _slope_ratio_abs_rank_60(df) -> pd.Series:
    return _rank_pct(_slope_ratio_20_50(df).abs(), 60)


_reg(f"{MODULE}.position.consensus_score_rank_60",
     "Consensus Score Percentile Rank (60)",
     "Position", "rank_of_relationship",
     "Percentile rank of directional_consensus_score_20 over the trailing 60 bars.",
     "rank_pct(directional_consensus_score_20, 60)",
     "1 most-clear consensus in the recent history; 0 least clear.",
     _consensus_score_rank_60,
     inputs=[f"L1:{SRC[k]}" for k in SIGNED_SOURCES_20],
     complexity="O(n·60)")

_reg(f"{MODULE}.position.ema_cascade_score_rank_60",
     "EMA Cascade Score Percentile Rank (60)",
     "Position", "rank_of_relationship",
     "Percentile rank of ema_cascade_score_10_20_50_100 over the trailing 60 bars.",
     "rank_pct(ema_cascade_score_10_20_50_100, 60)",
     "1 cleanest cascade in the recent history; 0 most broken.",
     _cascade_score_rank_60,
     inputs=[f"L1:{SRC[k]}" for k in ("ema_10", "ema_20", "ema_50", "ema_100")],
     complexity="O(n·60)")

_reg(f"{MODULE}.position.slope_ratio_abs_rank_60",
     "|Slope Ratio| Percentile Rank (60)",
     "Position", "rank_of_relationship",
     "Percentile rank of |slope_ratio_20_50| over the trailing 60 bars.",
     "rank_pct(|clip(slope_20/slope_50, ±10)|, 60)",
     "1 most-extreme short/long divergence; 0 most-aligned.",
     _slope_ratio_abs_rank_60,
     inputs=[f"L1:{SRC['slope_20']}", f"L1:{SRC['slope_50']}"],
     complexity="O(n·60)")

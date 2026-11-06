"""Market Analysis — computes higher-level views from Atlas features.

These are HELPERS used by Atlas Terminal (Layer-5 consumer). They live
here for convenience but do not violate Book 1: every value derives
from registered Atlas features. This module invents no mathematics.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any
from atlas_core.compute import compute_features


def _last(x, default=None):
    try:
        v = float(x)
        return v if np.isfinite(v) else default
    except Exception:
        return default


def market_snapshot(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute a snapshot of derived market state from Atlas features."""
    ids = [
        "price.motion.log_return_1", "price.motion.log_return_5",
        "price.statistics.std_20", "price.statistics.zscore_20",
        "price.geometry.straightness_20", "price.geometry.complexity_20",
        "price.position.pct_rank_50", "price.position.minmax_50",
        "price.relative.dist_sma_20", "price.relative.dist_sma_200",
        "price.expansion.range_ratio_20", "price.clustering.vol_ratio_10",
        "price.regime.above_sma_50", "price.regime.above_sma_200",
        "price.entropy.shannon_30",
    ]
    feats = compute_features(df, ids)
    if len(feats) == 0:
        return {}
    last = feats.iloc[-1]

    trend_dir = _last(last.get("price.regime.above_sma_200"), 0) or 0
    trend_strength = abs(_last(last.get("price.relative.dist_sma_200"), 0) or 0)
    volatility = _last(last.get("price.statistics.std_20"), 0) or 0
    vol_cluster = _last(last.get("price.clustering.vol_ratio_10"), 1) or 1
    expansion = _last(last.get("price.expansion.range_ratio_20"), 1) or 1
    straightness = _last(last.get("price.geometry.straightness_20"), 0) or 0
    complexity = _last(last.get("price.geometry.complexity_20"), 0) or 0
    pct_val = _last(last.get("price.position.pct_rank_50"), 0.5)
    pct_rank = 0.5 if pct_val is None else pct_val
    entropy = _last(last.get("price.entropy.shannon_30"), 0) or 0

    # Composite Market Health (0..100) — deterministic template.
    trend_score = min(100, trend_strength * 500)                # 0..100
    stability_score = max(0, 100 - complexity * 8)              # fewer flips = stabler
    coherence_score = straightness * 100                        # 0..100
    vol_regime_score = 100 * max(0, 1 - min(vol_cluster / 2, 1))
    health = float(np.clip(0.30 * trend_score + 0.25 * stability_score +
                           0.25 * coherence_score + 0.20 * vol_regime_score,
                           0, 100))

    regime = "Uptrend" if trend_dir > 0 else "Downtrend" if trend_dir < 0 else "Neutral"
    vol_state = ("Expanding" if expansion > 1.1 else
                 "Contracting" if expansion < 0.9 else "Stable")

    return {
        "regime": regime,
        "trend_direction": int(trend_dir),
        "trend_strength": round(trend_strength, 4),
        "volatility": round(volatility, 6),
        "volatility_state": vol_state,
        "expansion_ratio": round(expansion, 3),
        "vol_cluster_ratio": round(vol_cluster, 3),
        "straightness": round(straightness, 3),
        "complexity": round(complexity, 2),
        "percentile_position": round(pct_rank, 3),
        "entropy": round(entropy, 3),
        "market_health": round(health, 1),
        "components": {
            "trend_score": round(trend_score, 1),
            "stability_score": round(stability_score, 1),
            "coherence_score": round(coherence_score, 1),
            "vol_regime_score": round(vol_regime_score, 1),
        }
    }


def explain_snapshot(snap: Dict[str, Any]) -> Dict[str, str]:
    """Deterministic, Registry-driven natural language explanation."""
    if not snap:
        return {"beginner": "Not enough data yet.", "pro": "Insufficient data."}

    reg = snap["regime"]
    ts = snap["trend_strength"]
    vs = snap["volatility_state"]
    er = snap["expansion_ratio"]
    st = snap["straightness"]
    cx = snap["complexity"]
    pr = snap["percentile_position"]
    h = snap["market_health"]

    beginner = (
        f"The market is currently in an **{reg.lower()}**. "
        f"Price is at the **{int(pr*100)}th percentile** of the last 50 bars — "
        f"{'near the top' if pr > 0.8 else 'near the bottom' if pr < 0.2 else 'in the middle'}. "
        f"Volatility looks **{vs.lower()}** (range is {er:.2f}× its normal size). "
        f"The move is **{'clean and directional' if st > 0.5 else 'choppy' if st < 0.25 else 'moderately structured'}**. "
        f"Overall market health: **{h:.0f}/100**."
    )
    pro = (
        f"Regime: {reg} (dir={snap['trend_direction']}, |Δ%|_200={ts:.3f}). "
        f"σ_20={snap['volatility']:.4f}, expansion={er:.2f}, "
        f"vol-cluster={snap['vol_cluster_ratio']:.2f}. "
        f"Trajectory: straightness={st:.2f}, complexity={cx:.1f} turning points. "
        f"Position: pct_rank_50={pr:.2f}, entropy_30={snap['entropy']:.2f}. "
        f"Composite health {h:.1f}/100 "
        f"(trend {snap['components']['trend_score']:.0f}, "
        f"stability {snap['components']['stability_score']:.0f}, "
        f"coherence {snap['components']['coherence_score']:.0f}, "
        f"vol {snap['components']['vol_regime_score']:.0f})."
    )
    return {"beginner": beginner, "pro": pro}

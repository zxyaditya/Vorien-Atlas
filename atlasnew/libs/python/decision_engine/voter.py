"""Voter — aggregate signals into a single recommendation."""
from __future__ import annotations
from typing import Dict, Any, List


# How much each signal contributes to the final decision.
# v0.6: adds Microstructure (L1) and MarketStructure (L2).
# v0.7.1: adds TrendAlignment (L2 · trend_relationships). Weight budget of
#         0.05 redistributed from Trend (−0.02), Momentum (−0.01),
#         TrendMomentum (−0.02) — TrendMomentum is temporal; TrendAlignment
#         is cross-source. See docs/L2_SPECS/TREND_RELATIONSHIPS_DE_REVIEW.md §2.
# v0.7.2: adds FractalCoherence (L2 · fractal_relationships, direction-neutral).
#         Weight budget of 0.03 redistributed exclusively from the other
#         direction-neutral confidence-modulators: Structure (−0.02),
#         Entropy (−0.01). Directional weights untouched.
#         See docs/L2_SPECS/FRACTAL_RELATIONSHIPS_DE_REVIEW.md §3.
# v0.7.3: adds RelativeStrength (L2 · relative_strength, direction-neutral).
#         Weight budget of 0.03 drawn from Trend (−0.02), Momentum (−0.01) —
#         RS is a *comparative* strength quantity partially overlapping with
#         what Trend/Momentum measure in absolute terms.
#         See docs/L2_SPECS/RELATIVE_STRENGTH_DE_REVIEW.md §3.
# v0.8.0: adds 5 Layer-3 state signals (Session 8 milestone). Weight
#         budget of 0.15 drawn from adjacent signals whose information
#         L3 states partially subsume:
#           Trend         −0.02 (TrendState re-expresses trend as state)
#           Momentum      −0.02 (ParticipationState covers accum/dist)
#           Regime        −0.03 (RegimeState is the L3 four-way regime)
#           MarketStructure −0.03 (LiquidityState complements BOS/CHoCH)
#           Microstructure −0.03 (LiquidityState uses wick+exec-imb)
#           Volatility    −0.01 (RegimeState absorbs volatile-state axis)
#           Entropy       −0.01 (RegimeState absorbs regime-uncertainty)
#         Sum invariant preserved: weights still total 1.00.
#         See docs/L3_MARKET_UNDERSTANDING.md §8.
# v0.9.0: adds 2 Layer-4-derived signals. Weight budget of 0.05 drawn:
#           Trend         −0.01 → 0.09
#           Momentum      −0.01 → 0.07
#           Regime        −0.01 → 0.08
#           Structure     −0.01 → 0.02
#           Volume        −0.01 → 0.09
#         Sum invariant preserved at 1.00. See docs/L4_REPRESENTATION.md §8.
SIGNAL_WEIGHTS = {
    "Trend": 0.09,                # v0.9.0: 0.10 → 0.09
    "Momentum": 0.07,             # v0.9.0: 0.08 → 0.07
    "TrendMomentum": 0.03,
    "TrendAlignment": 0.05,
    "FractalCoherence": 0.03,
    "RelativeStrength": 0.03,
    "Regime": 0.08,               # v0.9.0: 0.09 → 0.08
    "Structure": 0.02,            # v0.9.0: 0.03 → 0.02
    "MeanReversion": 0.06,
    "Volume": 0.09,               # v0.9.0: 0.10 → 0.09
    "Volatility": 0.02,
    "Liquidity": 0.03,
    "Microstructure": 0.07,
    "MarketStructure": 0.12,
    "Entropy": 0.01,
    # v0.8.0 · L3 states
    "TrendState": 0.04,
    "RangeState": 0.03,
    "ParticipationState": 0.03,
    "LiquidityState": 0.03,
    "RegimeState": 0.02,
    # v0.9.0 · L4-derived signals
    "CrossFlow": 0.03,            # NEW v0.9.0 (L4 · cross_module_interactions)
    "MetaConfidence": 0.02,       # NEW v0.9.0 (L4 · meta_features)
}
# Invariant: sum(SIGNAL_WEIGHTS.values()) == 1.00 (asserted by pytest).


def vote(signals: List[Dict[str, Any]],
         weights: Dict[str, float] = None,
         ml_agreement: Dict[str, Any] = None) -> Dict[str, Any]:
    """Aggregate signals. Optional custom weights override manual defaults.

    v0.11.0: `ml_agreement` (DEC-019) is an OPTIONAL dict describing what
    the Learning System believes about the same window:
        {"probability_up": 0.72, "agreement": 0.85, "n_models": 3}
    When present AND the LS agrees with the voter's tentative direction,
    a bounded confidence bonus of at most 0.15 is added. The bonus is
    reported explicitly in the output; it never overrides the decision;
    it never appears when `ml_agreement=None`. See DEC-019.
    """
    w_map = weights if weights else SIGNAL_WEIGHTS
    directional_score = 0.0
    strength_score = 0.0
    weight_sum = 0.0
    contributions: Dict[str, float] = {}

    for sig in signals:
        w = w_map.get(sig["name"], 0.0)
        weight_sum += w
        contrib = sig["direction"] * sig["strength"] * w
        directional_score += contrib
        strength_score += sig["strength"] * w
        contributions[sig["name"]] = abs(contrib)

    if weight_sum == 0:
        return {"decision": "WAIT", "score": 0.0, "confidence": 0.0,
                "family_contribution": {}, "reasoning": "No signals available."}

    # Confidence: agreement among directional signals + adjustments
    directional = [s for s in signals
                   if s["direction"] != 0 and w_map.get(s["name"], 0) > 0]
    if directional:
        signs = [s["direction"] for s in directional]
        agreement = abs(sum(signs)) / len(signs)  # 0..1
    else:
        agreement = 0.0
    avg_conf = sum(s.get("confidence", 0.0) for s in signals) / max(1, len(signals))

    # Penalize confidence when entropy is high or volatility is elevated
    ent_sig = next((s for s in signals if s["name"] == "Entropy"), None)
    vol_sig = next((s for s in signals if s["name"] == "Volatility"), None)
    ent_boost = ent_sig.get("strength", 0.0) if ent_sig else 0.0   # Removed artificial 0.5 baseline
    vol_penalty = 0.0
    if vol_sig and vol_sig.get("state") == "elevated":
        vol_penalty = 0.15

    confidence = max(0.0, min(1.0,
        0.55 * agreement + 0.25 * avg_conf + 0.20 * ent_boost - vol_penalty))

    score = directional_score / weight_sum   # ∈ [-1, +1]

    # ── DEC-019 · additive, bounded, explainable LS confidence bonus ──
    ml_bonus = 0.0
    ml_bonus_details: Dict[str, Any] = {"applied": False, "reason": "not_provided"}
    if ml_agreement is not None:
        p_up = ml_agreement.get("probability_up")
        agreement_ml = ml_agreement.get("agreement", 0.0) or 0.0
        n_models = int(ml_agreement.get("n_models", 0) or 0)
        # Only apply when LS speaks with enough samples + reasonable agreement.
        if (p_up is not None and n_models >= 1 and agreement_ml >= 0.5
                and isinstance(p_up, (int, float))):
            ls_dir = 1 if p_up > 0.5 else (-1 if p_up < 0.5 else 0)
            voter_dir = 1 if score > 0 else (-1 if score < 0 else 0)
            match = ls_dir != 0 and ls_dir == voter_dir
            if match:
                # Bounded above by 0.15; scaled by (agreement − 0.5) so
                # weak agreement contributes little. Direction match
                # required. Explainable single-line formula.
                ml_bonus = float(min(0.15, 0.30 * (agreement_ml - 0.5)))
                ml_bonus = max(0.0, ml_bonus)
            ml_bonus_details = {
                "applied": bool(match),
                "ls_direction": int(ls_dir),
                "voter_direction": int(voter_dir),
                "probability_up": float(p_up),
                "agreement": float(agreement_ml),
                "n_models": n_models,
                "bonus": round(ml_bonus, 6),
                "reason": ("direction_match" if match
                            else "direction_mismatch"),
                "cap": 0.15,
            }
    confidence = max(0.0, min(1.0, confidence + ml_bonus))

    # Decision thresholds — deliberately conservative
    if score > 0.20 and confidence > 0.45:
        decision = "LONG"
    elif score < -0.20 and confidence > 0.45:
        decision = "SHORT"
    else:
        decision = "WAIT"

    total_c = sum(contributions.values()) or 1.0
    family_pct = {k: round(100 * v / total_c, 1) for k, v in contributions.items()}

    reasoning = _bullets(signals, decision)

    return {
        "decision": decision,
        "score": round(score, 4),
        "confidence": round(confidence, 4),
        "agreement": round(agreement, 4),
        "family_contribution": family_pct,
        "reasoning": reasoning,
        "ml_confidence_bonus": ml_bonus_details,
    }


def _bullets(signals, decision):
    bullets = []
    for s in signals:
        if s["direction"] == 0 and s["name"] not in ("Volatility", "Entropy"):
            continue
        # pick the top-weight piece of evidence
        if not s["evidence"]:
            continue
        top = max(s["evidence"], key=lambda e: e.get("weight", 0))
        arrow = "↑" if s["direction"] > 0 else "↓" if s["direction"] < 0 else "•"
        bullets.append(f"{arrow} {s['name']}: {top.get('argument', '')}")
    return bullets

"""Recommender — the single top-level entrypoint that composes everything.

v0.11.0 (DEC-019): accepts an optional `ml_advisor` dict populated by the
FastAPI composition layer from the Learning System's `DEBridge`. The
advisor NEVER changes the decision. It may:
  * enrich the voter's confidence with a bounded bonus (via `vote()`),
  * populate an `ml_dissent` block when the LS strongly disagrees with
    the voter direction (warning only, decision unchanged),
  * pass through as `ml_advisor` in the response so the frontend and
    downstream explainers can display the LS opinion transparently.

If `ml_advisor is None` the entire pipeline is bit-identical to v0.10.0.
The Decision Engine never imports from `learning_system/`
(DEC-017 preserved). Data flows in as a plain dict.
"""
from __future__ import annotations
import pandas as pd
from typing import Dict, Any, Optional

from decision_engine.signals import compute_all_signals
from decision_engine.voter import vote
from decision_engine.risk import assess_risk, position_sizing
from decision_engine.analogues import find_analogues
from decision_engine.explainer import explain_recommendation


def _detect_dissent(voter_score: float, voter_confidence: float,
                     ml_prob_up: Optional[float],
                     ml_agreement: Optional[float]) -> Dict[str, Any]:
    """DEC-019 dissent rule: fire ONLY when
      * voter confidence ≥ 0.45 (voter is not itself uncertain),
      * ml_prob_up crosses to the opposite side of 0.5 by at least 0.10,
      * ml_agreement ≥ 0.60 (LS itself agrees enough to matter).
    """
    if (ml_prob_up is None or ml_agreement is None
            or voter_confidence < 0.45):
        return {"fired": False, "reason": "insufficient_signals"}
    voter_dir = 1 if voter_score > 0 else (-1 if voter_score < 0 else 0)
    ls_dir = 1 if ml_prob_up > 0.60 else (-1 if ml_prob_up < 0.40 else 0)
    if voter_dir == 0 or ls_dir == 0:
        return {"fired": False, "reason": "no_directional_conflict"}
    if voter_dir == ls_dir:
        return {"fired": False, "reason": "no_conflict"}
    if float(ml_agreement) < 0.60:
        return {"fired": False, "reason": "low_ls_agreement"}
    arrow = "↑" if ls_dir > 0 else "↓"
    warning = (
        f"Learning System dissents: probability_up={ml_prob_up:.2f} "
        f"(direction {arrow}) with agreement={ml_agreement:.2f} across "
        f"stored models. Voter direction is opposite. Decision unchanged."
    )
    return {
        "fired": True,
        "voter_direction": int(voter_dir),
        "ls_direction": int(ls_dir),
        "probability_up": float(ml_prob_up),
        "agreement": float(ml_agreement),
        "warning": warning,
    }


def recommend(df: pd.DataFrame, model_agreement: Dict[str, Any] = None,
              horizon: int = 5, use_learned_weights: bool = False,
              use_regime_conditional_weights: bool = False,
              learned_weights_window: int = 200,
              context: Dict[str, pd.DataFrame] = None,
              ml_advisor: Optional[Dict[str, Any]] = None,
              analogue_schema: str = "v1") -> Dict[str, Any]:
    """Compose signals → vote → risk → analogues → explanation.

    context: optional DEC-007 multi-symbol payload (e.g. {"peer": peer_df}).
    Forwarded to compute_all_signals and learn_weights so L2 cross-symbol
    features (relative_strength.*) populate when a peer is supplied.

    use_regime_conditional_weights: v0.13.0 · Session 13. When True,
    consumes `/api/decision/regime_conditional_weights` under the hood:
    detects the CURRENT L3 regime code (last valid value of
    `market_regime.regime.active_state_code`) and votes with the per-regime
    weight vector for that code. Falls back to the global learned weights
    if the current regime has too few samples. Fully explainable — the
    active regime + which vector was used are reported in the response.

    ml_advisor: optional DEC-019 payload with keys:
      * probability_up   (float 0..1)
      * agreement        (float 0..1)
      * n_models         (int)
      * best_model_id    (str, optional)
      * kind             (str, optional)
    When present, drives the voter's confidence bonus + the dissent
    detector. Never overrides the decision.

    analogue_schema: "v1" (default; L1-heavy 19-dim) or "v2" (L4
    embeddings + curated L2/L3 numerics; DEC-019).
    """
    signals_bundle = compute_all_signals(df, context=context)
    signals = signals_bundle["signals"]

    weights_used = None
    weight_source = "manual"
    regime_conditional_meta: Optional[Dict[str, Any]] = None

    if use_regime_conditional_weights:
        # DEC-020 · Session 13 wiring. One interpretable LR per L3 regime
        # code; then the CURRENT regime's vector is used for this call.
        try:
            from decision_engine.weight_learner import learn_regime_conditional_weights
            from atlas_core.compute import compute_features
            reg_result = learn_regime_conditional_weights(
                df, horizon=horizon, window=learned_weights_window,
                context=context,
            )
            # Detect current regime code from the last valid value.
            regime_fid = reg_result.get(
                "regime_feature_id",
                "market_regime.regime.active_state_code")
            reg = compute_features(df, [regime_fid],
                                   context=context)[regime_fid]
            active_code = None
            for v in reversed(list(reg.values)):
                if v == v and v is not None:
                    try:
                        active_code = int(v)
                    except Exception:
                        active_code = None
                    if active_code is not None:
                        break
            regimes = (reg_result.get("regimes") or {})
            entry = regimes.get(str(active_code)) if active_code is not None else None
            fallback = "no_regime_detected"
            chosen_weights = None
            if entry and entry.get("learned_weights"):
                chosen_weights = entry["learned_weights"]
                fallback = entry.get("fallback")   # None or "global"
            elif reg_result.get("global_fallback", {}).get("learned_weights"):
                chosen_weights = reg_result["global_fallback"]["learned_weights"]
                fallback = "global"
            if chosen_weights:
                weights_used = chosen_weights
                weight_source = "regime_conditional"
                regime_conditional_meta = {
                    "active_regime_code": active_code,
                    "fallback": fallback,
                    "regime_feature_id": regime_fid,
                    "n_regimes_available": len(regimes),
                    "regime_sample_count": (entry or {}).get("n_samples"),
                }
        except Exception as e:
            regime_conditional_meta = {
                "error": f"regime-conditional weights failed: {e}",
                "fallback": "manual",
            }
    if weights_used is None and use_learned_weights:
        try:
            from decision_engine.weight_learner import learn_weights
            lw = learn_weights(df, horizon=horizon,
                               window=learned_weights_window, context=context)
            if "learned_weights" in lw:
                weights_used = lw["learned_weights"]
                weight_source = "learned"
        except Exception:
            weights_used = None

    v = vote(signals, weights=weights_used, ml_agreement=ml_advisor)
    risk = assess_risk(df)
    sizing = position_sizing(v["score"], v["confidence"], risk)
    analogues = find_analogues(df, k=10, horizon=horizon,
                                schema=analogue_schema)
    expl = explain_recommendation(signals, v, risk, analogues)

    # DEC-019 dissent detection.
    ml_prob_up = ml_advisor.get("probability_up") if ml_advisor else None
    ml_agree = ml_advisor.get("agreement") if ml_advisor else None
    ml_dissent = _detect_dissent(v["score"], v["confidence"],
                                    ml_prob_up, ml_agree)

    return {
        "decision": v["decision"],
        "score": v["score"],
        "confidence": v["confidence"],
        "agreement": v["agreement"],
        "weight_source": weight_source,
        "weights_used": weights_used,
        "regime_conditional": regime_conditional_meta,
        "family_contribution": v["family_contribution"],
        "signals": signals,
        "risk": risk,
        "sizing": sizing,
        "analogues": analogues,
        "model_agreement": model_agreement or {"note": "not requested"},
        "ml_advisor": ml_advisor or {"available": False,
                                        "note": "not requested"},
        "ml_confidence_bonus": v.get("ml_confidence_bonus",
                                       {"applied": False}),
        "ml_dissent": ml_dissent,
        "explanation": expl,
        "feature_snapshot": signals_bundle["feature_snapshot"],
        "disclaimer": ("Research prototype — not investment advice. "
                       "All numbers derive from mathematical features; "
                       "none guarantees future performance."),
    }

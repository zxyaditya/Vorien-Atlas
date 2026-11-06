"""DEBridge — optional read-only helpers for the Decision Engine.

The Learning System never mutates DE state. The DE can (in a follow-up
milestone) *choose* to enrich its own outputs using these helpers, or
ignore them entirely.

Current helpers:
  * `latest_calibrated_prob_up(...)` — fetch the newest stored prediction
    for a given symbol/model kind.
  * `model_ensemble_agreement_score(...)` — measure cross-model
    directional agreement across the top-K stored models on a symbol.

Both are async because they read Mongo through the ModelRegistry.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

import numpy as np


class DEBridge:
    def __init__(self, model_registry, inference_pipeline):
        self._registry = model_registry
        self._inference = inference_pipeline

    async def latest_calibrated_prob_up(
        self, provider: str, symbol: str,
        interval: str = "1d", period: str = "3y",
        kind: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Score the newest stored model of `kind` on the current window.

        Returns {model_id, kind, probability_up, confidence, direction}
        or None if no model exists.
        """
        docs = await self._registry.list(kind=kind, limit=1)
        if not docs:
            return None
        model_id = docs[0]["model_id"]
        from learning_system.contracts import InferenceRequest
        pred = await self._inference.predict(InferenceRequest(
            model_id=model_id, provider=provider, symbol=symbol,
            interval=interval, period=period,
        ))
        if pred is None:
            return None
        return {
            "model_id": pred.model_id, "kind": pred.kind,
            "probability_up": pred.probability_up,
            "confidence": pred.confidence,
            "direction": pred.direction,
        }

    async def model_ensemble_agreement_score(
        self, provider: str, symbol: str,
        interval: str = "1d", period: str = "3y",
        top_k: int = 3, metric: str = "accuracy_mean",
    ) -> Optional[Dict[str, Any]]:
        """Score the top-K stored models on the current window and
        report how tightly they agree.

        Returns:
            {n_models, mean_prob_up, agreement, votes}
            where agreement ∈ [0, 1] is 1 minus the std of prob-up
            across models.
        """
        candidates = await self._registry.best(metric=metric, top=top_k)
        if not candidates:
            return None
        from learning_system.contracts import InferenceRequest
        prob_ups: List[float] = []
        votes = {"UP": 0, "DOWN": 0, "ABSTAIN": 0}
        for c in candidates:
            pred = await self._inference.predict(InferenceRequest(
                model_id=c["model_id"], provider=provider, symbol=symbol,
                interval=interval, period=period,
            ))
            if pred is None or pred.probability_up is None:
                continue
            prob_ups.append(pred.probability_up)
            votes[pred.direction] = votes.get(pred.direction, 0) + 1
        if not prob_ups:
            return None
        std = float(np.std(prob_ups))
        agreement = float(max(0.0, 1.0 - 4.0 * std))    # std ≥ 0.25 → 0.
        return {
            "n_models": int(len(prob_ups)),
            "mean_prob_up": round(float(np.mean(prob_ups)), 6),
            "agreement": round(agreement, 6),
            "votes": votes,
        }

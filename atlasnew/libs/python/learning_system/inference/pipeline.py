"""InferencePipeline — load a persisted model, run it on current data.

Expectations:
  - The model was saved via ModelRegistry (feature IDs are recorded in
    Mongo metadata).
  - Fresh OHLCV is fetched via atlas_core.data.fetch_smart.
  - Feature matrix is computed with the same feature IDs as at training.
  - Prediction is on the *last* row that has non-NaN features.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from learning_system.contracts import InferenceRequest, Prediction
from learning_system.dataset.feature_matrix import build_feature_matrix


class InferencePipeline:
    def __init__(self, model_registry, data_fetcher):
        """data_fetcher(provider, symbol, interval, period) → pd.DataFrame."""
        self._registry = model_registry
        self._fetch = data_fetcher

    async def predict(self, req: InferenceRequest) -> Optional[Prediction]:
        meta = await self._registry.get(req.model_id)
        if meta is None:
            return None
        model = await self._registry.load_model(req.model_id)
        if model is None:
            return None

        df = self._fetch(req.provider, req.symbol, req.interval, req.period)
        if df is None or len(df) < 100:
            return None

        context: Optional[Dict[str, pd.DataFrame]] = None
        if req.peer_provider and req.peer_symbol:
            peer_df = self._fetch(req.peer_provider, req.peer_symbol,
                                   req.interval, req.period)
            if peer_df is not None:
                peer_df = peer_df.reindex(df.index).ffill()
                context = {"peer": peer_df}

        feature_ids = list(meta.get("feature_ids") or [])
        X = build_feature_matrix(df, feature_ids, context=context,
                                   dropna_policy="none")
        if len(X) < 1:
            return None
        # Align to the model's training feature order.
        train_cols = getattr(model, "_feature_names", []) or list(X.columns)
        cols = [c for c in train_cols if c in X.columns]
        if not cols:
            return None
        proba = model.predict_proba(X[cols])
        p_up = float(proba[-1, 1])
        direction = "UP" if p_up > 0.55 else ("DOWN" if p_up < 0.45
                                                 else "ABSTAIN")
        confidence = float(min(1.0, abs(p_up - 0.5) * 2))
        top = sorted(model.feature_importances().items(),
                     key=lambda kv: -kv[1])[:10]
        top_features = [{"id": k, "importance": round(float(v), 6)}
                         for k, v in top]
        return Prediction(
            model_id=req.model_id,
            experiment_id=str(meta.get("experiment_id", "")),
            kind=str(meta.get("kind", "")),
            direction=direction,
            probability_up=round(p_up, 6),
            confidence=round(confidence, 6),
            horizon=int(meta.get("metrics", {}).get("horizon", 5)) or 5,
            top_features=top_features,
            provider=req.provider,
            symbol=req.symbol,
            as_of=datetime.now(timezone.utc).isoformat(),
        )

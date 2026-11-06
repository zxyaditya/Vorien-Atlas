"""ModelRegistry — filesystem for artifacts + Mongo for metadata.

Every persisted model has a unique `model_id` (UUID4 hex) and is
stored under `ARTIFACT_ROOT/<experiment_id>/<model_id>.pkl`. Mongo
collection `learning_models` carries JSON-safe metadata for querying.
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from learning_system.contracts import to_json_safe
from learning_system.models import MODEL_REGISTRY, BaseModel
from learning_system.models.base import BaseModel as _Base

ARTIFACT_ROOT = Path(os.environ.get(
    "LEARNING_SYSTEM_ARTIFACT_ROOT",
    "/app/learning_system/artifacts"
))
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

COLLECTION = "learning_models"


class ModelRegistry:
    def __init__(self, mongo_db):
        self._db = mongo_db
        self._col = mongo_db[COLLECTION] if mongo_db is not None else None

    # ---- write ----------------------------------------------------------
    async def save(self, model: BaseModel, experiment_id: str, fold: int,
                    metrics: Dict[str, Any],
                    feature_ids: List[str],
                    provider: str,
                    symbol: str,
                    interval: str,
                    tags: Optional[List[str]] = None,
                    ) -> Dict[str, Any]:
        model_id = uuid.uuid4().hex
        exp_dir = ARTIFACT_ROOT / experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = exp_dir / f"{model_id}.pkl"
        model.to_disk(artifact_path)
        
        try:
            size_bytes = os.path.getsize(artifact_path)
        except OSError:
            size_bytes = 0
            
        try:
            imp = model.feature_importances()
            top = sorted(imp.items(), key=lambda kv: -kv[1])[:25]
            feature_importance = [{"id": k, "importance": round(float(v), 6)} for k, v in top]
        except Exception:
            feature_importance = []
            
        doc = {
            "model_id": model_id,
            "experiment_id": experiment_id,
            "fold": int(fold),
            "kind": model.kind,
            "hyperparams": to_json_safe(model.hyperparams),
            "seed": int(model.seed),
            "feature_ids": list(feature_ids),
            "n_features": len(feature_ids),
            "artifact_path": str(artifact_path),
            "file_size_bytes": size_bytes,
            "feature_importance": feature_importance,
            "metrics": to_json_safe(metrics),
            "provider": provider,
            "symbol": symbol,
            "tags": list(tags or []),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if self._col is not None:
            await self._col.insert_one(dict(doc))
            doc.pop("_id", None)
        return doc

    # ---- read -----------------------------------------------------------
    async def get(self, model_id: str) -> Optional[Dict[str, Any]]:
        if self._col is None:
            return None
        doc = await self._col.find_one({"model_id": model_id})
        if doc is not None:
            doc.pop("_id", None)
        return doc

    async def list(self, kind: Optional[str] = None,
                    experiment_id: Optional[str] = None,
                    provider: Optional[str] = None,
                    symbol: Optional[str] = None,
                    limit: int = 50) -> List[Dict[str, Any]]:
        if self._col is None:
            return []
        q: Dict[str, Any] = {}
        if kind:
            q["kind"] = kind
        if experiment_id:
            q["experiment_id"] = experiment_id
        if provider:
            q["provider"] = provider
        if symbol:
            q["symbol"] = symbol
        cur = self._col.find(q).sort("created_at", -1).limit(limit)
        out = []
        async for d in cur:
            d.pop("_id", None)
            out.append(d)
        return out

    async def best(self, metric: str = "accuracy_mean", top: int = 5,
                    kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """Best models by a single metric key. Reads from experiment aggregates."""
        if self._col is None:
            return []
        q: Dict[str, Any] = {}
        if kind:
            q["kind"] = kind
        # NB: metric here is a *fold* metric — e.g. "accuracy", "log_loss".
        cur = self._col.find(q, {
            "model_id": 1, "kind": 1, "experiment_id": 1,
            "metrics": 1, "tags": 1, "created_at": 1,
        })
        docs = []
        async for d in cur:
            metrics = d.get("metrics", {})
            
            if metric == "composite":
                acc = float(metrics.get("accuracy_mean", 0.0))
                ic = float(metrics.get("ic_mean", 0.0))
                # Add them up, or use whatever weighting. Both are typically -1 to 1 or 0 to 1
                v = acc + ic
            else:
                v = metrics.get(metric)
                
            if isinstance(v, (int, float)):
                d["_score"] = float(v)
                d.pop("_id", None)
                docs.append(d)
        # Log-loss / brier are minimised; everything else maximised.
        reverse = metric not in ("log_loss", "brier")
        docs.sort(key=lambda d: d["_score"], reverse=reverse)
        return docs[:top]

    # ---- update ---------------------------------------------------------
    async def update(self, model_id: str, updates: Dict[str, Any]) -> bool:
        if self._col is None:
            return False
        res = await self._col.update_one({"model_id": model_id}, {"$set": updates})
        return res.modified_count > 0

    # ---- delete ---------------------------------------------------------
    async def delete(self, model_id: str) -> bool:
        if self._col is None:
            return False
        # Fetch it first to delete the artifact
        doc = await self.get(model_id)
        if doc and "artifact_path" in doc:
            try:
                os.remove(doc["artifact_path"])
            except OSError:
                pass
        res = await self._col.delete_one({"model_id": model_id})
        return res.deleted_count > 0

    # ---- load ----------------------------------------------------------
    async def load_model(self, model_id: str) -> Optional[_Base]:
        meta = await self.get(model_id)
        if meta is None:
            return None
        cls = MODEL_REGISTRY.get(meta["kind"])
        if cls is None:
            return None
        artifact_path = Path(meta["artifact_path"])
        if not artifact_path.exists():
            import logging
            logging.getLogger("atlas.registry").warning(
                "Model artifact missing from disk: %s (model_id=%s). "
                "The model may have been trained in a different container run. "
                "Re-train the model to regenerate the artifact.",
                artifact_path, model_id,
            )
            return None
        try:
            return cls.from_disk(artifact_path)
        except Exception as exc:
            import logging
            logging.getLogger("atlas.registry").error(
                "Failed to load model artifact %s: %s", artifact_path, exc
            )
            return None

    async def stats(self) -> Dict[str, Any]:
        if self._col is None:
            return {"n_models": 0, "by_kind": {}}
        n = await self._col.count_documents({})
        by_kind = {}
        cur = self._col.aggregate([
            {"$group": {"_id": "$kind", "n": {"$sum": 1}}},
        ])
        async for d in cur:
            by_kind[d["_id"]] = int(d["n"])
        return {"n_models": int(n), "by_kind": by_kind}

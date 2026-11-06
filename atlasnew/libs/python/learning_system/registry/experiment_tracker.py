"""ExperimentTracker — Mongo-backed record of every ExperimentResult."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from learning_system.contracts import ExperimentResult, to_json_safe

COLLECTION = "learning_experiments"


class ExperimentTracker:
    def __init__(self, mongo_db):
        self._db = mongo_db
        self._col = mongo_db[COLLECTION] if mongo_db is not None else None

    async def record(self, result: ExperimentResult) -> Dict[str, Any]:
        doc = to_json_safe(result)
        doc["recorded_at"] = datetime.now(timezone.utc).isoformat()
        if self._col is not None:
            await self._col.insert_one(dict(doc))
            doc.pop("_id", None)
        return doc

    async def get(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        if self._col is None:
            return None
        d = await self._col.find_one({"experiment_id": experiment_id})
        if d is not None:
            d.pop("_id", None)
        return d

    async def list(self, name: Optional[str] = None,
                    limit: int = 50) -> List[Dict[str, Any]]:
        if self._col is None:
            return []
        q = {}
        if name:
            q["spec.name"] = name
        cur = self._col.find(q).sort("created_at", -1).limit(limit)
        out = []
        async for d in cur:
            d.pop("_id", None)
            out.append(d)
        return out

    async def stats(self) -> Dict[str, Any]:
        if self._col is None:
            return {"n_experiments": 0}
        n = await self._col.count_documents({})
        return {"n_experiments": int(n)}

"""BacktestTracker — Mongo-backed record of every BacktestResult.

Same pattern as ExperimentTracker (v0.10.0). One Mongo document per
walk-forward backtest run. Backtest results are otherwise transient;
persistence lets the frontend and future analytics query the history
of every strategy configuration ever evaluated.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from learning_system.contracts import to_json_safe

COLLECTION = "learning_backtests"


class BacktestTracker:
    def __init__(self, mongo_db):
        self._db = mongo_db
        self._col = mongo_db[COLLECTION] if mongo_db is not None else None

    async def record(self, result) -> Dict[str, Any]:
        doc = to_json_safe(result)
        doc["recorded_at"] = datetime.now(timezone.utc).isoformat()
        # Guarantee a top-level `backtest_id` for indexing.
        if "backtest_id" not in doc:
            doc["backtest_id"] = doc.get("id") or ""
        if self._col is not None:
            await self._col.insert_one(dict(doc))
            doc.pop("_id", None)
        return doc

    async def get(self, backtest_id: str) -> Optional[Dict[str, Any]]:
        if self._col is None:
            return None
        d = await self._col.find_one({"backtest_id": backtest_id})
        if d is not None:
            d.pop("_id", None)
        return d

    async def list(self, model_id: Optional[str] = None,
                    symbol: Optional[str] = None,
                    limit: int = 50) -> List[Dict[str, Any]]:
        if self._col is None:
            return []
        q: Dict[str, Any] = {}
        if model_id:
            q["spec.model_id"] = model_id
        if symbol:
            q["spec.symbol"] = symbol
        cur = self._col.find(q, {"equity_curve": 0, "trades": 0})\
                        .sort("created_at", -1).limit(limit)
        out = []
        async for d in cur:
            d.pop("_id", None)
            out.append(d)
        return out

    async def stats(self) -> Dict[str, Any]:
        if self._col is None:
            return {"n_backtests": 0}
        n = await self._col.count_documents({})
        return {"n_backtests": int(n)}

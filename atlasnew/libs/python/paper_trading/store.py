"""Async Mongo store for Paper Trading. Uses motor.

Collections:
  paper_accounts    — single default account (v1.0 single-user)
  paper_positions   — open positions only
  paper_trades      — closed-trade audit records (immutable append)
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from paper_trading.contracts import PaperAccount


DEFAULT_ACCOUNT_KEY = "default"      # single-user marker on account docs


class PaperStore:
    def __init__(self, db):
        self.db = db
        self.accounts = db.paper_accounts
        self.positions = db.paper_positions
        self.trades = db.paper_trades

    async def ensure_indexes(self):
        import pymongo
        await self.positions.create_index(
            [("symbol", pymongo.ASCENDING)],
            unique=True,
            partialFilterExpression={"status": "open"}
        )

    # ── Accounts ────────────────────────────────────────────────────────
    async def get_or_create_default(self) -> Dict[str, Any]:
        doc = await self.accounts.find_one({"_key": DEFAULT_ACCOUNT_KEY}, {"_id": 0})
        if doc:
            return doc
        acc = PaperAccount()
        d = acc.to_dict()
        d["_key"] = DEFAULT_ACCOUNT_KEY
        await self.accounts.insert_one(dict(d))
        d.pop("_id", None)
        return d

    async def update_account(self, account: Dict[str, Any]) -> None:
        d = {k: v for k, v in account.items() if k != "_id"}
        d["_key"] = DEFAULT_ACCOUNT_KEY
        await self.accounts.replace_one({"_key": DEFAULT_ACCOUNT_KEY}, d, upsert=True)

    async def reset_account(self, starting_balance: Optional[float] = None,
                             fees_bps_per_side: Optional[float] = None,
                             slippage_bps: Optional[float] = None,
                             ) -> Dict[str, Any]:
        await self.positions.delete_many({})
        await self.trades.delete_many({})
        acc = PaperAccount()
        if starting_balance is not None:
            acc.starting_balance = float(starting_balance)
            acc.cash = float(starting_balance)
        if fees_bps_per_side is not None:
            acc.fees_bps_per_side = float(fees_bps_per_side)
        if slippage_bps is not None:
            acc.slippage_bps = float(slippage_bps)
        d = acc.to_dict()
        d["_key"] = DEFAULT_ACCOUNT_KEY
        await self.accounts.replace_one({"_key": DEFAULT_ACCOUNT_KEY}, d, upsert=True)
        d.pop("_id", None)
        return d

    async def update_settings(self,
                               fees_bps_per_side: Optional[float] = None,
                               slippage_bps: Optional[float] = None,
                               name: Optional[str] = None,
                               ) -> Dict[str, Any]:
        acc = await self.get_or_create_default()
        if fees_bps_per_side is not None:
            acc["fees_bps_per_side"] = float(fees_bps_per_side)
        if slippage_bps is not None:
            acc["slippage_bps"] = float(slippage_bps)
        if name is not None:
            acc["name"] = str(name)
        await self.update_account(acc)
        return acc

    # ── Positions ───────────────────────────────────────────────────────
    async def insert_position(self, position: Dict[str, Any]) -> None:
        await self.positions.insert_one(dict(position))

    async def upsert_position(self, position: Dict[str, Any]) -> None:
        d = {k: v for k, v in position.items() if k != "_id"}
        await self.positions.replace_one(
            {"position_id": position["position_id"]}, d, upsert=True)

    async def get_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        return await self.positions.find_one({"position_id": position_id},
                                              {"_id": 0})

    async def list_open_positions(self) -> List[Dict[str, Any]]:
        cur = self.positions.find({"status": "open"}, {"_id": 0}).sort(
            "opened_at", -1)
        return await cur.to_list(500)

    async def delete_position(self, position_id: str) -> bool:
        res = await self.positions.delete_one({"position_id": position_id})
        return res.deleted_count > 0

    # ── Trades ──────────────────────────────────────────────────────────
    async def insert_trade(self, trade: Dict[str, Any]) -> None:
        await self.trades.insert_one(dict(trade))

    async def list_trades(self, limit: int = 500,
                          symbol: Optional[str] = None,
                          side: Optional[str] = None,
                          since: Optional[str] = None,
                          until: Optional[str] = None,
                          ) -> List[Dict[str, Any]]:
        q: Dict[str, Any] = {}
        if symbol: q["symbol"] = symbol
        if side: q["side"] = side
        if since or until:
            q["closed_at"] = {}
            if since: q["closed_at"]["$gte"] = since
            if until: q["closed_at"]["$lte"] = until
        cur = self.trades.find(q, {"_id": 0}).sort("closed_at", -1)
        return await cur.to_list(limit)

    async def count_trades(self) -> int:
        return await self.trades.count_documents({})

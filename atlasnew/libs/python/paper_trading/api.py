"""FastAPI router for Paper Trading (v1.0.0).

All routes are mounted under `/api/paper/*`. Depends on:
  - `store`: PaperStore (Mongo persistence)
  - `fetch_smart(provider, symbol, interval, period)` for prices
  - `recommend_fn(...)` optional: to fetch the *current* Atlas recommendation
      when opening a position via the shortcut endpoint. Not required for
      manual open (`/positions/open`) which accepts a snapshot in the body.

Book 1: This module DOES NOT import from `decision_engine` or
`learning_system`. Recommendation payloads flow in as plain dicts.
"""
from __future__ import annotations
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import math
import numpy as np

from paper_trading.contracts import (
    PaperAccount, PaperPosition, PaperTrade,
    OpenPositionRequest, _utcnow,
)
from paper_trading.engine import (
    open_position, mark_to_market, close_position, check_tp_sl_hit,
    account_equity,
)
from paper_trading.analytics import compute_metrics, build_equity_curve
from paper_trading.store import PaperStore


# ── Pydantic wire schemas ────────────────────────────────────────────────
class ResetRequest(BaseModel):
    starting_balance: Optional[float] = None
    fees_bps_per_side: Optional[float] = None
    slippage_bps: Optional[float] = None


class SettingsRequest(BaseModel):
    fees_bps_per_side: Optional[float] = None
    slippage_bps: Optional[float] = None
    name: Optional[str] = None


class OpenReq(BaseModel):
    provider: str = "synthetic"
    symbol: str
    interval: str = "1d"
    side: str = Field(..., pattern="^(long|short)$")
    size_pct: float = Field(10.0, ge=0.01, le=100.0)
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    # If reference_price is not provided, backend fetches latest close.
    reference_price: Optional[float] = None
    # Full Atlas recommendation snapshot (opt-in). Frontend passes the
    # entire /api/decision/recommend payload to make the trade auditable.
    atlas_snapshot: Optional[Dict[str, Any]] = None
    note: str = ""


class CloseReq(BaseModel):
    exit_price: Optional[float] = None
    exit_reason: str = "manual"
    note: str = ""


class MarkAllReq(BaseModel):
    auto_close_on_tp_sl: bool = True


# ── Helpers ──────────────────────────────────────────────────────────────
def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, np.floating) or isinstance(obj, float):
        return None if not math.isfinite(obj) else float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return [_clean(v) for v in obj.tolist()]
    return obj


def _latest_bar(df) -> Optional[Dict[str, float]]:
    if df is None or getattr(df, "empty", True):
        return None
    row = df.iloc[-1]
    return {
        "close": float(row["close"]),
        "high": float(row.get("high", row["close"])),
        "low": float(row.get("low", row["close"])),
    }


class ModelDeployRequest(BaseModel):
    model_id: str
    symbol: str
    provider: str = "synthetic"
    interval: str = "1d"
    period: str = "6mo"
    size_pct: float = Field(10.0, ge=0.1, le=100.0)
    stop_loss_pct: float = Field(0.0, ge=0.0)
    take_profit_pct: float = Field(0.0, ge=0.0)
    upper_threshold: float = Field(0.55, ge=0.5, le=1.0)
    lower_threshold: float = Field(0.45, ge=0.0, le=0.5)
    preview_only: bool = False
    note: str = ""

def build_router(*, store: PaperStore, fetch_smart,
                  model_registry=None) -> APIRouter:
    """`fetch_smart(provider, symbol, interval, period) -> DataFrame`.
    `model_registry`: optional ModelRegistry for the model-deploy endpoint.
    """
    r = APIRouter(prefix="/api/paper-trading", tags=["paper-trading"])
    import asyncio
    _account_lock = asyncio.Lock()

    # ── Meta ────────────────────────────────────────────────────────────
    @r.get("/")
    async def meta():
        return {
            "app": "Atlas Paper Trading",
            "version": "1.0.0",
            "supports": {
                "one_open_position_per_symbol": True,
                "user_input_size_pct": True,
                "atlas_snapshot_capture": True,
                "auto_tp_sl_on_mark": True,
                "csv_export": True,
            }
        }

    # ── Account ─────────────────────────────────────────────────────────
    @r.get("/account")
    async def get_account():
        acc = await store.get_or_create_default()
        open_pos = await store.list_open_positions()
        equity = account_equity(acc, open_pos)
        unrealized = sum(p.get("unrealized_pnl", 0.0) or 0.0 for p in open_pos)
        return _clean({
            "account": acc,
            "equity": round(equity, 2),
            "unrealized_pnl": round(unrealized, 2),
            "open_position_count": len(open_pos),
        })

    @r.post("/account/reset")
    async def reset_account(req: ResetRequest):
        acc = await store.reset_account(
            starting_balance=req.starting_balance,
            fees_bps_per_side=req.fees_bps_per_side,
            slippage_bps=req.slippage_bps,
        )
        return _clean({"account": acc, "reset": True})

    @r.post("/account/settings")
    async def update_settings(req: SettingsRequest):
        acc = await store.update_settings(
            fees_bps_per_side=req.fees_bps_per_side,
            slippage_bps=req.slippage_bps,
            name=req.name,
        )
        return _clean({"account": acc})

    # ── Open positions ──────────────────────────────────────────────────
    @r.post("/positions/open")
    async def open_pos(req: OpenReq):
        async with _account_lock:
            return await _open_pos(req)
            
    async def _open_pos(req: OpenReq):
        acc = await store.get_or_create_default()
        open_positions = await store.list_open_positions()

        ref = req.reference_price
        if ref is None:
            df = fetch_smart(req.provider, req.symbol, req.interval, "6mo")
            latest = _latest_bar(df)
            if latest is None:
                raise HTTPException(404, "no market data to price the entry")
            ref = latest["close"]

        try:
            pos, updated_acc = open_position(
                account=acc,
                open_positions=open_positions,
                req=OpenPositionRequest(
                    account_id=acc.get("account_id", ""),
                    provider=req.provider,
                    symbol=req.symbol,
                    interval=req.interval,
                    side=req.side,
                    size_pct=req.size_pct,
                    stop_price=req.stop_price,
                    take_profit_price=req.take_profit_price,
                    reference_price=float(ref),
                    atlas_snapshot=req.atlas_snapshot,
                    note=req.note,
                ),
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

        d = pos.to_dict()
        d["last_mark_price"] = float(ref)
        d["last_mark_at"] = _utcnow()
        
        try:
            await store.insert_position(d)
        except Exception as e:
            import pymongo
            if isinstance(e, pymongo.errors.DuplicateKeyError):
                raise HTTPException(400, f"already an open position on {req.symbol} (concurrent request)")
            raise e
            
        await store.update_account(updated_acc)
        return _clean({"position": d, "account": updated_acc})

    @r.get("/positions/open")
    async def list_open():
        positions = await store.list_open_positions()
        # Mark-to-market on read for a fresh view (does not persist).
        marked = []
        for p in positions:
            df = fetch_smart(p["provider"], p["symbol"], p["interval"], "3mo")
            latest = _latest_bar(df)
            if latest:
                p2 = mark_to_market(p, latest["close"])
                marked.append(p2)
            else:
                marked.append(p)
        return _clean(marked)

    @r.post("/positions/mark")
    async def mark_all(req: MarkAllReq):
        async with _account_lock:
            return await _mark_all(req)
            
    async def _mark_all(req: MarkAllReq):
        """Mark every open position to the latest close. If auto_close_on_tp_sl
        is true (default), any position whose bar high/low crosses TP or SL
        is closed at the trigger price."""
        acc = await store.get_or_create_default()
        positions = await store.list_open_positions()
        marked, closed_ids = [], []
        for p in positions:
            df = fetch_smart(p["provider"], p["symbol"], p["interval"], "3mo")
            latest = _latest_bar(df)
            if latest is None:
                marked.append(p); continue
            hit = None
            if req.auto_close_on_tp_sl:
                hit = check_tp_sl_hit(p, latest["high"], latest["low"], latest["close"])
            if hit:
                reason, price = hit
                try:
                    trade, updated_acc = close_position(
                        acc, p, exit_price=price, exit_reason=reason,
                        note="auto-close on mark")
                except ValueError:
                    continue
                    
                deleted = await store.delete_position(p["position_id"])
                if deleted:
                    await store.insert_trade(trade.to_dict())
                    await store.update_account(updated_acc)
                    acc = updated_acc
                    closed_ids.append(trade.trade_id)
            else:
                p2 = mark_to_market(p, latest["close"])
                await store.upsert_position(p2)
                marked.append(p2)
        return _clean({
            "marked": marked,
            "closed_trade_ids": closed_ids,
            "account": acc,
        })

    @r.post("/positions/{position_id}/close")
    async def manual_close(position_id: str, req: CloseReq):
        async with _account_lock:
            return await _manual_close(position_id, req)
            
    async def _manual_close(position_id: str, req: CloseReq):
        acc = await store.get_or_create_default()
        pos = await store.get_position(position_id)
        if not pos:
            raise HTTPException(404, "position not found")
        if pos.get("status") != "open":
            raise HTTPException(400, "position not open")

        price = req.exit_price
        if price is None:
            df = fetch_smart(pos["provider"], pos["symbol"], pos["interval"], "3mo")
            latest = _latest_bar(df)
            if latest is None:
                raise HTTPException(404, "no market data to price the exit")
            price = latest["close"]

        try:
            trade, updated_acc = close_position(
                acc, pos, exit_price=float(price),
                exit_reason=req.exit_reason or "manual",
                note=req.note)
        except ValueError as e:
            raise HTTPException(400, str(e))
            
        deleted = await store.delete_position(position_id)
        if not deleted:
            raise HTTPException(400, "position already closed concurrently")
            
        await store.insert_trade(trade.to_dict())
        await store.update_account(updated_acc)
        return _clean({"trade": trade.to_dict(), "account": updated_acc})

    # ── Trades ──────────────────────────────────────────────────────────
    @r.get("/trades")
    async def list_trades(limit: int = 200,
                            symbol: Optional[str] = None,
                            side: Optional[str] = None,
                            since: Optional[str] = None,
                            until: Optional[str] = None):
        docs = await store.list_trades(limit=limit, symbol=symbol,
                                         side=side, since=since, until=until)
        return _clean(docs)

    @r.get("/trades/{trade_id}")
    async def get_trade(trade_id: str):
        doc = await store.trades.find_one({"trade_id": trade_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "trade not found")
        return _clean(doc)

    @r.get("/trades.csv")
    async def trades_csv(limit: int = 5000,
                         symbol: Optional[str] = None,
                         side: Optional[str] = None):
        """CSV export of trade history. Omits atlas_snapshot for readability;
        callers who want the full snapshot should hit /trades or /trades/{id}."""
        from fastapi.responses import PlainTextResponse
        docs = await store.list_trades(limit=limit, symbol=symbol, side=side)
        cols = [
            "trade_id", "symbol", "provider", "interval", "side", "quantity",
            "entry_price", "exit_price", "stop_price", "take_profit_price",
            "fees_paid", "slippage_cost", "realized_pnl", "realized_pnl_pct",
            "r_multiple", "exit_reason", "opened_at", "closed_at",
            "holding_seconds", "bars_held", "note",
        ]
        lines = [",".join(cols)]
        for d in docs:
            row = []
            for c in cols:
                v = d.get(c)
                if v is None: row.append("")
                elif isinstance(v, str):
                    row.append('"' + v.replace('"', '""') + '"')
                else:
                    row.append(str(v))
            lines.append(",".join(row))
        return PlainTextResponse("\n".join(lines), media_type="text/csv")

    # ── Analytics ───────────────────────────────────────────────────────
    @r.get("/analytics")
    async def analytics(limit: int = 5000):
        acc = await store.get_or_create_default()
        trades = await store.list_trades(limit=limit)
        open_positions = await store.list_open_positions()
        metrics = compute_metrics(acc.get("starting_balance", 100_000.0),
                                    trades)
        curve = build_equity_curve(acc.get("starting_balance", 100_000.0),
                                     trades)
        unreal = sum((p.get("unrealized_pnl") or 0.0) for p in open_positions)
        equity = account_equity(acc, open_positions)
        return _clean({
            "account": acc,
            "metrics": metrics,
            "equity_curve": curve,
            "equity": round(equity, 2),
            "unrealized_pnl": round(unreal, 2),
            "open_position_count": len(open_positions),
            "closed_trade_count": len(trades),
        })

    # ── Model Deploy → Paper Trading ────────────────────────────────────
    @r.post("/model-deploy")
    async def model_deploy(req: ModelDeployRequest):
        """Run inference with a trained model and open a paper position if signal is clear.

        Returns: signal direction, probability, and position details if opened.
        Requires model_registry to be injected into build_router.
        """
        if model_registry is None:
            raise HTTPException(503, "Model registry not available")

        # 1. Fetch model metadata and artifact
        meta = await model_registry.get(req.model_id)
        if meta is None:
            raise HTTPException(404, f"Model '{req.model_id}' not found")
        model = await model_registry.load_model(req.model_id)
        if model is None:
            raise HTTPException(500, "Failed to load model artifact — retrain the model")

        feature_ids = list(meta.get("feature_ids") or [])
        if not feature_ids:
            raise HTTPException(400, "Model has no feature_ids recorded — retrain the model")

        # 2. Fetch latest market data
        df = fetch_smart(req.provider, req.symbol, req.interval, req.period)
        if df is None or len(df) < 10:
            raise HTTPException(404, f"No market data for {req.symbol}")

        # 3. Build feature matrix and predict on the latest bar
        try:
            from learning_system.dataset.feature_matrix import build_feature_matrix
            X = build_feature_matrix(df, feature_ids)
            X_latest = X.dropna().iloc[[-1]]  # last complete bar
            if X_latest.empty:
                raise HTTPException(400, "Feature matrix is all-NaN — insufficient data")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Feature computation failed: {e}")

        try:
            proba = model.predict_proba(X_latest)
            prob_up = float(proba[0, 1])
        except Exception as e:
            raise HTTPException(500, f"Model prediction failed: {e}")

        # 4. Determine signal
        if prob_up >= req.upper_threshold:
            signal = "long"
        elif prob_up <= req.lower_threshold:
            signal = "short"
        else:
            signal = "FLAT"

        inference_result = {
            "model_id": req.model_id,
            "model_kind": meta.get("kind", "unknown"),
            "prob_up": round(prob_up, 4),
            "prob_down": round(1.0 - prob_up, 4),
            "signal": signal,
            "upper_threshold": req.upper_threshold,
            "lower_threshold": req.lower_threshold,
            "feature_count": len(feature_ids),
            "bar_time": str(X_latest.index[-1]) if len(X_latest) else None,
        }

        # 5. Open position if signal is clear and not preview-only
        if req.preview_only or req.note == "__signal_preview__":
            return _clean({
                "position_opened": False,
                "reason": "Preview mode (read-only)",
                "inference": inference_result,
            })

        if signal in ("long", "short"):
            ref = float(df["close"].iloc[-1])
            stop_price = None
            take_profit_price = None
            if req.stop_loss_pct > 0:
                stop_price = ref * (1 - req.stop_loss_pct / 100) if signal == "long" else ref * (1 + req.stop_loss_pct / 100)
            if req.take_profit_pct > 0:
                take_profit_price = ref * (1 + req.take_profit_pct / 100) if signal == "long" else ref * (1 - req.take_profit_pct / 100)

            acc = await store.get_or_create_default()
            open_positions = await store.list_open_positions()
            try:
                pos, updated_acc = open_position(
                    account=acc,
                    open_positions=open_positions,
                    req=OpenPositionRequest(
                        account_id=acc.get("account_id", ""),
                        provider=req.provider,
                        symbol=req.symbol,
                        interval=req.interval,
                        side=signal,
                        size_pct=req.size_pct,
                        stop_price=stop_price,
                        take_profit_price=take_profit_price,
                        reference_price=ref,
                        atlas_snapshot={"inference": inference_result, "model_meta": meta},
                        note=req.note or f"Model deploy: {req.model_id} ({signal}, p={prob_up:.3f})",
                    ),
                )
            except ValueError as e:
                # Position already open or insufficient funds — still return the signal
                return _clean({
                    "position_opened": False,
                    "reason": str(e),
                    "inference": inference_result,
                })

            pos_dict = pos.to_dict()
            pos_dict["last_mark_price"] = float(ref)
            pos_dict["last_mark_at"] = _utcnow()
            await store.insert_position(pos_dict)
            await store.update_account(updated_acc)
            # Register active bot session in atlas_bots for real-time portfolio monitoring
            if hasattr(store, "_db") and store._db is not None:
                try:
                    await store._db.atlas_bots.update_one(
                        {"model_id": req.model_id, "symbol": req.symbol},
                        {"$set": {
                            "name": f"{meta.get('kind', 'Model').upper()}-{req.symbol} ({len(feature_ids)} Feats)",
                            "market": f"{req.symbol} ({req.interval})",
                            "status": "Active",
                            "allocation": float(req.size_pct * 1000.0),
                            "unrealized_pnl": 0.0,
                            "trades_count": 1,
                            "model_id": req.model_id,
                            "updated_at": _utcnow()
                        }},
                        upsert=True
                    )
                except Exception:
                    pass
            return _clean({
                "position_opened": True,
                "inference": inference_result,
                "position": pos_dict,
                "account": updated_acc,
            })
        else:
            return _clean({
                "position_opened": False,
                "reason": f"Signal is FLAT (prob_up={prob_up:.3f}, thresholds=[{req.lower_threshold}, {req.upper_threshold}])",
                "inference": inference_result,
            })

    return r

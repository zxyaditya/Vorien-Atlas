"""Paper Trading engine — open, mark-to-market, close.

Operates on plain dataclasses; delegates persistence to `store.py` at the
FastAPI layer. No Atlas Core imports.
"""
from __future__ import annotations
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timezone
import math

from paper_trading.contracts import (
    PaperAccount, PaperPosition, PaperTrade,
    OpenPositionRequest, ClosePositionRequest, _utcnow,
)


def _safe(x, default=0.0):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _apply_slippage(reference_price: float, side: str, slippage_bps: float,
                     kind: str) -> float:
    """Adverse slippage. `kind` in {'entry','exit'}. Long entry / short exit
    pay uptick; short entry / long exit pay downtick."""
    if reference_price is None or reference_price <= 0:
        return reference_price
    adverse = slippage_bps / 10_000.0
    if kind == "entry":
        return reference_price * (1 + adverse) if side == "long" else reference_price * (1 - adverse)
    else:  # exit
        return reference_price * (1 - adverse) if side == "long" else reference_price * (1 + adverse)


def account_equity(account: Dict[str, Any],
                   open_positions: List[Dict[str, Any]]) -> float:
    """cash + notional_at_entry + sum of unrealized PnL on open positions."""
    unreal = sum(_safe(p.get("unrealized_pnl")) for p in open_positions)
    notional = sum(_safe(p.get("notional_at_entry")) for p in open_positions)
    return _safe(account.get("cash")) + notional + unreal


def compute_position_size(equity: float, price: float, size_pct: float) -> float:
    """quantity = (equity * size_pct%) / price."""
    if price is None or price <= 0 or equity <= 0:
        return 0.0
    notional = equity * (max(0.0, min(100.0, size_pct)) / 100.0)
    return notional / price


def open_position(account: Dict[str, Any],
                   open_positions: List[Dict[str, Any]],
                   req: OpenPositionRequest) -> Tuple[PaperPosition, Dict[str, Any]]:
    """Return (new_position, updated_account_dict). Raises ValueError on
    invalid input (bad side, duplicate symbol, non-positive quantity, etc.)."""
    if req.side not in ("long", "short"):
        raise ValueError(f"invalid side: {req.side!r}")
    if req.reference_price is None or req.reference_price <= 0:
        raise ValueError("reference_price must be positive")

    # v1.0 policy: one open position per symbol (per account).
    for p in open_positions:
        if p.get("symbol") == req.symbol and p.get("status") == "open":
            raise ValueError(
                f"already an open position on {req.symbol}; close it first")

    slip = _safe(account.get("slippage_bps"), 0.0)
    fee_bps = _safe(account.get("fees_bps_per_side"), 0.0)

    fill_price = _apply_slippage(req.reference_price, req.side, slip, "entry")
    equity = account_equity(account, open_positions)
    quantity = compute_position_size(equity, fill_price, req.size_pct)
    if quantity <= 0:
        raise ValueError("computed quantity is zero — check size_pct / price")

    notional = quantity * fill_price
    entry_fees = notional * (fee_bps / 10_000.0)

    cost = notional + entry_fees
    if _safe(account.get("cash")) < cost:
        raise ValueError(f"Insufficient buying power. Cost: {cost:.2f}, Cash: {_safe(account.get('cash')):.2f}")

    pos = PaperPosition(
        account_id=req.account_id,
        symbol=req.symbol,
        provider=req.provider,
        interval=req.interval,
        side=req.side,
        quantity=quantity,
        notional_at_entry=notional,
        entry_price=fill_price,
        reference_price=req.reference_price,
        stop_price=req.stop_price,
        take_profit_price=req.take_profit_price,
        fees_paid=entry_fees,
        size_pct=req.size_pct,
        atlas_snapshot=req.atlas_snapshot or {},
        note=req.note or "",
    )

    # Deduct notional + entry fee from cash. Short positions still hold cash
    # (v1.0 simplification: no margin model; short is symmetric to long).
    updated = dict(account)
    updated["cash"] = _safe(account.get("cash")) - notional - entry_fees
    updated["updated_at"] = _utcnow()
    return pos, updated


def mark_to_market(position: Dict[str, Any], mark_price: float) -> Dict[str, Any]:
    """Return a copy of the position with updated unrealized PnL fields.
    Does NOT auto-close on TP/SL — caller decides based on hit flags."""
    p = dict(position)
    side = p.get("side", "long")
    q = _safe(p.get("quantity"))
    entry = _safe(p.get("entry_price"))
    if q <= 0 or entry <= 0 or mark_price <= 0:
        return p
    sign = 1.0 if side == "long" else -1.0
    unreal = sign * q * (mark_price - entry)
    p["last_mark_price"] = float(mark_price)
    p["last_mark_at"] = _utcnow()
    p["unrealized_pnl"] = round(unreal, 2)
    denom = _safe(p.get("notional_at_entry"))
    p["unrealized_pnl_pct"] = round(100.0 * unreal / denom, 4) if denom else 0.0
    p["updated_at"] = _utcnow()
    return p


def check_tp_sl_hit(position: Dict[str, Any], high: float, low: float,
                    close: float) -> Optional[Tuple[str, float]]:
    """Return (exit_reason, exit_price) if TP or SL is hit inside the bar.
    Priority: SL first (conservative). Uses bar high/low; if unavailable,
    falls back to close-vs-threshold comparison.
    """
    side = position.get("side", "long")
    sl = position.get("stop_price")
    tp = position.get("take_profit_price")
    high = _safe(high, close)
    low = _safe(low, close)

    if side == "long":
        if sl is not None and low <= sl:
            return ("stop_loss", float(sl))
        if tp is not None and high >= tp:
            return ("take_profit", float(tp))
    else:  # short
        if sl is not None and high >= sl:
            return ("stop_loss", float(sl))
        if tp is not None and low <= tp:
            return ("take_profit", float(tp))
    return None


def close_position(account: Dict[str, Any],
                    position: Dict[str, Any],
                    exit_price: float,
                    exit_reason: str = "manual",
                    note: str = "") -> Tuple[PaperTrade, Dict[str, Any]]:
    """Realise the position at `exit_price`. `exit_price` is expected to
    already reflect any slippage the caller wants applied (auto-close
    paths pass raw trigger; manual pass the current close).

    Returns (trade_record, updated_account_dict).
    """
    side = position.get("side", "long")
    q = _safe(position.get("quantity"))
    entry = _safe(position.get("entry_price"))
    if q <= 0 or entry <= 0 or exit_price <= 0:
        raise ValueError("cannot close: invalid quantity or prices")

    slip = _safe(account.get("slippage_bps"), 0.0)
    fee_bps = _safe(account.get("fees_bps_per_side"), 0.0)
    fill_exit = _apply_slippage(exit_price, side, slip, "exit")

    sign = 1.0 if side == "long" else -1.0
    gross = sign * q * (fill_exit - entry)
    exit_notional = q * fill_exit
    exit_fees = exit_notional * (fee_bps / 10_000.0)
    entry_fees = _safe(position.get("fees_paid"))
    fees_total = entry_fees + exit_fees
    ref_price = position.get("reference_price")
    ref_price = ref_price if ref_price is not None else entry
    slip_cost = q * abs(exit_price - fill_exit) + q * abs(entry - ref_price)

    realized = gross - exit_fees   # entry fee already deducted from cash on open
    net_pnl_full = gross - fees_total  # for reporting
    notional_at_entry = _safe(position.get("notional_at_entry"))
    realized_pct = (100.0 * net_pnl_full / notional_at_entry) if notional_at_entry else 0.0

    # R-multiple: PnL vs initial risk = |entry - stop| * quantity.
    r_multiple = None
    sl = position.get("stop_price")
    if sl is not None:
        risk_per_unit = abs(entry - _safe(sl))
        risk_total = risk_per_unit * q
        if risk_total > 0:
            r_multiple = round(net_pnl_full / risk_total, 3)

    opened_at = position.get("opened_at", "")
    now = _utcnow()
    try:
        t0 = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(now.replace("Z", "+00:00"))
        holding_seconds = (t1 - t0).total_seconds()
    except Exception:
        holding_seconds = 0.0

    trade = PaperTrade(
        position_id=position.get("position_id", ""),
        account_id=position.get("account_id", ""),
        symbol=position.get("symbol", ""),
        provider=position.get("provider", "synthetic"),
        interval=position.get("interval", "1d"),
        side=side,
        quantity=q,
        entry_price=entry,
        exit_price=fill_exit,
        stop_price=position.get("stop_price"),
        take_profit_price=position.get("take_profit_price"),
        fees_paid=round(fees_total, 4),
        slippage_cost=round(slip_cost, 4),
        realized_pnl=round(net_pnl_full, 2),
        realized_pnl_pct=round(realized_pct, 4),
        r_multiple=r_multiple,
        exit_reason=exit_reason,
        opened_at=opened_at,
        closed_at=now,
        holding_seconds=holding_seconds,
        atlas_snapshot=position.get("atlas_snapshot", {}) or {},
        note=note or position.get("note", ""),
    )

    # Cash accounting: return notional + realized PnL - exit fee.
    # Entry side already debited notional+entry_fee on open.
    updated = dict(account)
    updated["cash"] = _safe(account.get("cash")) + notional_at_entry + realized
    updated["realized_pnl"] = _safe(account.get("realized_pnl")) + trade.realized_pnl
    updated["updated_at"] = now
    return trade, updated

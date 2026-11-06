"""PaperExecutionEngine — simulated fills at bar close with fees+slippage.

Exactly the same interface as `LiveExecutionEngine` (which is a stub
today). This is the single, deterministic implementation used for both
historical backtests and forward-in-time paper trading. When the live
engine ships, no strategy code changes.
"""
from __future__ import annotations
import uuid
from typing import Optional

from learning_system.backtest.execution.base import ExecutionEngine
from learning_system.backtest.portfolio import Portfolio


class PaperExecutionEngine(ExecutionEngine):
    def __init__(self, initial_cash: float = 100_000.0,
                  fee_bps: float = 5.0, slippage_bps: float = 5.0):
        self.portfolio = Portfolio(initial_cash)
        self.fee_bps = float(fee_bps)
        self.slippage_bps = float(slippage_bps)

    # ---- helpers -----------------------------------------------------
    def _apply_slippage(self, price: float, direction: int) -> float:
        """Buys pay slightly more, sells receive slightly less."""
        adj = price * self.slippage_bps / 10_000.0
        return price + adj if direction > 0 else price - adj

    def _fee(self, notional: float) -> float:
        return abs(notional) * self.fee_bps / 10_000.0

    # ---- interface ---------------------------------------------------
    def open_position(self, direction: int, size: float, price: float,
                       timestamp: str, reason: str = "") -> dict:
        if self.portfolio.has_open_position():
            raise ValueError(
                "cannot open: existing position must be closed first"
            )
        fill_price = self._apply_slippage(price, direction)
        notional = fill_price * size
        fee = self._fee(notional)
        # Reserve fee from cash; cash unchanged until close for the
        # symmetric long/short bookkeeping (paper broker convention).
        self.portfolio.cash -= fee
        trade_id = uuid.uuid4().hex
        self.portfolio.open_trade = {
            "trade_id": trade_id,
            "direction": int(direction),
            "open_time": timestamp,
            "open_price": float(fill_price),
            "size": float(size),
            "fee_paid": float(fee),
            "open_reason": reason,
        }
        return dict(self.portfolio.open_trade)

    def close_position(self, price: float, timestamp: str,
                        reason: str = "") -> dict:
        if not self.portfolio.has_open_position():
            raise ValueError("no open position to close")
        ot = self.portfolio.open_trade
        direction = int(ot["direction"])
        size = float(ot["size"])
        entry = float(ot["open_price"])
        # Reverse-direction slippage for the exit fill.
        exit_price = self._apply_slippage(price, -direction)
        notional = exit_price * size
        exit_fee = self._fee(notional)
        gross = (exit_price - entry) * size * direction
        total_fee = float(ot["fee_paid"]) + exit_fee
        pnl = gross - exit_fee
        # Realise into cash.
        self.portfolio.cash += pnl
        return_pct = pnl / (entry * size) * 100.0 if entry * size else 0.0
        trade = {
            "trade_id": ot["trade_id"],
            "direction": direction,
            "open_time": ot["open_time"],
            "open_price": entry,
            "close_time": timestamp,
            "close_price": float(exit_price),
            "size": size,
            "fee_paid": float(total_fee),
            "pnl": float(pnl),
            "return_pct": float(return_pct),
            "open_reason": ot["open_reason"],
            "close_reason": reason,
        }
        self.portfolio.closed_trades.append(trade)
        self.portfolio.open_trade = None
        return trade

    def mark_to_market(self, price: float, timestamp: str) -> dict:
        equity = self.portfolio.cash
        exposure = 0.0
        open_dir = 0
        if self.portfolio.has_open_position():
            ot = self.portfolio.open_trade
            direction = int(ot["direction"])
            size = float(ot["size"])
            entry = float(ot["open_price"])
            unrealised = (price - entry) * size * direction
            equity += unrealised
            exposure = float(price * size * direction)
            open_dir = direction
        return {
            "time": timestamp, "equity": float(equity),
            "cash": float(self.portfolio.cash),
            "exposure": float(exposure),
            "open_position": int(open_dir),
            "price": float(price),
        }

    def has_open_position(self) -> bool:
        return self.portfolio.has_open_position()

    def position_direction(self) -> int:
        if not self.portfolio.has_open_position():
            return 0
        return int(self.portfolio.open_trade["direction"])

    def snapshot(self) -> dict:
        return {
            "cash": float(self.portfolio.cash),
            "n_closed_trades": len(self.portfolio.closed_trades),
            "has_open": self.portfolio.has_open_position(),
        }

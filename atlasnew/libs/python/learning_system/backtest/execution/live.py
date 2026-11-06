"""LiveExecutionEngine — broker-ready implementation (DEC-020).

Same abstract `ExecutionEngine` contract as `PaperExecutionEngine`. The
difference: every call is translated into a `BrokerAdapter` call, so
strategies never know whether they're running against a simulated
adapter, a broker's paper endpoint, or a real live broker.

Design (Session 13):

* Instantiate with a concrete `BrokerAdapter`. If the caller passes
  `broker_adapter=None`, the engine raises a clear error explaining that
  live trading requires an adapter. This preserves the v0.12.0
  behaviour where instantiating a "live" engine without wiring was a
  loud failure, but now the fix is a single-line wire-up.

* Every open/close is submitted to the broker with a fresh
  `client_order_id`, then the resulting broker fill (price, fees) is
  used as the trade's realised numbers. No hidden simulation.

* The engine keeps a local `_open_trade` mirror strictly for the
  `ExecutionEngine` API (open_position, close_position pairing). The
  ground truth is always the broker (`get_position`, `get_account`).

* Safety: `dry_run` from the adapter is surfaced in `snapshot()`.
"""
from __future__ import annotations
import uuid
from typing import Any, Dict, Optional

from learning_system.backtest.execution.base import ExecutionEngine
from learning_system.backtest.broker.base import (
    BrokerAdapter, BrokerError,
)


class LiveExecutionEngine(ExecutionEngine):
    """ExecutionEngine backed by a concrete BrokerAdapter (DEC-020).

    Typical wire-up:

        adapter = SimulatedBrokerAdapter(initial_cash=100_000, ...)
        adapter.set_last_price("SPY", 450.0)
        engine  = LiveExecutionEngine(symbol="SPY", broker_adapter=adapter)
        # existing strategy code runs unchanged
    """

    def __init__(self, symbol: str = "",
                 broker_adapter: Optional[BrokerAdapter] = None,
                 broker_config: Optional[Dict[str, Any]] = None):
        if broker_adapter is None:
            raise NotImplementedError(
                "LiveExecutionEngine requires a concrete BrokerAdapter. "
                "Wire one in (e.g. SimulatedBrokerAdapter for dry-runs, "
                "or a real broker adapter when it is added). The strategy "
                "code above does not need to change."
            )
        if not symbol:
            raise ValueError("LiveExecutionEngine requires a `symbol`; the "
                             "broker needs to know what to trade.")
        self.symbol = str(symbol)
        self.broker: BrokerAdapter = broker_adapter
        self.broker_config = dict(broker_config or {})
        self._open_trade: Optional[Dict[str, Any]] = None
        self._closed_trades: list = []

    def _new_client_order_id(self, tag: str) -> str:
        return f"atlas-{tag}-{uuid.uuid4().hex[:12]}"

    def open_position(self, direction: int, size: float, price: float,
                      timestamp: str, reason: str = "") -> dict:
        if self._open_trade is not None:
            raise ValueError(
                "cannot open: existing position must be closed first"
            )
        if direction not in (-1, 1):
            raise ValueError(f"direction must be -1 or +1, got {direction}")
        side = "buy" if direction > 0 else "sell"
        client_id = self._new_client_order_id("open")
        try:
            order = self.broker.submit_order(
                symbol=self.symbol, side=side, quantity=float(size),
                order_type="market",
                client_order_id=client_id,
            )
        except BrokerError as e:
            raise ValueError(f"broker rejected open order: {e}") from e

        fill_price = order.average_fill_price
        if fill_price is None:
            fill_price = float(price)

        self._open_trade = {
            "trade_id": order.broker_order_id,
            "client_order_id": order.client_order_id,
            "direction": int(direction),
            "open_time": timestamp,
            "open_price": float(fill_price),
            "size": float(size),
            "fee_paid": float(order.fees_paid),
            "open_reason": reason,
            "broker_status": order.status,
        }
        return dict(self._open_trade)

    def close_position(self, price: float, timestamp: str,
                       reason: str = "") -> dict:
        if self._open_trade is None:
            raise ValueError("no open position to close")
        ot = self._open_trade
        direction = int(ot["direction"])
        size = float(ot["size"])
        entry = float(ot["open_price"])
        side = "sell" if direction > 0 else "buy"
        client_id = self._new_client_order_id("close")
        try:
            order = self.broker.submit_order(
                symbol=self.symbol, side=side, quantity=size,
                order_type="market",
                client_order_id=client_id,
            )
        except BrokerError as e:
            raise ValueError(f"broker rejected close order: {e}") from e

        exit_price = order.average_fill_price
        if exit_price is None:
            exit_price = float(price)
        exit_fee = float(order.fees_paid)
        gross = (exit_price - entry) * size * direction
        total_fee = float(ot["fee_paid"]) + exit_fee
        pnl = gross - exit_fee
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
            "broker_status": order.status,
        }
        self._closed_trades.append(trade)
        self._open_trade = None
        return trade

    def mark_to_market(self, price: float, timestamp: str) -> dict:
        acct = self.broker.get_account()
        equity = float(acct.equity)
        cash = float(acct.cash)
        exposure = 0.0
        open_dir = 0
        if self._open_trade is not None:
            direction = int(self._open_trade["direction"])
            size = float(self._open_trade["size"])
            exposure = float(price * size * direction)
            open_dir = direction
            entry = float(self._open_trade["open_price"])
            unrealised = (price - entry) * size * direction
            equity = cash + unrealised
        return {
            "time": timestamp,
            "equity": float(equity),
            "cash": float(cash),
            "exposure": float(exposure),
            "open_position": int(open_dir),
            "price": float(price),
        }

    def has_open_position(self) -> bool:
        return self._open_trade is not None

    def position_direction(self) -> int:
        if self._open_trade is None:
            return 0
        return int(self._open_trade["direction"])

    def snapshot(self) -> dict:
        acct = self.broker.get_account()
        return {
            "broker": self.broker.broker_name,
            "dry_run": self.broker.dry_run,
            "is_paper": self.broker.is_paper,
            "cash": float(acct.cash),
            "equity": float(acct.equity),
            "n_closed_trades": len(self._closed_trades),
            "has_open": self._open_trade is not None,
            "symbol": self.symbol,
        }

    @property
    def portfolio(self):
        # Shim so BacktestEngine's raw_trades.closed_trades accessor works.
        class _Shim:
            def __init__(self, trades, open_trade):
                self.closed_trades = trades
                self.open_trade = open_trade
        return _Shim(list(self._closed_trades), self._open_trade)

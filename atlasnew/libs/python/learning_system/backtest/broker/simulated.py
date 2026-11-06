"""SimulatedBrokerAdapter — an in-memory broker used for tests.

This is NOT a real broker. It exists so `LiveExecutionEngine` can be
wired end-to-end against a concrete `BrokerAdapter` today, without any
real broker credentials, so:

  * the engine ↔ adapter plumbing is exercised in tests,
  * developers can validate a strategy against the live-engine code path
    before signing up for a real broker.

When a real broker adapter is added (Alpaca, IB, Binance) the strategy
and the LiveExecutionEngine both stay identical.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from learning_system.backtest.broker.base import (
    BrokerAdapter, BrokerAccount, BrokerError, BrokerOrder, BrokerPosition,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SimulatedBrokerAdapter(BrokerAdapter):
    """Deterministic in-memory broker for tests and dry-runs.

    Behaves like a market broker with immediate fills at the last known
    price. Applies fee_bps and slippage_bps symmetrically. Idempotent
    on `client_order_id`.
    """

    broker_name = "simulated"

    def __init__(self, initial_cash: float = 100_000.0,
                 fee_bps: float = 5.0, slippage_bps: float = 5.0,
                 last_prices: Optional[Dict[str, float]] = None,
                 *, dry_run: bool = False, is_paper: bool = True):
        super().__init__({"initial_cash": initial_cash,
                          "fee_bps": fee_bps,
                          "slippage_bps": slippage_bps},
                         dry_run=dry_run, is_paper=is_paper)
        self.cash = float(initial_cash)
        self.fee_bps = float(fee_bps)
        self.slippage_bps = float(slippage_bps)
        self._last_prices: Dict[str, float] = dict(last_prices or {})
        self._positions: Dict[str, BrokerPosition] = {}
        self._orders_by_broker_id: Dict[str, BrokerOrder] = {}
        self._orders_by_client_id: Dict[str, str] = {}   # client → broker

    # ---- test helpers (not part of BrokerAdapter contract) --------------
    def set_last_price(self, symbol: str, price: float) -> None:
        self._last_prices[symbol] = float(price)

    # ---- Account -------------------------------------------------------
    def get_account(self) -> BrokerAccount:
        equity = self.cash + sum(p.market_value for p in self._positions.values())
        return BrokerAccount(cash=self.cash, equity=equity,
                              buying_power=self.cash,
                              currency="USD", account_id="SIM-ACC")

    def get_position(self, symbol: str) -> Optional[BrokerPosition]:
        return self._positions.get(symbol)

    def get_last_price(self, symbol: str) -> float:
        if symbol not in self._last_prices:
            raise BrokerError(f"no last price known for {symbol!r}")
        return float(self._last_prices[symbol])

    # ---- Orders --------------------------------------------------------
    def submit_order(self, symbol, side, quantity, order_type="market",
                     limit_price=None, client_order_id=None,
                     time_in_force="day") -> BrokerOrder:
        if side not in ("buy", "sell"):
            raise BrokerError(f"invalid side {side!r}")
        if quantity <= 0:
            raise BrokerError(f"quantity must be positive, got {quantity}")
        if order_type not in ("market", "limit"):
            raise BrokerError(f"unsupported order_type {order_type!r}")

        client_id = client_order_id or uuid.uuid4().hex
        # Idempotency: return the original receipt if we've seen this id.
        if client_id in self._orders_by_client_id:
            existing_id = self._orders_by_client_id[client_id]
            return self._orders_by_broker_id[existing_id]

        broker_id = uuid.uuid4().hex
        submitted_at = _now()

        if self.dry_run:
            order = BrokerOrder(
                client_order_id=client_id, broker_order_id=broker_id,
                symbol=symbol, side=side, quantity=float(quantity),
                order_type=order_type, status="submitted",
                filled_quantity=0.0, average_fill_price=None,
                fees_paid=0.0, submitted_at=submitted_at,
                metadata={"dry_run": True},
            )
            self._orders_by_broker_id[broker_id] = order
            self._orders_by_client_id[client_id] = broker_id
            return order

        # Determine fill price
        if order_type == "market":
            base_price = self.get_last_price(symbol)
        else:
            base_price = float(limit_price) if limit_price is not None else self.get_last_price(symbol)

        direction = 1 if side == "buy" else -1
        slip = base_price * self.slippage_bps / 10_000.0
        fill_price = base_price + slip if direction > 0 else base_price - slip
        notional = fill_price * quantity
        fee = abs(notional) * self.fee_bps / 10_000.0

        # Update position
        pos = self._positions.get(symbol)
        signed_qty = direction * float(quantity)
        if pos is None:
            new_qty = signed_qty
            new_avg = fill_price
        else:
            # Weighted-average entry only when adding to same side.
            if (pos.quantity >= 0 and signed_qty >= 0) or (pos.quantity < 0 and signed_qty < 0):
                total_qty = pos.quantity + signed_qty
                if total_qty == 0:
                    new_qty = 0.0
                    new_avg = 0.0
                else:
                    new_avg = (pos.average_entry_price * pos.quantity
                                + fill_price * signed_qty) / total_qty
                    new_qty = total_qty
            else:
                # Reducing / flipping. Keep avg on residual, or reset.
                new_qty = pos.quantity + signed_qty
                if new_qty == 0:
                    new_avg = 0.0
                elif (pos.quantity > 0) != (new_qty > 0):
                    # Flipped sides — new average is the fill price.
                    new_avg = fill_price
                else:
                    # Same side, just smaller — keep old avg.
                    new_avg = pos.average_entry_price

        # Realise cash impact
        self.cash -= signed_qty * fill_price
        self.cash -= fee

        if new_qty == 0:
            self._positions.pop(symbol, None)
        else:
            mv = new_qty * fill_price
            self._positions[symbol] = BrokerPosition(
                symbol=symbol, quantity=float(new_qty),
                average_entry_price=float(new_avg),
                unrealised_pnl=0.0, market_value=float(mv),
            )

        filled_at = _now()
        order = BrokerOrder(
            client_order_id=client_id, broker_order_id=broker_id,
            symbol=symbol, side=side, quantity=float(quantity),
            order_type=order_type, status="filled",
            filled_quantity=float(quantity),
            average_fill_price=float(fill_price),
            fees_paid=float(fee),
            submitted_at=submitted_at, filled_at=filled_at,
            metadata={"simulated": True},
        )
        self._orders_by_broker_id[broker_id] = order
        self._orders_by_client_id[client_id] = broker_id
        return order

    def cancel_order(self, broker_order_id: str) -> BrokerOrder:
        order = self._orders_by_broker_id.get(broker_order_id)
        if order is None:
            raise BrokerError(f"unknown broker_order_id {broker_order_id!r}")
        if order.status != "submitted":
            return order
        cancelled = BrokerOrder(
            client_order_id=order.client_order_id,
            broker_order_id=order.broker_order_id,
            symbol=order.symbol, side=order.side, quantity=order.quantity,
            order_type=order.order_type, status="cancelled",
            filled_quantity=0.0, average_fill_price=None,
            fees_paid=0.0, submitted_at=order.submitted_at,
            metadata=dict(order.metadata),
        )
        self._orders_by_broker_id[broker_order_id] = cancelled
        return cancelled

    def get_order(self, broker_order_id: str) -> BrokerOrder:
        order = self._orders_by_broker_id.get(broker_order_id)
        if order is None:
            raise BrokerError(f"unknown broker_order_id {broker_order_id!r}")
        return order

    def list_open_orders(self, symbol: Optional[str] = None) -> List[BrokerOrder]:
        return [o for o in self._orders_by_broker_id.values()
                if o.status == "submitted"
                and (symbol is None or o.symbol == symbol)]

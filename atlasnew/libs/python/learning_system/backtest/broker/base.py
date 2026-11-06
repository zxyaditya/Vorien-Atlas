"""BrokerAdapter — abstract contract every real broker must implement.

DEC-020. The abstract interface is what makes `LiveExecutionEngine`
broker-agnostic. Adding Alpaca / IB / Binance later is a single-file
addition of a concrete subclass; strategies do not change.

Design rules (Session 13):

1. **Idempotency**: every `submit_order` MUST accept a `client_order_id`
   and MUST behave idempotently — resubmitting the same id returns the
   original order without duplicating execution. Real brokers can crash
   between our POST and their ack; we must be able to retry safely.

2. **Safety kill-switch**: adapters read a `dry_run` flag. If set,
   `submit_order` and `cancel_order` must be no-ops that log intent but
   never touch a real market. This is enforced at the adapter layer
   (not the engine layer) so it survives strategy bugs.

3. **Explicit numeric contracts**: quantities in "units" (contracts /
   shares / lots), prices in quote currency per unit. Fees & slippage
   are reported by the broker (not simulated) on the fill.

4. **No hidden state**: every call is a pure function of its inputs
   plus the broker's account state. Adapters MUST NOT cache positions
   locally — always read from the broker's ground truth.

5. **Immutable receipts**: `BrokerOrder` / `BrokerPosition` /
   `BrokerAccount` are frozen dataclasses. Once returned by the broker
   they are read-only.

No real broker credentials live here. This module contains only the
contract.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List


class BrokerError(Exception):
    """Every broker adapter raises this (or a subclass) on failure.

    Callers of `LiveExecutionEngine` should only ever have to catch
    `BrokerError` — never a broker-specific exception type.
    """


@dataclass(frozen=True)
class BrokerOrder:
    """Immutable order receipt returned by an adapter."""
    client_order_id: str
    broker_order_id: str
    symbol: str
    side: str            # "buy" | "sell"
    quantity: float
    order_type: str      # "market" | "limit"
    status: str          # "submitted" | "filled" | "rejected" | "cancelled"
    filled_quantity: float = 0.0
    average_fill_price: Optional[float] = None
    fees_paid: float = 0.0
    submitted_at: str = ""
    filled_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerPosition:
    symbol: str
    quantity: float       # signed: positive=long, negative=short
    average_entry_price: float
    unrealised_pnl: float
    market_value: float


@dataclass(frozen=True)
class BrokerAccount:
    cash: float
    equity: float
    buying_power: float
    currency: str = "USD"
    account_id: str = ""


class BrokerAdapter(ABC):
    """The single point of extension for real brokers.

    A concrete adapter (Alpaca / IB / Binance / ...) subclasses this and
    implements every abstract method. Nothing else in Atlas needs to
    change when a new broker is added.

    Two mandatory adapter-level flags:
      * `dry_run` — if True, `submit_order`/`cancel_order` return a
        simulated `BrokerOrder` without contacting the broker.
      * `is_paper` — True for the broker's paper-trading endpoint. Real
        brokers usually expose this via a different base URL or a flag.
    """

    #: Human-readable name, e.g. "alpaca" or "ibkr". Used in logs.
    broker_name: str = "abstract"

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 *, dry_run: bool = True, is_paper: bool = True):
        self.config = dict(config or {})
        # Safety: default to dry-run + paper. Only a deliberate flip in
        # the caller can enable real live trading.
        self.dry_run = bool(dry_run)
        self.is_paper = bool(is_paper)

    # ---- Account state -------------------------------------------------
    @abstractmethod
    def get_account(self) -> BrokerAccount: ...

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[BrokerPosition]: ...

    @abstractmethod
    def get_last_price(self, symbol: str) -> float: ...

    # ---- Orders --------------------------------------------------------
    @abstractmethod
    def submit_order(self, symbol: str, side: str, quantity: float,
                     order_type: str = "market",
                     limit_price: Optional[float] = None,
                     client_order_id: Optional[str] = None,
                     time_in_force: str = "day") -> BrokerOrder:
        """Idempotent order submission.

        `client_order_id` is required for idempotency. If the caller
        omits it, the adapter MUST synthesise a UUID.
        """

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> BrokerOrder: ...

    @abstractmethod
    def get_order(self, broker_order_id: str) -> BrokerOrder: ...

    @abstractmethod
    def list_open_orders(self, symbol: Optional[str] = None) -> List[BrokerOrder]: ...

    # ---- Introspection -------------------------------------------------
    def health(self) -> Dict[str, Any]:
        """Optional health-check. Concrete brokers should ping the API.

        Default implementation reports adapter-level flags only.
        """
        return {
            "broker": self.broker_name,
            "dry_run": self.dry_run,
            "is_paper": self.is_paper,
            "connected": True,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return (f"<{type(self).__name__} broker={self.broker_name!r} "
                f"dry_run={self.dry_run} is_paper={self.is_paper}>")

"""Immutable data contracts for Paper Trading (v1.0.0).

All monetary values are stored in USD (single-currency v1.0). Prices carry
the symbol's native currency but PnL is always computed in the account's
currency — currency conversion is out-of-scope for v1.0.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class PaperAccount:
    """Single-user paper account. v1.0 uses one account per install."""
    account_id: str = field(default_factory=lambda: _new_id("acc"))
    name: str = "Atlas Paper Account"
    currency: str = "USD"
    starting_balance: float = 100_000.0
    cash: float = 100_000.0            # available cash
    realized_pnl: float = 0.0          # cumulative closed-trade PnL
    fees_bps_per_side: float = 5.0     # 5 basis points per side
    slippage_bps: float = 2.0          # 2 bps of adverse slippage on fills
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PaperPosition:
    """Open paper position. Persisted while status='open'; when closed we
    move the record into `paper_trades` and delete from `paper_positions`.
    """
    position_id: str = field(default_factory=lambda: _new_id("pos"))
    account_id: str = ""
    symbol: str = ""
    provider: str = "synthetic"
    interval: str = "1d"
    side: str = "long"                 # 'long' | 'short'
    quantity: float = 0.0              # units of the underlying
    notional_at_entry: float = 0.0     # quantity * entry_price
    entry_price: float = 0.0           # fill price (after slippage)
    reference_price: float = 0.0       # last price at time-of-open (pre-slip)
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    fees_paid: float = 0.0             # entry fees only; exit fees on close
    size_pct: float = 10.0             # % of equity requested
    status: str = "open"               # 'open' | 'closed'
    opened_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)
    last_mark_price: Optional[float] = None
    last_mark_at: Optional[str] = None
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    # Atlas snapshot — captured at open, immutable.
    atlas_snapshot: Dict[str, Any] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PaperTrade:
    """Closed paper trade. Immutable audit record."""
    trade_id: str = field(default_factory=lambda: _new_id("trd"))
    position_id: str = ""
    account_id: str = ""
    symbol: str = ""
    provider: str = "synthetic"
    interval: str = "1d"
    side: str = "long"
    quantity: float = 0.0
    entry_price: float = 0.0
    exit_price: float = 0.0
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    fees_paid: float = 0.0                # entry + exit combined
    slippage_cost: float = 0.0
    realized_pnl: float = 0.0             # net of fees + slippage
    realized_pnl_pct: float = 0.0         # vs notional_at_entry
    r_multiple: Optional[float] = None    # PnL / initial-risk
    exit_reason: str = "manual"           # 'manual' | 'take_profit' | 'stop_loss'
    opened_at: str = ""
    closed_at: str = field(default_factory=_utcnow)
    holding_seconds: float = 0.0
    bars_held: Optional[int] = None
    atlas_snapshot: Dict[str, Any] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OpenPositionRequest:
    account_id: str
    provider: str
    symbol: str
    interval: str
    side: str                # 'long' | 'short'
    size_pct: float          # % of current equity to deploy
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    reference_price: Optional[float] = None    # snapshot price at open time
    atlas_snapshot: Optional[Dict[str, Any]] = None
    note: str = ""


@dataclass
class ClosePositionRequest:
    exit_price: Optional[float] = None   # if None, uses latest close
    exit_reason: str = "manual"
    note: str = ""

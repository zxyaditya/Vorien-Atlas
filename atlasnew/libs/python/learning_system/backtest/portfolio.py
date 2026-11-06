"""Portfolio bookkeeping. Cash + open position + closed trades."""
from __future__ import annotations
from typing import List, Optional


class Portfolio:
    def __init__(self, initial_cash: float = 100_000.0):
        self.initial_cash = float(initial_cash)
        self.cash: float = float(initial_cash)
        self.open_trade: Optional[dict] = None
        self.closed_trades: List[dict] = []

    def has_open_position(self) -> bool:
        return self.open_trade is not None

    def as_dict(self) -> dict:
        return {
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "open_trade": self.open_trade,
            "n_closed": len(self.closed_trades),
        }

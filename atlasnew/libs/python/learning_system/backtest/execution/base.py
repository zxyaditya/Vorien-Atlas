"""ExecutionEngine abstract interface.

The SAME methods are called by the backtest engine, a paper broker, and
a future live broker. Whatever changes underneath, the strategy code
above does not.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


class ExecutionEngine(ABC):
    """Every concrete implementation must satisfy this exact contract."""

    @abstractmethod
    def open_position(self, direction: int, size: float, price: float,
                       timestamp: str, reason: str = "") -> dict:
        """Open a position. direction ∈ {-1, +1}; size in units.

        Returns a trade-open receipt with fees & effective fill price
        (which may differ from `price` due to slippage).
        """

    @abstractmethod
    def close_position(self, price: float, timestamp: str,
                        reason: str = "") -> dict:
        """Close the currently open position. Returns realised trade dict."""

    @abstractmethod
    def mark_to_market(self, price: float, timestamp: str) -> dict:
        """Mark the current position to `price` at `timestamp`.

        Returns {equity, cash, exposure, open_position}.
        """

    @abstractmethod
    def has_open_position(self) -> bool: ...

    @abstractmethod
    def position_direction(self) -> int:
        """-1, 0, or +1."""

    @abstractmethod
    def snapshot(self) -> dict:
        """Portfolio snapshot: {equity, cash, exposure, ...}."""

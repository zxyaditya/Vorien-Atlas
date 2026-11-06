from __future__ import annotations
from typing import Optional


class FuturesPortfolio:
    """Tracks paper portfolio state for perpetual swap trading.
    
    Only supports ONE open position at a time (max_open_positions = 1).
    All accounting is in USD.
    """

    def __init__(self, initial_cash: float = 10_000.0, leverage: float = 5.0):
        self.initial_cash = initial_cash
        self.leverage     = leverage
        self.cash         = initial_cash

        # Open position state
        self.position_direction: int   = 0     # +1 LONG, -1 SHORT, 0 flat
        self.position_size_usd: float  = 0.0   # Notional USD
        self.entry_price: float        = 0.0
        self.bars_held: int            = 0

        # Running history
        self.realized_pnl: float       = 0.0
        self.n_wins: int               = 0
        self.n_losses: int             = 0

    @property
    def is_open(self) -> bool:
        return self.position_direction != 0

    @property
    def margin_used(self) -> float:
        """Cash locked as margin for the open position."""
        return self.position_size_usd / self.leverage if self.is_open else 0.0

    @property
    def free_cash(self) -> float:
        return self.cash - self.margin_used

    def equity(self, current_price: float) -> float:
        """Mark-to-market equity = cash + unrealized PnL."""
        return self.cash + self.unrealized_pnl(current_price)

    def unrealized_pnl(self, current_price: float) -> float:
        if not self.is_open or self.entry_price == 0:
            return 0.0
        ret = self.position_direction * (current_price - self.entry_price) / self.entry_price
        return ret * self.position_size_usd

    def liquidation_price(self) -> float:
        """Approximate liquidation price (simplified: 1/leverage move against)."""
        if not self.is_open:
            return 0.0
        liq_ret = -1.0 / self.leverage
        return self.entry_price * (1.0 + self.position_direction * liq_ret)

    def open_position(self, direction: int, current_price: float,
                      size_pct: float = 0.20) -> dict:
        """Open a new position.
        
        Args:
            direction: +1 LONG, -1 SHORT
            current_price: Entry price
            size_pct: Fraction of equity to risk (margin used)
        """
        if self.is_open:
            return {}

        eq = self.equity(current_price)
        margin = eq * size_pct
        if margin > self.free_cash:
            margin = self.free_cash * 0.95  # never use exactly all cash

        notional = margin * self.leverage

        self.position_direction = direction
        self.position_size_usd  = notional
        self.entry_price        = current_price
        self.bars_held          = 0

        return {
            "action": "OPEN",
            "direction": direction,
            "size_usd": notional,
            "price": current_price,
            "margin": margin,
        }

    def close_position(self, current_price: float, reason: str = "") -> dict:
        """Close the open position and settle PnL."""
        if not self.is_open:
            return {}

        pnl = self.unrealized_pnl(current_price)
        ret_pct = self.position_direction * (current_price - self.entry_price) / self.entry_price

        # Simple fee: 0.04% per side (Binance maker/taker)
        fee = self.position_size_usd * 0.0004 * 2
        net_pnl = pnl - fee

        self.realized_pnl += net_pnl
        self.cash += net_pnl  # settle into cash

        if net_pnl > 0:
            self.n_wins += 1
        else:
            self.n_losses += 1

        result = {
            "action": "CLOSE",
            "direction": self.position_direction,
            "size_usd": self.position_size_usd,
            "entry_price": self.entry_price,
            "close_price": current_price,
            "pnl": net_pnl,
            "return_pct": ret_pct,
            "reason": reason,
            "bars_held": self.bars_held,
        }

        # Reset
        self.position_direction = 0
        self.position_size_usd  = 0.0
        self.entry_price        = 0.0
        self.bars_held          = 0

        return result

    def tick(self):
        """Called once per bar to increment bars_held."""
        if self.is_open:
            self.bars_held += 1

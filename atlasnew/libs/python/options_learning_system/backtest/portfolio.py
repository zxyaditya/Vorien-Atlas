"""Options Portfolio State.

Tracks open positions and aggregate Greeks limits.
"""
from __future__ import annotations
from typing import Dict, List, Optional
from options_learning_system.backtest.contracts import OptionsTrade, OptionsStrategyPolicy


class OptionsPortfolio:
    def __init__(self, initial_cash: float, policy: OptionsStrategyPolicy):
        self.cash = initial_cash
        self.policy = policy
        self.open_positions: Dict[str, OptionsTrade] = {}
        
        # Aggregate Greeks
        self.net_delta = 0.0
        self.net_gamma = 0.0
        self.net_theta = 0.0
        self.net_vega = 0.0

    def add_position(self, trade: OptionsTrade) -> None:
        """Add a new open position and deduct cash (premium + fees)."""
        self.open_positions[trade.trade_id] = trade
        
        # direction: 1 (buy), -1 (sell)
        # premium flow: buying means cash goes down, selling means cash goes up
        premium_flow = trade.size * trade.open_price * trade.direction * -1
        self.cash += premium_flow - trade.fee_paid
        self.update_greeks()

    def remove_position(self, trade_id: str, close_price: float, fee_paid: float,
                        close_reason: str, close_time: str) -> OptionsTrade:
        """Close an open position, realize PnL, update cash."""
        if trade_id not in self.open_positions:
            raise KeyError(f"Trade {trade_id} not in portfolio.")
            
        trade = self.open_positions.pop(trade_id)
        trade.close_time = close_time
        trade.close_price = close_price
        trade.close_reason = close_reason
        trade.fee_paid += fee_paid
        
        # premium flow: closing a long means selling (receive cash)
        premium_flow = trade.size * close_price * trade.direction
        self.cash += premium_flow - fee_paid
        
        # Calculate realized PnL
        if trade.direction == 1:
            trade.pnl = (close_price - trade.open_price) * trade.size - trade.fee_paid
            trade.return_pct = (close_price - trade.open_price) / (trade.open_price + 1e-6)
        else:
            trade.pnl = (trade.open_price - close_price) * trade.size - trade.fee_paid
            trade.return_pct = (trade.open_price - close_price) / (trade.open_price + 1e-6)
            
        self.update_greeks()
        return trade

    def get_position(self, trade_id: str) -> Optional[OptionsTrade]:
        return self.open_positions.get(trade_id)

    def update_greeks(self) -> None:
        """Recompute aggregate net Greeks."""
        net_d = net_g = net_t = net_v = 0.0
        for trade in self.open_positions.values():
            greeks = trade.greeks_at_open
            sign = trade.direction
            size = trade.size
            net_d += greeks.get("delta", 0.0) * sign * size
            net_g += greeks.get("gamma", 0.0) * sign * size
            net_t += greeks.get("theta", 0.0) * sign * size
            net_v += greeks.get("vega", 0.0) * sign * size
            
        self.net_delta = net_d
        self.net_gamma = net_g
        self.net_theta = net_t
        self.net_vega = net_v

    def total_equity(self) -> float:
        """Cash + Net Liquidation Value of open positions."""
        nlv = 0.0
        for trade in self.open_positions.values():
            nlv += trade.size * trade.open_price * trade.direction
        return self.cash + nlv

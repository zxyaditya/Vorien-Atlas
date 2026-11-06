from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FuturesStrategyPolicy:
    """Decision parameters for the Futures Strategy."""
    upper_threshold: float = 0.58          # P(UP) above this → consider LONG
    lower_threshold: float = 0.42          # P(UP) below this → consider SHORT
    vpin_gate: float = 0.70                # Reject entry if VPIN exceeds this (toxic flow)
    vpin_exit_gate: float = 0.85           # Force exit if VPIN spikes above this while in trade
    hurst_trend_threshold: float = 0.55    # H > 0.55 → trending regime, allow trend-following
    mean_rev_score_threshold: float = 0.5  # Mean reversion score threshold for ranging regime
    stop_loss_pct: float = 0.015           # 1.5% stop loss (of position value)
    take_profit_pct: float = 0.030         # 3.0% take profit (of position value)
    atr_stop_multiplier: float = 2.0       # Dynamic stop = atr_stop_multiplier × ATR_pct
    max_leverage: float = 5.0              # Maximum allowed leverage
    position_size_pct: float = 0.20        # Risk 20% of equity per trade
    cooldown_bars: int = 3                 # Bars to wait after close before re-entry
    time_stop_bars: int = 50              # Force close if trade held this many bars
    risk_score_gate: float = 5.0          # Reject entry if regime.risk_score exceeds this


@dataclass
class FuturesTrade:
    """A complete futures paper trade (open → close)."""
    trade_id: str
    symbol: str
    direction: int                        # +1 = LONG, -1 = SHORT
    open_time: str
    open_price: float
    size_usd: float                       # Notional value in USD
    leverage: float
    close_time: Optional[str] = None
    close_price: Optional[float] = None
    close_reason: str = ""
    pnl: float = 0.0
    return_pct: float = 0.0
    bars_held: int = 0
    # Context at entry
    prob_up_at_open: float = 0.0
    vpin_at_open: float = 0.0
    hurst_at_open: float = 0.0


@dataclass
class FuturesEquityPoint:
    """Portfolio snapshot at each bar."""
    time: str
    equity: float
    cash: float
    unrealized_pnl: float
    n_open_positions: int
    price: float


@dataclass
class FuturesBacktestResult:
    """Full result of a futures backtest run."""
    n_bars: int
    trades: list
    equity_curve: list
    metrics: dict
    duration_seconds: float
    status: str = "ok"
    error: Optional[str] = None

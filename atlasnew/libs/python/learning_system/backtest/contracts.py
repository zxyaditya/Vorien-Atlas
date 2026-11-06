"""Backtest contracts. JSON-safe dataclasses."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class StrategyPolicy:
    upper_threshold: float = 0.51        # p_up above this  → LONG
    lower_threshold: float = 0.49        # p_up below this  → SHORT
    allow_short: bool = True
    position_size_pct: float = 30.0      # % of equity per open (increased for Kelly scaling headroom)
    max_leverage: float = 2.0            # hard cap on |exposure| / equity
    stop_atr_mult: float = 0.0           # 0 = disabled
    take_profit_atr_mult: float = 0.0    # 0 = disabled
    stop_loss_pct: float = 0.0           # 0 = disabled, fixed % stop loss
    take_profit_pct: float = 0.0         # 0 = disabled, fixed % take profit
    cool_down_bars: int = 1              # bars to wait after a close
    dynamic_exits: bool = True           # Use L3 microstructure exits
    dynamic_sizing: bool = True          # Use L4 confidence z-score sizing
    fractional_kelly: float = 0.5        # Kelly multiplier to enforce Half-Kelly or similar
    trailing_stop_atr_mult: float = 0.0  # 0 = disabled, trails the highest high / lowest low
    entropy_threshold: float = 99.0        # disabled by default (max allowed L4 entropy)
    agreement_threshold: float = 0.0       # disabled by default (min allowed L3 agreement)


@dataclass(frozen=True)
class BacktestSpec:
    model_id: str                        # persisted model to consume
    provider: str = "synthetic"
    symbol: str = "SYN-EQUITY"
    interval: str = "1d"
    period: str = "5y"
    peer_provider: Optional[str] = None
    peer_symbol: Optional[str] = None
    warmup_bars: int = 250               # rows skipped before trading
    initial_cash: float = 100_000.0
    fee_bps: float = 5.0                 # 5 bps per side (round-trip = 10)
    slippage_bps: float = 5.0            # symmetric slippage per fill
    policy: StrategyPolicy = field(default_factory=StrategyPolicy)
    execution_mode: str = "paper"        # "paper" | "live" (live raises)
    hold_bars: int = 0                   # 0 = use strategy exits; >0 = fixed-horizon exit after N bars
    regime_gate: bool = True             # L3/L4 regime gating (only trade in trending coherent states)


@dataclass
class Trade:
    trade_id: str
    direction: int                       # +1 LONG, -1 SHORT
    open_time: str
    open_price: float
    close_time: Optional[str]
    close_price: Optional[float]
    size: float                          # shares / units
    fee_paid: float
    pnl: float                           # realised, after fees + slippage
    return_pct: float                    # realised return on the notional
    open_reason: str
    close_reason: str


@dataclass
class EquityPoint:
    time: str
    equity: float
    cash: float
    exposure: float                      # signed notional of open position
    open_position: int                   # -1 / 0 / +1
    price: float


@dataclass
class BacktestResult:
    backtest_id: str
    spec: BacktestSpec
    n_bars_evaluated: int
    trades: List[Trade]
    equity_curve: List[EquityPoint]
    metrics: Dict[str, float]
    duration_seconds: float
    created_at: str
    execution_mode: str
    status: str = "ok"
    error: Optional[str] = None

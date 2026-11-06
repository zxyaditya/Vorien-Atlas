"""Options Backtest Contracts — data classes for the options execution engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OptionsStrategyPolicy:
    """ML model + Greeks → Action decision parameters."""
    upper_threshold: float = 0.55        # p_up above → BUY_CALL / SELL_PUT
    lower_threshold: float = 0.45        # p_up below → BUY_PUT / SELL_CALL
    vol_expand_threshold: float = 0.55   # p_vol_expand above → prefer long vega
    vol_crush_threshold: float = 0.45    # p_vol_expand below → prefer short vega
    dynamic_thresholds: bool = True      # scale probability thresholds based on regime
    atr_trailing_stop_multiplier: float = 2.0  # trail stop by ATR multiples
    volatility_regime_scaling: bool = True     # scale position size by VIX/ATR
    allow_short: bool = True             # allow selling options (short premium)
    max_contracts: int = 5              # max open positions simultaneously
    min_dte: int = 7                    # reject options with < 7 DTE
    max_dte: int = 60                   # reject options with > 60 DTE
    min_moneyness: float = 0.92         # reject if spot/strike < 0.92 (too deep ITM)
    max_moneyness: float = 1.08         # reject if spot/strike > 1.08 (too deep OTM)
    max_spread_pct: float = 0.15        # reject if bid/ask spread > 15%
    position_size_usd: float = 5_000.0  # notional per trade in USD
    cool_down_bars: int = 2             # bars to wait after close before re-entry
    max_delta_exposure: float = 3.0     # absolute cap on portfolio net delta
    max_vega_exposure: float = 500.0    # absolute cap on portfolio net vega
    stop_loss_pct: float = 0.50         # close if position loses > 50% of premium paid
    take_profit_pct: float = 1.00       # close if position gains > 100% of premium paid


@dataclass(frozen=True)
class OptionsBacktestSpec:
    """Full specification for an options backtest run."""
    model_id: str
    underlying: str = "ETH"
    period: str = "1y"
    initial_cash: float = 100_000.0
    fee_per_contract: float = 2.0        # USD per contract per side
    r: float = 0.0                       # risk-free rate
    policy: OptionsStrategyPolicy = field(default_factory=OptionsStrategyPolicy)
    warmup_bars: int = 100
    front_dte_max: int = 45              # front-month definition


@dataclass
class OptionsTrade:
    """A completed options trade (open + close)."""
    trade_id: str
    instrument_name: str
    underlying: str
    option_type: str                    # "call" or "put"
    direction: int                      # +1 = buy, -1 = sell
    strike: float
    expiry: str
    dte_at_open: int
    open_time: str
    open_price: float                   # premium paid/received per contract
    open_spot: float                    # underlying spot at open
    open_iv: float                      # IV at open
    close_time: Optional[str] = None
    close_price: Optional[float] = None
    close_reason: str = ""              # "model_exit", "stop_loss", "take_profit",
                                        # "expiry_itm", "expiry_otm", "gamma_flip"
    size: float = 0.0                   # number of contracts
    fee_paid: float = 0.0
    pnl: float = 0.0                    # realised PnL after fees
    return_pct: float = 0.0
    greeks_at_open: Dict[str, float] = field(default_factory=dict)
    greeks_at_close: Dict[str, float] = field(default_factory=dict)
    # PnL attribution
    delta_pnl: float = 0.0
    gamma_pnl: float = 0.0
    theta_pnl: float = 0.0
    vega_pnl: float = 0.0


@dataclass
class OptionsEquityPoint:
    """Portfolio mark-to-market snapshot at each bar."""
    time: str
    equity: float
    cash: float
    n_open_positions: int
    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    spot: float


@dataclass
class OptionsBacktestResult:
    """Complete result of an options backtest run."""
    backtest_id: str
    spec: OptionsBacktestSpec
    n_bars_evaluated: int
    trades: List[OptionsTrade]
    equity_curve: List[OptionsEquityPoint]
    metrics: Dict[str, float]
    duration_seconds: float
    created_at: str
    status: str = "ok"
    error: Optional[str] = None

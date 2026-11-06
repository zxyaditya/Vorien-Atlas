"""Walk-forward Backtesting Framework (L5, inside learning_system/).

Measures any Learning-System configuration on out-of-sample data.

Key design principle: **the ExecutionEngine interface is the same for
paper backtest and future live trading.** Swap the concrete engine and
nothing else changes; a strategy written today for `PaperExecutionEngine`
will run tomorrow against `LiveExecutionEngine` without modification.
"""
from __future__ import annotations
from learning_system.backtest.contracts import (  # noqa: F401
    BacktestSpec, StrategyPolicy, Trade, EquityPoint, BacktestResult,
)
from learning_system.backtest.execution.base import ExecutionEngine  # noqa: F401
from learning_system.backtest.execution.paper import PaperExecutionEngine  # noqa: F401
from learning_system.backtest.portfolio import Portfolio  # noqa: F401
from learning_system.backtest.strategy import Strategy  # noqa: F401
from learning_system.backtest.engine import BacktestEngine  # noqa: F401
from learning_system.backtest.metrics import compute_backtest_metrics  # noqa: F401
from learning_system.backtest.execution.live import LiveExecutionEngine  # noqa: F401
from learning_system.backtest.broker import (  # noqa: F401
    BrokerAdapter, BrokerOrder, BrokerPosition, BrokerAccount,
    BrokerError, SimulatedBrokerAdapter,
)

"""Broker adapters — the thin translation layer between an
ExecutionEngine call (open_position / close_position / mark_to_market)
and a concrete broker's REST/WS API.

DEC-020 (Session 13). Adding a new broker means implementing the
abstract `BrokerAdapter` interface. Every existing strategy runs
against the new broker without a single change, because the
`LiveExecutionEngine` sits between the strategy and the adapter and
speaks ExecutionEngine on one side and BrokerAdapter on the other.

No real broker credentials live here. Concrete broker adapters (Alpaca,
Interactive Brokers, Binance, ...) will be added in a subsequent
session once approved.
"""
from learning_system.backtest.broker.base import (
    BrokerAdapter,
    BrokerOrder,
    BrokerPosition,
    BrokerAccount,
    BrokerError,
)
from learning_system.backtest.broker.simulated import SimulatedBrokerAdapter

__all__ = [
    "BrokerAdapter",
    "BrokerOrder",
    "BrokerPosition",
    "BrokerAccount",
    "BrokerError",
    "SimulatedBrokerAdapter",
]

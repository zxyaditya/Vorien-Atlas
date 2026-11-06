"""Options Backtest Metrics.

Calculates performance metrics from equity curve and trades.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Any
from options_learning_system.backtest.contracts import OptionsBacktestResult


def calculate_backtest_metrics(result: OptionsBacktestResult) -> Dict[str, Any]:
    if not result.equity_curve:
        return {}

    equity = pd.Series([e.equity for e in result.equity_curve],
                       index=pd.to_datetime([e.time for e in result.equity_curve]))
                       
    if len(equity) < 2:
        return {}

    returns = equity.pct_change().dropna()
    
    total_return = (equity.iloc[-1] / equity.iloc[0]) - 1.0
    
    # Assuming 1h bars for annualization
    annualized_return = (1 + total_return) ** (252 * 24 / len(equity)) - 1.0
    
    vol = returns.std() * np.sqrt(252 * 24)
    sharpe = (annualized_return - result.spec.r) / vol if vol > 0 else 0.0
    
    downside_returns = returns[returns < 0]
    downside_vol = downside_returns.std() * np.sqrt(252 * 24)
    sortino = (annualized_return - result.spec.r) / downside_vol if downside_vol > 0 else 0.0

    cum_max = equity.cummax()
    drawdown = (equity - cum_max) / cum_max
    max_drawdown = drawdown.min()

    win_rate = 0.0
    total_trades = len(result.trades)
    if total_trades > 0:
        winning_trades = [t for t in result.trades if t.pnl > 0]
        win_rate = len(winning_trades) / total_trades

    metrics = {
        "total_return_pct": total_return * 100,
        "annualized_return_pct": annualized_return * 100,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown_pct": max_drawdown * 100,
        "win_rate_pct": win_rate * 100,
        "total_trades": total_trades,
    }
    
    result.metrics = metrics
    return metrics

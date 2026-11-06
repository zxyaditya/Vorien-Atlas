import numpy as np
import pandas as pd
from typing import List


def compute_metrics(trades: list, equity_curve: list, initial_cash: float = 10_000.0) -> dict:
    """Compute a comprehensive set of performance metrics.
    
    Args:
        trades: List of trade result dicts from FuturesPortfolio.close_position()
        equity_curve: List of FuturesEquityPoint dataclasses
        initial_cash: Starting capital
        
    Returns:
        dict of labelled metrics
    """
    if not equity_curve:
        return {}

    equities = np.array([p.equity for p in equity_curve])
    returns  = np.diff(equities) / equities[:-1]

    # ── Basic ────────────────────────────────────────────────────────────
    final_equity = equities[-1]
    total_return = (final_equity - initial_cash) / initial_cash

    n_trades = len(trades)
    if n_trades == 0:
        return {"total_return": total_return, "n_trades": 0}

    pnls     = np.array([t["pnl"] for t in trades])
    rets     = np.array([t["return_pct"] for t in trades])

    wins     = pnls[pnls > 0]
    losses   = pnls[pnls <= 0]

    win_rate = len(wins) / n_trades if n_trades > 0 else 0.0
    avg_win  = float(wins.mean()) if len(wins) > 0 else 0.0
    avg_loss = float(losses.mean()) if len(losses) > 0 else 0.0

    profit_factor = (wins.sum() / abs(losses.sum())) if losses.sum() != 0 else float("inf")
    expectancy    = win_rate * avg_win + (1 - win_rate) * avg_loss

    # ── Risk-adjusted ratios ─────────────────────────────────────────────
    bars_per_year = 365 * 24 * 12   # 5-min bars per year
    ann_factor    = np.sqrt(bars_per_year)

    sharpe   = (returns.mean() / returns.std()) * ann_factor if returns.std() > 0 else 0.0

    downside = returns[returns < 0]
    sortino  = (returns.mean() / downside.std()) * ann_factor if len(downside) > 0 and downside.std() > 0 else 0.0

    # ── Drawdown ─────────────────────────────────────────────────────────
    running_max = np.maximum.accumulate(equities)
    drawdowns   = (equities - running_max) / running_max
    max_dd      = float(drawdowns.min())

    calmar = (total_return / abs(max_dd)) if max_dd != 0 else 0.0

    # ── Trade duration ───────────────────────────────────────────────────
    bars_held = [t.get("bars_held", 0) for t in trades]
    avg_bars_held = float(np.mean(bars_held)) if bars_held else 0.0

    return {
        "total_return_pct":   round(total_return * 100, 2),
        "final_equity":       round(final_equity, 2),
        "n_trades":           n_trades,
        "win_rate":           round(win_rate * 100, 2),
        "profit_factor":      round(profit_factor, 3),
        "expectancy_usd":     round(expectancy, 2),
        "avg_win_usd":        round(avg_win, 2),
        "avg_loss_usd":       round(avg_loss, 2),
        "sharpe_ratio":       round(sharpe, 3),
        "sortino_ratio":      round(sortino, 3),
        "max_drawdown_pct":   round(max_dd * 100, 2),
        "calmar_ratio":       round(calmar, 3),
        "avg_bars_held":      round(avg_bars_held, 1),
    }

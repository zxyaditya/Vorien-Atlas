"""Backtest metrics. All finite floats."""
from __future__ import annotations
import math
from typing import Dict, List

import numpy as np


def _safe(v: float) -> float:
    v = float(v)
    return v if math.isfinite(v) else 0.0


def compute_backtest_metrics(equity_curve: List[dict],
                              trades: List[dict],
                              bars_per_year: int = 252) -> Dict[str, float]:
    if len(equity_curve) < 2:
        return {"total_return_pct": 0.0, "n_trades": len(trades)}
    eq = np.array([p["equity"] for p in equity_curve], dtype=float)
    rets = np.diff(eq) / np.maximum(eq[:-1], 1e-9)
    total_return = (eq[-1] / eq[0] - 1.0) * 100.0
    mean_r = float(rets.mean()) if len(rets) else 0.0
    std_r = float(rets.std(ddof=0)) if len(rets) else 0.0
    downside = rets[rets < 0]
    ds_std = float(downside.std(ddof=0)) if len(downside) else 0.0
    sharpe = ((mean_r / std_r) * math.sqrt(bars_per_year)
               if std_r > 0 else 0.0)
    sortino = ((mean_r / ds_std) * math.sqrt(bars_per_year)
                if ds_std > 0 else 0.0)
    # Max drawdown
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / np.maximum(peak, 1e-9)
    max_dd = float(dd.min()) * 100.0
    # Calmar (annualised return / max_dd)
    ann_return = ((eq[-1] / eq[0]) ** (bars_per_year / max(1, len(eq))) - 1.0) * 100.0
    calmar = (ann_return / abs(max_dd)) if max_dd != 0 else 0.0
    # Trade metrics
    pnls = [float(t.get("pnl", 0.0)) for t in trades]
    n_win = sum(1 for p in pnls if p > 0)
    n_loss = sum(1 for p in pnls if p < 0)
    hit_rate = n_win / len(pnls) if pnls else 0.0
    avg_win = np.mean([p for p in pnls if p > 0]) if n_win else 0.0
    avg_loss = np.mean([p for p in pnls if p < 0]) if n_loss else 0.0
    total_win = sum(p for p in pnls if p > 0)
    total_loss = abs(sum(p for p in pnls if p < 0))
    profit_factor = (total_win / total_loss) if total_loss > 0 else 0.0
    return {k: round(_safe(v), 6) for k, v in {
        "total_return_pct": total_return,
        "annualised_return_pct": ann_return,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown_pct": max_dd,
        "calmar": calmar,
        "n_trades": float(len(trades)),
        "hit_rate": hit_rate,
        "avg_win_pnl": float(avg_win),
        "avg_loss_pnl": float(avg_loss),
        "profit_factor": profit_factor,
        "final_equity": float(eq[-1]),
    }.items()}

"""Performance analytics for a paper account.

All computations are deterministic and read-only. No Atlas Core imports.
"""
from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone
import math


def _iso_to_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _safe(x: float, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def build_equity_curve(starting_balance: float,
                        trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build [{'time','equity','realized_pnl'}] by closed-trade timestamp."""
    trades = sorted(
        [t for t in trades if t.get("closed_at")],
        key=lambda t: t["closed_at"],
    )
    equity = float(starting_balance)
    curve = [{"time": trades[0]["opened_at"] if trades else datetime.now(timezone.utc).isoformat(),
              "equity": equity,
              "realized_pnl": 0.0}]
    total = 0.0
    for t in trades:
        pnl = _safe(t.get("realized_pnl"))
        equity += pnl
        total += pnl
        curve.append({"time": t["closed_at"], "equity": round(equity, 2),
                      "realized_pnl": round(total, 2)})
    return curve


def compute_metrics(starting_balance: float,
                    trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Full metric block. Returns finite floats or None (never NaN)."""
    n = len(trades)
    if n == 0:
        return {
            "n_trades": 0, "n_wins": 0, "n_losses": 0, "win_rate": None,
            "avg_win": None, "avg_loss": None, "avg_rr": None,
            "expectancy": None, "expectancy_pct": None, "profit_factor": None,
            "avg_holding_seconds": None, "avg_bars_held": None,
            "realized_pnl": 0.0, "realized_pnl_pct": 0.0,
            "max_drawdown": 0.0, "max_drawdown_pct": 0.0,
            "sharpe": None, "sortino": None, "calmar": None,
            "largest_win": None, "largest_loss": None,
            "total_fees": 0.0,
        }

    pnls = [_safe(t.get("realized_pnl")) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    n_wins, n_losses = len(wins), len(losses)
    total_pnl = sum(pnls)
    fees = sum(_safe(t.get("fees_paid")) for t in trades)

    curve = build_equity_curve(starting_balance, trades)
    equities = [c["equity"] for c in curve]
    peak = equities[0]
    max_dd = 0.0
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
    max_dd_pct = 100.0 * max_dd / peak if peak > 0 else 0.0

    # Trade-level Sharpe/Sortino on pct returns per trade
    pct_returns = [
        _safe(t.get("realized_pnl_pct")) / 100.0 for t in trades
    ]
    if len(pct_returns) >= 2:
        mean = sum(pct_returns) / len(pct_returns)
        var = sum((r - mean) ** 2 for r in pct_returns) / (len(pct_returns) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        neg = [r for r in pct_returns if r < 0]
        if neg:
            dvar = sum(r * r for r in neg) / len(neg)
            dstd = math.sqrt(dvar) if dvar > 0 else 0.0
        else:
            dstd = 0.0
        # Annualise assuming ~252 trades/yr equivalent; keep simple: sqrt(n)
        sharpe = (mean / std * math.sqrt(len(pct_returns))) if std > 0 else None
        sortino = (mean / dstd * math.sqrt(len(pct_returns))) if dstd > 0 else None
    else:
        sharpe = sortino = None

    # Calmar = total return / max DD (both as % of starting balance)
    total_ret_pct = 100.0 * total_pnl / starting_balance if starting_balance else 0.0
    calmar = (total_ret_pct / max_dd_pct) if max_dd_pct > 0 else None

    hold_seconds = [_safe(t.get("holding_seconds")) for t in trades
                     if t.get("holding_seconds") is not None]
    bars_held = [_safe(t.get("bars_held")) for t in trades
                  if t.get("bars_held") is not None]

    rrs = [_safe(t.get("r_multiple")) for t in trades
            if t.get("r_multiple") is not None]

    win_rate = n_wins / n
    avg_win = sum(wins) / n_wins if n_wins else None
    avg_loss = sum(losses) / n_losses if n_losses else None
    expectancy = total_pnl / n
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_win > 0 else None)

    def _rd(v, nd=2):
        return None if v is None else (None if not math.isfinite(v) else round(float(v), nd))

    return {
        "n_trades": n,
        "n_wins": n_wins,
        "n_losses": n_losses,
        "win_rate": _rd(win_rate, 4),
        "avg_win": _rd(avg_win, 2),
        "avg_loss": _rd(avg_loss, 2),
        "avg_rr": _rd(sum(rrs) / len(rrs), 3) if rrs else None,
        "expectancy": _rd(expectancy, 2),
        "expectancy_pct": _rd(100.0 * expectancy / starting_balance, 4) if starting_balance else None,
        "profit_factor": _rd(profit_factor, 3),
        "avg_holding_seconds": _rd(sum(hold_seconds) / len(hold_seconds), 1) if hold_seconds else None,
        "avg_bars_held": _rd(sum(bars_held) / len(bars_held), 1) if bars_held else None,
        "realized_pnl": _rd(total_pnl, 2),
        "realized_pnl_pct": _rd(total_ret_pct, 3),
        "max_drawdown": _rd(max_dd, 2),
        "max_drawdown_pct": _rd(max_dd_pct, 3),
        "sharpe": _rd(sharpe, 3),
        "sortino": _rd(sortino, 3),
        "calmar": _rd(calmar, 3),
        "largest_win": _rd(max(wins) if wins else None, 2),
        "largest_loss": _rd(min(losses) if losses else None, 2),
        "total_fees": _rd(fees, 2),
    }

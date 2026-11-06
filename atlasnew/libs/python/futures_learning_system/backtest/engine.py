from __future__ import annotations
import time
import logging
from dataclasses import dataclass
from typing import List

import pandas as pd

from futures_learning_system.backtest.contracts import (
    FuturesStrategyPolicy, FuturesTrade, FuturesEquityPoint, FuturesBacktestResult
)
from futures_learning_system.backtest.strategy  import FuturesStrategy, LONG, SHORT, HOLD
from futures_learning_system.backtest.portfolio import FuturesPortfolio
from futures_learning_system.backtest.metrics   import compute_metrics
from futures_learning_system.models.futures_xgb import FuturesXGBoostModel

logger = logging.getLogger("FuturesBacktestEngine")


class FuturesBacktestEngine:
    """Walks historical feature data bar-by-bar and simulates paper trading.
    
    Args:
        model: A trained FuturesXGBoostModel
        policy: FuturesStrategyPolicy parameters
        initial_cash: Starting paper capital in USD
        warmup_bars: Bars to skip at the start (model needs history)
    """

    def __init__(self,
                 model: FuturesXGBoostModel,
                 policy: FuturesStrategyPolicy = None,
                 initial_cash: float = 10_000.0,
                 warmup_bars: int = 120):
        self.model       = model
        self.strategy    = FuturesStrategy(policy or FuturesStrategyPolicy())
        self.portfolio   = FuturesPortfolio(initial_cash, leverage=policy.max_leverage if policy else 5.0)
        self.warmup_bars = warmup_bars

    def run(self, X: pd.DataFrame, ohlcv_df: pd.DataFrame) -> FuturesBacktestResult:
        """Run the full backtest.
        
        Args:
            X: Feature matrix, index = timestamps, rows = bars
            ohlcv_df: Raw OHLCV (used to get close price per bar)
        """
        t_start = time.time()

        trades: List[dict]          = []
        equity_curve: List[FuturesEquityPoint] = []

        cooldown_bars_remaining = 0
        trade_id_counter        = 0

        # Current open trade metadata (for tracking bars_held properly)
        open_trade_meta = None

        # Align ohlcv close to X index
        close_series = ohlcv_df["close"].reindex(X.index).ffill()

        for i, (ts, row) in enumerate(X.iterrows()):
            current_price = float(close_series.loc[ts])

            # Tick portfolio (increment bars_held)
            self.portfolio.tick()

            # Snapshot equity
            eq = self.portfolio.equity(current_price)
            eq_point = FuturesEquityPoint(
                time=str(ts),
                equity=eq,
                cash=self.portfolio.cash,
                unrealized_pnl=self.portfolio.unrealized_pnl(current_price),
                n_open_positions=1 if self.portfolio.is_open else 0,
                price=current_price,
            )
            equity_curve.append(eq_point)

            # Skip warmup
            if i < self.warmup_bars:
                continue

            context = row.to_dict()

            # ── Check exit ───────────────────────────────────────────────
            if self.portfolio.is_open:
                prob_up = float(self.model.predict_proba(X.iloc[[i]]).iloc[0])
                exit_reason = self.strategy.should_exit(
                    direction=self.portfolio.position_direction,
                    open_price=self.portfolio.entry_price,
                    current_price=current_price,
                    bars_held=self.portfolio.bars_held,
                    prob_up=prob_up,
                    context=context,
                )

                if exit_reason:
                    close_result = self.portfolio.close_position(current_price, exit_reason)
                    if close_result and open_trade_meta:
                        close_result.update(open_trade_meta)
                        trades.append(close_result)
                    open_trade_meta = None
                    cooldown_bars_remaining = self.strategy.policy.cooldown_bars

            # ── Check entry ──────────────────────────────────────────────
            if not self.portfolio.is_open and cooldown_bars_remaining <= 0:
                prob_up = float(self.model.predict_proba(X.iloc[[i]]).iloc[0])
                action = self.strategy.decide(prob_up, 0, context)

                if action in (LONG, SHORT):
                    direction = 1 if action == LONG else -1
                    open_result = self.portfolio.open_position(
                        direction, current_price,
                        size_pct=self.strategy.policy.position_size_pct
                    )
                    if open_result:
                        trade_id_counter += 1
                        open_trade_meta = {
                            "trade_id": f"trade_{trade_id_counter:04d}",
                            "prob_up_at_open": prob_up,
                            "vpin_at_open": context.get("flow.vpin_50", 0.5),
                            "hurst_at_open": context.get("info.hurst_exponent_50", 0.5),
                        }
                        logger.debug(f"Bar {i}: {action} @ {current_price:.2f}  P(UP)={prob_up:.3f}")

            if cooldown_bars_remaining > 0:
                cooldown_bars_remaining -= 1

        # ── Force-close any remaining position ───────────────────────────
        if self.portfolio.is_open and close_series.shape[0] > 0:
            final_price = float(close_series.iloc[-1])
            close_result = self.portfolio.close_position(final_price, "backtest_end")
            if close_result and open_trade_meta:
                close_result.update(open_trade_meta)
                trades.append(close_result)

        metrics = compute_metrics(trades, equity_curve, self.portfolio.initial_cash)

        logger.info("=" * 60)
        logger.info("Backtest Complete")
        for k, v in metrics.items():
            logger.info(f"  {k}: {v}")
        logger.info("=" * 60)

        return FuturesBacktestResult(
            n_bars=len(X),
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            duration_seconds=round(time.time() - t_start, 2),
        )

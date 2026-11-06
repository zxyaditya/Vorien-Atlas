from __future__ import annotations
import json
import os
import logging
import uuid
import numpy as np
from datetime import datetime, timezone
from typing import Optional

from futures_learning_system.backtest.strategy  import FuturesStrategy, LONG, SHORT, HOLD
from futures_learning_system.backtest.portfolio import FuturesPortfolio
from futures_learning_system.backtest.contracts import FuturesStrategyPolicy

logger = logging.getLogger("FuturesLivePaperEngine")

STATE_FILE = "futures_paper_state.json"


class FuturesLivePaperEngine:
    """Manages the live paper trading state, persisted to disk.
    
    On each call to process_tick(), it:
      1. Checks exit conditions for any open position
      2. Checks entry conditions for a new position  
      3. Saves portfolio state to JSON
      4. Returns an action dict for the broadcaster
    """

    def __init__(self,
                 policy: FuturesStrategyPolicy = None,
                 broadcaster=None,
                 symbol: str = "BTCUSDT",
                 initial_cash: float = 10_000.0):
        self.symbol      = symbol
        self.strategy    = FuturesStrategy(policy or FuturesStrategyPolicy())
        self.portfolio   = FuturesPortfolio(initial_cash, leverage=5.0)
        self.broadcaster = broadcaster

        self.cooldown_bars = 0
        self.trades = []
        self.equity_history = []
        self.open_trade_id: Optional[str] = None

        self._load_state()

    # ── Persistence ──────────────────────────────────────────────────────

    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    s = json.load(f)
                self.portfolio.cash              = s.get("cash", self.portfolio.initial_cash)
                self.portfolio.realized_pnl      = s.get("realized_pnl", 0.0)
                self.portfolio.n_wins            = s.get("n_wins", 0)
                self.portfolio.n_losses          = s.get("n_losses", 0)
                self.cooldown_bars               = s.get("cooldown_bars", 0)
                self.trades                      = s.get("trades", [])
                self.open_trade_id               = s.get("open_trade_id")
                self.equity_history              = s.get("equity_history", [])

                pos = s.get("open_position")
                if pos:
                    self.portfolio.position_direction = pos["direction"]
                    self.portfolio.position_size_usd  = pos["size_usd"]
                    self.portfolio.entry_price        = pos["entry_price"]
                    self.portfolio.bars_held          = pos.get("bars_held", 0)

                logger.info(f"State loaded: equity~${self.portfolio.cash:.2f}, "
                            f"pos={self.portfolio.position_direction}, "
                            f"n_trades={len(self.trades)}")
            except Exception as e:
                logger.warning(f"Could not load state file: {e}")

    def _save_state(self, current_price: float, inference: dict = None):
        current_eq = self.portfolio.equity(current_price)
        self.equity_history.append(current_eq)
        # Keep last 10,000 ticks max to avoid huge state file
        if len(self.equity_history) > 10000:
            self.equity_history = self.equity_history[-10000:]
            
        # Calculate MDD and Sharpe
        mdd, sharpe = 0.0, 0.0
        if len(self.equity_history) > 2:
            arr = np.array(self.equity_history)
            peaks = np.maximum.accumulate(arr)
            mdd = np.min((arr - peaks) / peaks) * 100
            rets = np.diff(arr) / arr[:-1]
            if np.std(rets) > 1e-8:
                sharpe = (np.mean(rets) / np.std(rets)) * np.sqrt(105120)

        # SL and TP calculation
        sl_price = 0.0
        tp_price = 0.0
        if self.portfolio.is_open:
            p = self.strategy.policy
            d = self.portfolio.position_direction
            entry = self.portfolio.entry_price
            
            # Using baseline dynamic stop loss calculation roughly matching strategy.py
            context = inference.get("context", {}) if inference else {}
            atr_pct = context.get("vol.atr_pct_14", 0.5)
            atr_baseline = max(0.1, atr_pct)
            dynamic_sl = min(0.10, max(p.stop_loss_pct, p.atr_stop_multiplier * atr_baseline / 100.0))
            
            sl_price = entry * (1.0 - (d * dynamic_sl))
            tp_price = entry * (1.0 + (d * p.take_profit_pct))

        telemetry = {}
        if inference:
            telemetry = {
                "prob_up": round(inference.get("prob_up", 0), 4),
                "vpin": round(inference.get("context", {}).get("flow.vpin_50", 0), 4),
                "hurst": round(inference.get("context", {}).get("info.hurst_exponent_50", 0), 4),
                "price": current_price
            }

        state = {
            "cash":         self.portfolio.cash,
            "realized_pnl": self.portfolio.realized_pnl,
            "n_wins":       self.portfolio.n_wins,
            "n_losses":     self.portfolio.n_losses,
            "cooldown_bars": self.cooldown_bars,
            "trades":       self.trades[-200:],   # keep last 200 only
            "open_trade_id": self.open_trade_id,
            "equity_history": self.equity_history,
            "metrics": {
                "mdd": round(mdd, 2),
                "sharpe": round(sharpe, 2)
            },
            "telemetry": telemetry,
            "equity_snapshot": {
                "equity":         round(current_eq, 2),
                "unrealized_pnl": round(self.portfolio.unrealized_pnl(current_price), 2),
            },
            "open_position": {
                "direction":  self.portfolio.position_direction,
                "size_usd":   self.portfolio.position_size_usd,
                "entry_price": self.portfolio.entry_price,
                "bars_held":  self.portfolio.bars_held,
                "sl_price":   round(sl_price, 2),
                "tp_price":   round(tp_price, 2)
            } if self.portfolio.is_open else None,
        }
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    # ── Main tick ────────────────────────────────────────────────────────

    def process_tick(self, inference: dict) -> dict:
        """Process one inference cycle and decide on a trade action."""
        if not inference:
            return {}

        prob_up       = inference["prob_up"]
        current_price = inference["price"]
        timestamp     = str(inference["timestamp"])
        context       = inference.get("context", {})

        self.portfolio.tick()

        action_taken = HOLD
        trade_event  = {}

        # ── Check exit ───────────────────────────────────────────────────
        if self.portfolio.is_open:
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
                
                # Recalculate SL/TP to log them in history
                p = self.strategy.policy
                d = close_result["direction"]
                entry = close_result["entry_price"]
                atr_pct = context.get("vol.atr_pct_14", 0.5)
                atr_baseline = max(0.1, atr_pct)
                dynamic_sl = min(0.10, max(p.stop_loss_pct, p.atr_stop_multiplier * atr_baseline / 100.0))
                sl_price = entry * (1.0 - (d * dynamic_sl))
                tp_price = entry * (1.0 + (d * p.take_profit_pct))

                trade_event = {
                    "event": "CLOSE",
                    "trade_id": self.open_trade_id,
                    "symbol": self.symbol,
                    "direction": "LONG" if d == 1 else "SHORT",
                    "entry_price": entry,
                    "close_price": current_price,
                    "size_usd": close_result["size_usd"],
                    "leverage": self.portfolio.leverage,
                    "sl_price": round(sl_price, 2),
                    "tp_price": round(tp_price, 2),
                    "pnl_usd": round(close_result["pnl"], 2),
                    "return_pct": round(close_result["return_pct"] * 100, 3),
                    "reason": exit_reason,
                    "bars_held": close_result["bars_held"],
                    "timestamp": timestamp,
                }
                self.trades.append(trade_event)
                self.open_trade_id = None
                self.cooldown_bars = self.strategy.policy.cooldown_bars
                action_taken = "CLOSE"

                logger.info(
                    f"[CLOSE] {trade_event['direction']} @ ${current_price:,.2f} | "
                    f"PnL=${trade_event['pnl_usd']:+.2f} ({trade_event['return_pct']:+.3f}%) | "
                    f"{exit_reason}"
                )

        # ── Check entry ──────────────────────────────────────────────────
        if not self.portfolio.is_open and self.cooldown_bars <= 0:
            action = self.strategy.decide(prob_up, 0, context)

            if action in (LONG, SHORT):
                direction = 1 if action == LONG else -1
                open_result = self.portfolio.open_position(
                    direction, current_price,
                    size_pct=self.strategy.policy.position_size_pct
                )
                if open_result:
                    self.open_trade_id = str(uuid.uuid4())[:8]
                    trade_event = {
                        "event": "OPEN",
                        "trade_id": self.open_trade_id,
                        "symbol": self.symbol,
                        "direction": action,
                        "entry_price": current_price,
                        "size_usd": round(open_result["size_usd"], 2),
                        "prob_up": round(prob_up, 4),
                        "vpin": round(context.get("flow.vpin_50", 0.5), 4),
                        "hurst": round(context.get("info.hurst_exponent_50", 0.5), 4),
                        "timestamp": timestamp,
                    }
                    action_taken = action
                    logger.info(
                        f"[OPEN] {action} @ ${current_price:,.2f} | "
                        f"Size=${open_result['size_usd']:,.0f} | "
                        f"P(UP)={prob_up:.3f} | VPIN={context.get('flow.vpin_50',0):.3f}"
                    )

        if self.cooldown_bars > 0:
            self.cooldown_bars -= 1

        # ── Save state ───────────────────────────────────────────────────
        self._save_state(current_price, inference)

        # ── Broadcast ────────────────────────────────────────────────────
        if self.broadcaster and trade_event:
            try:
                self.broadcaster.broadcast(trade_event)
            except Exception as e:
                logger.warning(f"Broadcaster error: {e}")

        equity = self.portfolio.equity(current_price)
        logger.info(
            f"[TICK] price=${current_price:,.2f} | P(UP)={prob_up:.3f} | "
            f"equity=${equity:,.2f} | action={action_taken}"
        )

        return {
            "action": action_taken,
            "prob_up": prob_up,
            "price": current_price,
            "equity": round(equity, 2),
            "trade_event": trade_event,
        }

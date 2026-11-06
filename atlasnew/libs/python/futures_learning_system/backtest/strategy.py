from __future__ import annotations
from typing import Optional
from futures_learning_system.backtest.contracts import FuturesStrategyPolicy

LONG  = "LONG"
SHORT = "SHORT"
HOLD  = "HOLD"
CLOSE = "CLOSE"


class FuturesStrategy:
    """Decision bridge between ML probabilities and execution.
    
    Entry Gates (ALL must pass):
      1. Probability Gate  — P(UP) > 0.58 for LONG, < 0.42 for SHORT
      2. Toxicity Gate     — VPIN < 0.70 (no trading in informed/toxic flow)
      3. Regime Gate       — Hurst > 0.55 (trending) OR mean_rev_score > threshold (ranging)
      4. Risk Gate         — regime.risk_score below critical threshold
      5. Cooldown Gate     — enforced externally by the engine
    """

    def __init__(self, policy: FuturesStrategyPolicy = None):
        self.policy = policy or FuturesStrategyPolicy()

    def decide(self,
               prob_up: float,
               current_positions: int,
               context: dict) -> str:
        """Return LONG, SHORT or HOLD for the current bar.
        
        Args:
            prob_up: XGBoost P(UP) probability [0, 1]
            current_positions: Number of currently open positions
            context: Dict of live feature values including vpin, hurst, risk_score, etc.
        """
        p = self.policy

        if prob_up is None:
            return HOLD

        # Already at capacity
        if current_positions >= 1:
            return HOLD

        # ── Gate 1: Probability ──────────────────────────────────────────
        bullish = prob_up > p.upper_threshold
        bearish = prob_up < p.lower_threshold
        if not (bullish or bearish):
            return HOLD

        # ── Gate 2: Toxicity (VPIN) ──────────────────────────────────────
        vpin = context.get("flow.vpin_50", 0.5)
        if vpin > p.vpin_gate:
            return HOLD

        # ── Gate 3: Regime ───────────────────────────────────────────────
        hurst = context.get("info.hurst_exponent_50", 0.5)
        mean_rev_score = context.get("regime.mean_reversion_score", 0.0)

        trending_ok  = hurst > p.hurst_trend_threshold
        rev_ok       = mean_rev_score > p.mean_rev_score_threshold
        regime_ok    = trending_ok or rev_ok
        if not regime_ok:
            return HOLD

        # ── Gate 4: Risk Score ───────────────────────────────────────────
        risk_score = context.get("regime.risk_score", 0.0)
        if risk_score > p.risk_score_gate:
            return HOLD

        if bullish:
            return LONG
        if bearish:
            return SHORT
        return HOLD

    def should_exit(self,
                    direction: int,
                    open_price: float,
                    current_price: float,
                    bars_held: int,
                    prob_up: float,
                    context: dict) -> str:
        """Return exit reason string, or '' if no exit.
        
        Args:
            direction: +1 LONG, -1 SHORT
            open_price: Entry price
            current_price: Latest price
            bars_held: How many bars this position has been held
            prob_up: Current model probability
            context: Live feature dict
        """
        p = self.policy

        # Unrealized return
        ret = direction * (current_price - open_price) / open_price

        # ── Dynamic stop loss scaled by ATR ────────────────────────────
        atr_pct = context.get("vol.atr_pct_14", 0.5)
        atr_baseline = max(0.1, atr_pct)
        dynamic_sl = min(0.10, max(p.stop_loss_pct,
                                   p.atr_stop_multiplier * atr_baseline / 100.0))

        if ret <= -dynamic_sl:
            return f"stop_loss_{dynamic_sl:.3f}"

        # ── Take profit ─────────────────────────────────────────────────
        if ret >= p.take_profit_pct:
            return "take_profit"

        # ── Time stop ───────────────────────────────────────────────────
        if bars_held >= p.time_stop_bars:
            return "time_stop"

        # ── Toxicity exit ───────────────────────────────────────────────
        vpin = context.get("flow.vpin_50", 0.5)
        if vpin > p.vpin_exit_gate:
            return "toxicity_spike"

        # ── Model reversal ──────────────────────────────────────────────
        if direction == 1 and prob_up < p.lower_threshold:
            return "model_reversal"
        if direction == -1 and prob_up > p.upper_threshold:
            return "model_reversal"

        return ""

"""Strategy — model probability + policy → action.

Actions: "LONG" | "SHORT" | "CLOSE" | "HOLD".

Deterministic; every threshold is explicit in `StrategyPolicy`.
"""
from __future__ import annotations
from typing import Optional

from learning_system.backtest.contracts import StrategyPolicy


class Strategy:
    def __init__(self, policy: StrategyPolicy):
        self.policy = policy

    def decide(self, prob_up: Optional[float], current_dir: int) -> str:
        """Return an action for the current bar.

        Hysteresis band design — entry and exit use DIFFERENT thresholds:
        - No open position:
            prob_up > upper_threshold → LONG   (e.g. > 0.65)
            prob_up < lower_threshold → SHORT  (e.g. < 0.35)
            else HOLD  (hold zone: 0.35–0.65, no trade)
        - Open LONG:
            prob_up < lower_threshold → CLOSE  (requires genuine DOWN conviction)
            else HOLD  (ignore noise in the hold zone)
        - Open SHORT:
            prob_up > upper_threshold → CLOSE  (requires genuine UP conviction)
            else HOLD

        This prevents round-trip fee bleed caused by the probability
        oscillating across a single threshold boundary.
        """
        p = self.policy
        if prob_up is None:
            return "HOLD"
        if current_dir == 0:
            if prob_up > p.upper_threshold:
                return "LONG"
            if prob_up < p.lower_threshold and p.allow_short:
                return "SHORT"
            return "HOLD"
        if current_dir > 0:
            # Exit LONG only when model shows genuine DOWN conviction
            if prob_up < p.lower_threshold:
                return "CLOSE"
            return "HOLD"
        # current_dir < 0 (SHORT)
        # Exit SHORT only when model shows genuine UP conviction
        if prob_up > p.upper_threshold:
            return "CLOSE"
        return "HOLD"

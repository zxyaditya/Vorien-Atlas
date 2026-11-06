"""Options Strategy — ML probabilities + Greeks → trading action.

This is the decision bridge between the ML model and the execution engine.
It uses BOTH the directional probability (p_up) and the volatility probability
(p_vol_expand) to select the right type of option to trade.
"""
from __future__ import annotations
from typing import Optional
from options_learning_system.backtest.contracts import OptionsStrategyPolicy


# ─────────────────────────────────────────────────────────────────────
# Action Codes
# ─────────────────────────────────────────────────────────────────────
BUY_CALL  = "BUY_CALL"    # Bullish + vol expansion: long gamma, long vega
BUY_PUT   = "BUY_PUT"     # Bearish + vol expansion: long gamma, long vega
SELL_CALL = "SELL_CALL"   # Bearish + vol crush: short gamma, collect theta
SELL_PUT  = "SELL_PUT"    # Bullish + vol crush: short gamma, collect theta
CLOSE     = "CLOSE"       # Exit all open positions
HOLD      = "HOLD"        # Do nothing


class OptionsStrategy:
    def __init__(self, policy: OptionsStrategyPolicy):
        self.policy = policy

    def decide(self,
               prob_up: Optional[float],
               prob_vol_expand: Optional[float],
               current_positions: int,
               portfolio_net_delta: float,
               portfolio_net_vega: float,
               context: Optional[dict] = None) -> str:
        """Return an action for the current bar."""
        p = self.policy
        context = context or {}

        # Safety: missing signal → HOLD
        if prob_up is None or prob_vol_expand is None:
            return HOLD

        # If portfolio Greeks are at limits → must reduce, don't add
        if abs(portfolio_net_delta) >= p.max_delta_exposure:
            return HOLD
        if abs(portfolio_net_vega) >= p.max_vega_exposure:
            return HOLD

        # Max positions cap
        if current_positions >= p.max_contracts:
            return HOLD
            
        # Dynamic threshold adjustment based on market toxicity (VPIN)
        # If VPIN is high (> 0.7), the market is toxic/unstable. Require a much stronger signal.
        vpin = context.get("vpin", 0.0)
        up_thresh = p.upper_threshold
        dn_thresh = p.lower_threshold
        
        if p.dynamic_thresholds and vpin > 0.7:
            up_thresh = min(0.9, up_thresh + 0.1)
            dn_thresh = max(0.1, dn_thresh - 0.1)

        bullish = prob_up > up_thresh
        bearish = prob_up < dn_thresh
        vol_expanding = prob_vol_expand > p.vol_expand_threshold
        vol_crushing = prob_vol_expand < p.vol_crush_threshold

        if bullish and vol_expanding:
            return BUY_CALL
        if bearish and vol_expanding:
            return BUY_PUT
        if bullish and vol_crushing and p.allow_short:
            return SELL_PUT
        if bearish and vol_crushing and p.allow_short:
            return SELL_CALL

        return HOLD

    def should_exit(self,
                    position_return_pct: float,
                    prob_up: Optional[float],
                    prob_vol_expand: Optional[float],
                    option_type: str,
                    direction: int,
                    dte: int,
                    portfolio_net_delta: float,
                    context: Optional[dict] = None) -> str:
        """Determine whether to exit an open position."""
        p = self.policy
        context = context or {}
        
        # Dynamic trailing stop loss based on ATR
        atr = context.get("atr", 0.0)
        stop_pct = p.stop_loss_pct
        if p.dynamic_thresholds and atr > 0:
            # If ATR is 5%, allow a 10% stop loss.
            stop_pct = min(1.0, max(stop_pct, atr * p.atr_trailing_stop_multiplier))

        # Stop Loss: lost > stop_pct of premium paid
        if position_return_pct <= -stop_pct:
            return f"dynamic_stop_loss_hit_{stop_pct:.2f}"

        # Take Profit: gained > take_profit_pct
        if position_return_pct >= p.take_profit_pct:
            return "take_profit"

        # Approaching expiry — exit early to avoid gamma risk acceleration
        if dte <= 3:
            return "approaching_expiry"

        # Greeks limit breach
        if abs(portfolio_net_delta) > p.max_delta_exposure * 1.2:
            return "delta_limit_breach"

        # Model signal reversal — only for long options
        if direction == 1 and prob_up is not None and prob_vol_expand is not None:
            if option_type == "call" and prob_up < p.lower_threshold:
                return "model_reversal"
            if option_type == "put" and prob_up > p.upper_threshold:
                return "model_reversal"

        return ""

"""Options Execution Engine (Event-Driven Backtester).

The core simulator that marries the ML strategy with the options chain,
BS pricing, and execution constraints.
"""
from __future__ import annotations
import uuid
import time
import pandas as pd
from typing import List, Dict, Any, Optional

from options_learning_system.backtest.contracts import (
    OptionsBacktestSpec, OptionsTrade, OptionsEquityPoint, OptionsBacktestResult
)
from options_learning_system.backtest.strategy import OptionsStrategy, HOLD, BUY_CALL, BUY_PUT, SELL_CALL, SELL_PUT, CLOSE
from options_learning_system.backtest.portfolio import OptionsPortfolio
from options_learning_system.backtest.pricing import mark_to_market
from atlas_options_core.data.chain_builder import OptionsChain


class OptionsBacktestEngine:
    def __init__(self, spec: OptionsBacktestSpec, strategy: OptionsStrategy):
        self.spec = spec
        self.strategy = strategy
        self.portfolio = OptionsPortfolio(spec.initial_cash, spec.policy)
        self.closed_trades: List[OptionsTrade] = []
        self.equity_curve: List[OptionsEquityPoint] = []
        
    def _find_best_contract(self, chain: OptionsChain, target_type: str, direction: int) -> Optional[Dict]:
        """Find the most suitable contract for entry based on policy."""
        best = None
        min_spread = float("inf")
        p = self.spec.policy
        
        for c in chain.contracts:
            if c.option_type != target_type:
                continue
            if c.dte < p.min_dte or c.dte > p.max_dte:
                continue
            if c.moneyness < p.min_moneyness or c.moneyness > p.max_moneyness:
                continue
                
            spread_pct = c.spread_pct
            if spread_pct > p.max_spread_pct:
                continue
                
            # Prefer the most liquid (tightest spread) within constraints
            if spread_pct < min_spread:
                min_spread = spread_pct
                best = c
                
        if best:
            # We pay Ask if buying, receive Bid if selling
            exec_price = best.ask if direction == 1 else best.bid
            if exec_price <= 0:
                exec_price = best.mid
                
            # BUG FIX: If exec_price is still 0 (dummy data missing quotes), use theoretical BS price
            if exec_price <= 0:
                from options_learning_system.backtest.pricing import mark_to_market
                iv_to_use = best.iv if best.iv > 0 else 0.5  # fallback to 50% IV
                mtm = mark_to_market(chain.spot, best.strike, best.dte / 365.0, self.spec.r, iv_to_use, best.option_type)
                exec_price = mtm["price"]
                best.iv = iv_to_use
                
            # Enforce a minimum premium floor to prevent infinite position sizing
            exec_price = max(exec_price, 1.0)
                
            return {
                "instrument_name": best.instrument_name,
                "strike": best.strike,
                "expiry": best.expiry,
                "dte": best.dte,
                "price": exec_price,
                "iv": best.iv,
                "delta": best.delta,
                "gamma": best.gamma,
                "theta": best.theta,
                "vega": best.vega
            }
        return None

    def run(self, chain_timeseries: List[OptionsChain], predictions_df: pd.DataFrame) -> OptionsBacktestResult:
        """Run the backtest loop."""
        start_time = time.time()
        
        for idx, chain in enumerate(chain_timeseries):
            ts = pd.to_datetime(chain.timestamp, utc=True)
            spot = chain.spot
            r = self.spec.r
            
            # 1. Update Portfolio Mark-to-Market & Handle Expiries/Exits
            open_ids = list(self.portfolio.open_positions.keys())
            for trade_id in open_ids:
                trade = self.portfolio.get_position(trade_id)
                # Find contract in current chain for current IV, or use last known IV
                current_contract = next((c for c in chain.contracts if c.instrument_name == trade.instrument_name), None)
                
                # Approximate DTE decrement (1 bar, assuming 1h bars)
                current_dte = trade.dte_at_open - (idx / 24.0) 
                current_iv = current_contract.iv if current_contract else trade.open_iv
                
                mtm = mark_to_market(spot, trade.strike, current_dte / 365.0, r, current_iv, trade.option_type)
                
                # Update current Greeks
                trade.greeks_at_open = mtm  # Update state for net portfolio
                self.portfolio.update_greeks()
                
                # Check Expiry
                if current_dte <= 0:
                    exit_price = mtm["price"]
                    reason = "expiry_itm" if exit_price > 0 else "expiry_otm"
                    closed = self.portfolio.remove_position(trade_id, exit_price, self.spec.fee_per_contract, reason, ts)
                    self.closed_trades.append(closed)
                    continue
                
                # Check Strategy Exits (Stop Loss, Take Profit, etc.)
                p_ret = (mtm["price"] - trade.open_price) / (trade.open_price + 1e-6) if trade.direction == 1 else (trade.open_price - mtm["price"]) / (trade.open_price + 1e-6)
                
                prob_up = predictions_df.loc[ts, "prob_up"] if ts in predictions_df.index and "prob_up" in predictions_df.columns else None
                prob_vol = predictions_df.loc[ts, "prob_vol_expand"] if ts in predictions_df.index and "prob_vol_expand" in predictions_df.columns else None
                
                exit_context = {
                    "vpin": predictions_df.loc[ts].get("vpin", 0.0) if ts in predictions_df.index else 0.0,
                    "atr": predictions_df.loc[ts].get("atr", 0.0) if ts in predictions_df.index else 0.0
                }
                
                exit_reason = self.strategy.should_exit(
                    p_ret, prob_up, prob_vol, trade.option_type, trade.direction, 
                    current_dte, self.portfolio.net_delta, exit_context
                )
                
                if exit_reason:
                    closed = self.portfolio.remove_position(trade_id, mtm["price"], self.spec.fee_per_contract, exit_reason, ts)
                    self.closed_trades.append(closed)

            # 2. Get ML signal & execute entry
            if idx > self.spec.warmup_bars and ts in predictions_df.index:
                prob_up = predictions_df.loc[ts].get("prob_up")
                prob_vol = predictions_df.loc[ts].get("prob_vol_expand")
                
                entry_context = {
                    "vpin": predictions_df.loc[ts].get("vpin", 0.0),
                    "atr": predictions_df.loc[ts].get("atr", 0.0)
                }
                
                action = self.strategy.decide(
                    prob_up, prob_vol, len(self.portfolio.open_positions),
                    self.portfolio.net_delta, self.portfolio.net_vega, entry_context
                )
                
                target_type = None
                direction = 0
                
                if action == BUY_CALL:
                    target_type = "call"; direction = 1
                elif action == BUY_PUT:
                    target_type = "put"; direction = 1
                elif action == SELL_CALL:
                    target_type = "call"; direction = -1
                elif action == SELL_PUT:
                    target_type = "put"; direction = -1
                elif action == CLOSE:
                    open_ids = list(self.portfolio.open_positions.keys())
                    for tid in open_ids:
                        trade = self.portfolio.get_position(tid)
                        self.closed_trades.append(
                            self.portfolio.remove_position(tid, trade.open_price, self.spec.fee_per_contract, "model_close_all", ts)
                        )
                
                if target_type:
                    contract = self._find_best_contract(chain, target_type, direction)
                    if contract:
                        size = self.spec.policy.position_size_usd / (contract["price"] * 100 + 1e-6) # Assuming multiplier 100
                        size = round(size, 2)
                        if size > 0:
                            trade = OptionsTrade(
                                trade_id=str(uuid.uuid4())[:8],
                                instrument_name=contract["instrument_name"],
                                underlying=self.spec.underlying,
                                option_type=target_type,
                                direction=direction,
                                strike=contract["strike"],
                                expiry=contract["expiry"],
                                dte_at_open=contract["dte"],
                                open_time=ts,
                                open_price=contract["price"],
                                open_spot=spot,
                                open_iv=contract["iv"],
                                size=size,
                                fee_paid=self.spec.fee_per_contract,
                                greeks_at_open={
                                    "delta": contract["delta"],
                                    "gamma": contract["gamma"],
                                    "theta": contract["theta"],
                                    "vega": contract["vega"]
                                }
                            )
                            self.portfolio.add_position(trade)
                            
            # 3. Record Equity Point
            self.equity_curve.append(OptionsEquityPoint(
                time=ts,
                equity=self.portfolio.total_equity(),
                cash=self.portfolio.cash,
                n_open_positions=len(self.portfolio.open_positions),
                net_delta=self.portfolio.net_delta,
                net_gamma=self.portfolio.net_gamma,
                net_theta=self.portfolio.net_theta,
                net_vega=self.portfolio.net_vega,
                spot=spot
            ))
            
        duration = time.time() - start_time
        return OptionsBacktestResult(
            backtest_id=f"bt_{int(time.time())}",
            spec=self.spec,
            n_bars_evaluated=len(chain_timeseries),
            trades=self.closed_trades,
            equity_curve=self.equity_curve,
            metrics={},
            duration_seconds=duration,
            created_at=str(pd.Timestamp.utcnow())
        )

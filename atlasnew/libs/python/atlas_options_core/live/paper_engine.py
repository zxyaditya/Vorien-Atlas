"""Live Paper Execution Engine.

Simulates execution against live Deribit orderbooks and manages
the active portfolio state via a persistent JSON file.
"""
import os
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict

from options_learning_system.backtest.contracts import OptionsStrategyPolicy, OptionsTrade
from options_learning_system.backtest.strategy import OptionsStrategy, BUY_CALL, BUY_PUT, SELL_CALL, SELL_PUT, CLOSE
from options_learning_system.backtest.portfolio import OptionsPortfolio
from options_learning_system.backtest.pricing import mark_to_market
from atlas_options_core.data.chain_builder import OptionsChain

logger = logging.getLogger("PaperEngine")


class LivePaperEngine:
    def __init__(self, state_file: str, policy: OptionsStrategyPolicy, broadcaster=None):
        self.state_file = state_file
        self.policy = policy
        self.broadcaster = broadcaster
        self.strategy = OptionsStrategy(policy)
        self.portfolio = OptionsPortfolio(policy.position_size_usd * 10, policy) # Mock $50k starting
        self.closed_trades = []
        self._load_state()

    def _load_state(self):
        """Load portfolio state from JSON to survive script restarts."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    # For simplicity, we just rebuild the cash balance. 
                    # A robust implementation would deserialize all open OptionsTrade objects.
                    self.portfolio.cash = data.get("cash", self.portfolio.cash)
                    open_pos = data.get("open_positions", {})
                    for tid, pdict in open_pos.items():
                        trade = OptionsTrade(
                            trade_id=tid,
                            instrument_name=pdict["instrument_name"],
                            underlying=pdict["underlying"],
                            option_type=pdict["option_type"],
                            direction=pdict["direction"],
                            strike=pdict["strike"],
                            expiry=pdict["expiry"],
                            dte_at_open=pdict["dte_at_open"],
                            open_time=pd.to_datetime(pdict["open_time"]),
                            open_price=pdict["open_price"],
                            open_spot=pdict["open_spot"],
                            open_iv=pdict["open_iv"],
                            size=pdict["size"],
                            fee_paid=pdict["fee_paid"],
                            greeks_at_open=pdict["greeks_at_open"]
                        )
                        self.portfolio.open_positions[tid] = trade
                logger.info(f"Loaded portfolio state. Cash: ${self.portfolio.cash:.2f}, Open: {len(self.portfolio.open_positions)}")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")

    def _save_state(self):
        try:
            open_pos = {}
            for tid, trade in self.portfolio.open_positions.items():
                open_pos[tid] = {
                    "instrument_name": trade.instrument_name,
                    "underlying": trade.underlying,
                    "option_type": trade.option_type,
                    "direction": trade.direction,
                    "strike": trade.strike,
                    "expiry": trade.expiry,
                    "dte_at_open": trade.dte_at_open,
                    "open_time": str(trade.open_time),
                    "open_price": trade.open_price,
                    "open_spot": trade.open_spot,
                    "open_iv": trade.open_iv,
                    "size": trade.size,
                    "fee_paid": trade.fee_paid,
                    "greeks_at_open": trade.greeks_at_open
                }
            data = {
                "cash": self.portfolio.cash,
                "open_positions": open_pos,
                "closed_trades_count": len(self.closed_trades)
            }
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _find_best_contract(self, chain: OptionsChain, target_type: str, direction: int) -> Optional[Dict]:
        best = None
        min_spread = float("inf")
        p = self.policy
        for c in chain.contracts:
            if c.option_type != target_type: continue
            if c.dte < p.min_dte or c.dte > p.max_dte: continue
            if c.moneyness < p.min_moneyness or c.moneyness > p.max_moneyness: continue
            
            spread = c.spread_pct
            if spread > p.max_spread_pct: continue
            if spread < min_spread:
                min_spread = spread
                best = c
                
        if best:
            exec_price = best.ask if direction == 1 else best.bid
            if exec_price <= 0:
                exec_price = best.mid
            if exec_price <= 0:
                exec_price = max(1.0, best.iv * 100) # mock fallback
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

    import pandas as pd # Ensure pandas is available for datetime parsing if needed
    
    def process_tick(self, inference_result: dict):
        if not inference_result:
            return
            
        ts = inference_result["timestamp"]
        spot = inference_result["spot"]
        chain = inference_result["chain"]
        prob_up = inference_result["prob_up"]
        prob_vol = inference_result["prob_vol_expand"]
        context = inference_result["context"]
        
        # 1. Evaluate Exits
        open_ids = list(self.portfolio.open_positions.keys())
        for tid in open_ids:
            trade = self.portfolio.get_position(tid)
            # Find live current quote
            current_contract = next((c for c in chain.contracts if c.instrument_name == trade.instrument_name), None)
            
            if current_contract:
                current_price = current_contract.bid if trade.direction == 1 else current_contract.ask
                if current_price <= 0:
                    current_price = current_contract.mid
                current_iv = current_contract.iv
                current_dte = current_contract.dte
            else:
                # Approximation if contract missing from live feed
                current_price = trade.open_price
                current_iv = trade.open_iv
                current_dte = trade.dte_at_open - 1
                
            if current_dte <= 0:
                logger.info(f"Closing {tid} - Expiry")
                self.closed_trades.append(self.portfolio.remove_position(tid, current_price, 0.5, "expiry", ts))
                continue
                
            p_ret = (current_price - trade.open_price) / (trade.open_price + 1e-6) if trade.direction == 1 else (trade.open_price - current_price) / (trade.open_price + 1e-6)
            
            exit_reason = self.strategy.should_exit(
                p_ret, prob_up, prob_vol, trade.option_type, trade.direction, 
                current_dte, self.portfolio.net_delta, context
            )
            
            if exit_reason:
                logger.info(f"Closing {tid} - Reason: {exit_reason} at PnL {p_ret*100:.2f}%")
                self.closed_trades.append(self.portfolio.remove_position(tid, current_price, 0.5, exit_reason, ts))
                
                if self.broadcaster:
                    trade_info = {
                        "instrument_name": trade.instrument_name,
                        "underlying": trade.underlying,
                        "option_type": trade.option_type,
                        "direction": trade.direction,
                        "size": trade.size,
                        "price": current_price,
                        "timestamp": ts
                    }
                    self.broadcaster.broadcast_trade(trade_info, "CLOSE", p_ret)
                
        # 2. Evaluate Entries
        action = self.strategy.decide(
            prob_up, prob_vol, len(self.portfolio.open_positions),
            self.portfolio.net_delta, self.portfolio.net_vega, context
        )
        
        target_type, direction = None, 0
        if action == BUY_CALL:
            target_type, direction = "call", 1
        elif action == BUY_PUT:
            target_type, direction = "put", 1
        elif action == SELL_CALL:
            target_type, direction = "call", -1
        elif action == SELL_PUT:
            target_type, direction = "put", -1
            
        if target_type:
            contract = self._find_best_contract(chain, target_type, direction)
            if contract:
                # Sizing
                size = self.policy.position_size_usd / (contract["price"] * 100 + 1e-6)
                size = round(size, 2)
                if size > 0:
                    trade = OptionsTrade(
                        trade_id=str(uuid.uuid4())[:8],
                        instrument_name=contract["instrument_name"],
                        underlying="ETH",
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
                        fee_paid=0.5,
                        greeks_at_open={
                            "delta": contract["delta"],
                            "gamma": contract["gamma"],
                            "theta": contract["theta"],
                            "vega": contract["vega"]
                        }
                    )
                    self.portfolio.add_position(trade)
                    logger.info(f"OPEN {action} -> {trade.size}x {trade.instrument_name} @ ${trade.open_price:.2f}")
                    
                    if self.broadcaster:
                        trade_info = {
                            "instrument_name": contract["instrument_name"],
                            "underlying": "ETH",
                            "option_type": target_type,
                            "direction": direction,
                            "size": size,
                            "price": contract["price"],
                            "timestamp": ts
                        }
                        self.broadcaster.broadcast_trade(trade_info, "OPEN")

        # Finalize
        self.portfolio.update_greeks()
        self._save_state()
        
        logger.info(f"End of Tick. Equity: ${self.portfolio.total_equity():.2f}, Open: {len(self.portfolio.open_positions)}")

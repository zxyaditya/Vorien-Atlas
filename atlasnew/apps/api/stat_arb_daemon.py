import os
import json
import time
import logging
from datetime import datetime, timezone
import ccxt
import pandas as pd
import numpy as np

# Adjust imports since this is in backend root
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'stat_arb'))

from stat_arb_backtester import kalman_hedge_ratio, rolling_ou_zscore
from walk_forward_statarb import fetch_large_data

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
STATE_FILE = "stat_arb_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error reading state: {e}")
    return {
        "capital": 250.0,
        "initial_capital": 250.0, # Fixed sizing base
        "leverage": 10.0,
        "in_trade": 0, # 1 for Long Spread, -1 for Short Spread
        "entry_price_y": 0.0,
        "entry_price_x": 0.0,
        "qty_y": 0.0,
        "qty_x": 0.0,
        "trades": [],
        "equity_curve": [10000.0],
        # Telemetry
        "z_score": 0.0,
        "kalman_beta": 0.0,
        "volatility": 0.0,
        "regime": "RANGING", # RANGING or TRENDING
        "vol_threshold": 0.009817, # Hardcoded from 1-Year Train Phase
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def run_daemon():
    exchange = ccxt.binanceusdm()
    y_sym = 'AVAX/USDT:USDT'
    x_sym = 'SOL/USDT:USDT'
    
    fee_rate = 0.0002 # 0.02% Maker Limit Order
    
    z_entry = 2.0
    z_tp = 0.5
    z_sl = 4.0
    window = 24
    
    while True:
        try:
            state = load_state()
            
            logging.info("Fetching live data for StatArb Engine...")
            # We need 2150 hours to cover the 24h rolling windows safely with no burn-in issues
            y_prices = fetch_large_data(y_sym, exchange, '1h', 2150)
            x_prices = fetch_large_data(x_sym, exchange, '1h', 2150)
            
            df = pd.DataFrame({
                y_sym: y_prices,
                x_sym: x_prices
            }).dropna()
            
            # Math
            df['log_y'] = np.log(df[y_sym])
            df['log_x'] = np.log(df[x_sym])
            df['beta'] = kalman_hedge_ratio(df['log_y'], df['log_x'])
            df['spread'] = df['log_y'] - (df['beta'] * df['log_x'])
            
            df['spread_volatility'] = df['spread'].rolling(24).std()
            df['z_score'] = rolling_ou_zscore(df['spread'], window=window)
            
            # Live Metrics
            live_z = float(df['z_score'].iloc[-1])
            live_beta = float(df['beta'].iloc[-1])
            live_vol = float(df['spread_volatility'].iloc[-1])
            live_regime = "TRENDING (HALT)" if live_vol > state['vol_threshold'] else "RANGING (SAFE)"
            
            price_y = float(df[y_sym].iloc[-1])
            price_x = float(df[x_sym].iloc[-1])
            
            # Update telemetry
            state['z_score'] = live_z
            state['kalman_beta'] = live_beta
            state['volatility'] = live_vol
            state['regime'] = live_regime
            state['timestamp'] = datetime.now(timezone.utc).isoformat()
            
            # Decision Engine
            in_trade = state['in_trade']
            capital = state['capital']
            initial_capital = state['initial_capital']
            leverage = state['leverage']
            qty_y = state['qty_y']
            qty_x = state['qty_x']
            entry_price_y = state['entry_price_y']
            entry_price_x = state['entry_price_x']
            
            # ENTRY
            if in_trade == 0 and "SAFE" in live_regime:
                if live_z > z_entry:
                    logging.info(f"OPENING SHORT SPREAD. Z-Score: {live_z:.2f}")
                    in_trade = -1
                    qty_y = -(initial_capital * leverage) / price_y
                    qty_x = (initial_capital * leverage * live_beta) / price_x
                    entry_price_y = price_y
                    entry_price_x = price_x
                    fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
                    capital -= fees
                elif live_z < -z_entry:
                    logging.info(f"OPENING LONG SPREAD. Z-Score: {live_z:.2f}")
                    in_trade = 1
                    qty_y = (initial_capital * leverage) / price_y
                    qty_x = -(initial_capital * leverage * live_beta) / price_x
                    entry_price_y = price_y
                    entry_price_x = price_x
                    fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
                    capital -= fees
                    
            # EXIT
            elif in_trade == -1 and (live_z <= z_tp or live_z >= z_sl or "HALT" in live_regime):
                logging.info(f"CLOSING SHORT SPREAD. Z-Score: {live_z:.2f}")
                pnl_y = qty_y * (price_y - entry_price_y)
                pnl_x = qty_x * (price_x - entry_price_x)
                fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
                trade_pnl = pnl_y + pnl_x - fees
                capital += trade_pnl
                state['trades'].append(trade_pnl)
                state['equity_curve'].append(capital)
                in_trade = 0
                qty_y = 0.0
                qty_x = 0.0
                
            elif in_trade == 1 and (live_z >= -z_tp or live_z <= -z_sl or "HALT" in live_regime):
                logging.info(f"CLOSING LONG SPREAD. Z-Score: {live_z:.2f}")
                pnl_y = qty_y * (price_y - entry_price_y)
                pnl_x = qty_x * (price_x - entry_price_x)
                fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
                trade_pnl = pnl_y + pnl_x - fees
                capital += trade_pnl
                state['trades'].append(trade_pnl)
                state['equity_curve'].append(capital)
                in_trade = 0
                qty_y = 0.0
                qty_x = 0.0
                
            # Unrealized PNL
            unrealized = 0.0
            if in_trade != 0:
                unrealized = qty_y * (price_y - entry_price_y) + qty_x * (price_x - entry_price_x)
                
            state['capital'] = capital
            state['in_trade'] = in_trade
            state['qty_y'] = qty_y
            state['qty_x'] = qty_x
            state['entry_price_y'] = entry_price_y
            state['entry_price_x'] = entry_price_x
            state['unrealized_pnl'] = unrealized
            
            save_state(state)
            logging.info(f"State saved. Equity: ${capital:.2f} | Unrealized: ${unrealized:.2f} | Regime: {live_regime}")
            
        except Exception as e:
            logging.error(f"Daemon Error: {e}")
            
        # Loop interval: 20 seconds for UI responsiveness
        time.sleep(20)

if __name__ == "__main__":
    run_daemon()

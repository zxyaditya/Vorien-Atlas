import os
import ccxt
import pandas as pd
import numpy as np
import statsmodels.api as sm
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def fetch_data(symbol, exchange, timeframe='1h', limit=1500):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df['close']

from pykalman import KalmanFilter

def kalman_hedge_ratio(y, x):
    logging.info("Calculating Dynamic Kalman Filter Hedge Ratio...")
    obs_mat = sm.add_constant(x.values, prepend=False)[:, np.newaxis, :]
    kf = KalmanFilter(
        n_dim_obs=1, n_dim_state=2,
        initial_state_mean=[0, 0],
        initial_state_covariance=np.ones((2, 2)),
        transition_matrices=np.eye(2),
        observation_matrices=obs_mat,
        observation_covariance=0.1,
        transition_covariance=np.eye(2) * 1e-4
    )
    state_means, _ = kf.filter(y.values)
    return pd.Series(state_means[:, 0], index=y.index)

def rolling_ou_zscore(spread, window=100, dt=1.0):
    ou_z = []
    for i in range(len(spread)):
        if i <= window:
            ou_z.append(np.nan)
        else:
            y = spread.iloc[i-window+1:i+1].values
            x = spread.iloc[i-window:i].values
            
            x_const = sm.add_constant(x, prepend=True)
            try:
                model = sm.OLS(y, x_const).fit()
                a = model.params[0]
                b = model.params[1]
                
                if b <= 0 or b >= 1:
                    ou_z.append(np.nan)
                    continue
                    
                sigma_e = np.sqrt(model.mse_resid)
                theta = -np.log(b) / dt
                mu = a / (1 - b)
                
                if theta < 1e-6:
                    ou_z.append(np.nan)
                    continue
                    
                sigma = sigma_e * np.sqrt(2 * theta / (1 - np.exp(-2 * theta * dt)))
                sigma_eq = sigma / np.sqrt(2 * theta)
                
                current_spread = spread.iloc[i]
                z = (current_spread - mu) / sigma_eq
                ou_z.append(z)
            except Exception:
                ou_z.append(np.nan)
                
    return pd.Series(ou_z, index=spread.index)

def backtest(df, y_col, x_col, z_entry=2.0, z_tp=0.5, z_sl=4.0):
    in_trade = 0 # 1 for Long Spread, -1 for Short Spread
    trades = []
    capital = 10000.0
    
    entry_price_y = 0.0
    entry_price_x = 0.0
    qty_y = 0.0
    qty_x = 0.0
    
    fee_rate = 0.0004 # 0.04% taker fee on Binance Futures
    
    equity_curve = [capital]
    
    for i in range(1, len(df)):
        z = df['z_score'].iloc[i-1] # Use previous bar's z-score to prevent lookahead
        price_y = df[y_col].iloc[i]
        price_x = df[x_col].iloc[i]
        beta = df['beta'].iloc[i-1]
        
        if pd.isna(z) or pd.isna(beta):
            equity_curve.append(capital)
            continue
            
        # Entry Logic
        if in_trade == 0:
            if z > z_entry:
                # Short Spread: Short Y, Long X
                in_trade = -1
                qty_y = -capital / price_y
                qty_x = (capital * beta) / price_x
                entry_price_y = price_y
                entry_price_x = price_x
                # Deduct fees
                fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
                capital -= fees
                
            elif z < -z_entry:
                # Long Spread: Long Y, Short X
                in_trade = 1
                qty_y = capital / price_y
                qty_x = -(capital * beta) / price_x
                entry_price_y = price_y
                entry_price_x = price_x
                # Deduct fees
                fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
                capital -= fees
                
        # Exit Logic
        elif in_trade == -1 and (z <= z_tp or z >= z_sl):
            # Close Short Spread (Take Profit or Stop Loss)
            pnl_y = qty_y * (price_y - entry_price_y)
            pnl_x = qty_x * (price_x - entry_price_x)
            
            fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
            trade_pnl = pnl_y + pnl_x - fees
            capital += trade_pnl
            trades.append(trade_pnl)
            in_trade = 0
            
        elif in_trade == 1 and (z >= -z_tp or z <= -z_sl):
            # Close Long Spread (Take Profit or Stop Loss)
            pnl_y = qty_y * (price_y - entry_price_y)
            pnl_x = qty_x * (price_x - entry_price_x)
            
            fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
            trade_pnl = pnl_y + pnl_x - fees
            capital += trade_pnl
            trades.append(trade_pnl)
            in_trade = 0
            
        # Mark to market (unrealized) if in trade, else realized
        if in_trade != 0:
            unrealized_pnl = qty_y * (price_y - entry_price_y) + qty_x * (price_x - entry_price_x)
            equity_curve.append(capital + unrealized_pnl)
        else:
            equity_curve.append(capital)
            
    return trades, equity_curve

def main():
    exchange = ccxt.binanceusdm()
    
    # Using the best pair from Phase 1
    y_sym = 'AVAX/USDT:USDT'
    x_sym = 'SOL/USDT:USDT'
    
    logging.info(f"Fetching data for {y_sym} and {x_sym}")
    y_prices = fetch_data(y_sym, exchange, '1h', 1500)
    x_prices = fetch_data(x_sym, exchange, '1h', 1500)
    
    df = pd.DataFrame({
        y_sym: y_prices,
        x_sym: x_prices
    }).dropna()
    
    logging.info("Calculating Rolling OLS and Z-Scores...")
    df['log_y'] = np.log(df[y_sym])
    df['log_x'] = np.log(df[x_sym])
    
    best_return = -999.0
    best_params = {}
    
    print("\nStarting Parameter Sweep...")
    
    # Calculate dynamic beta using Kalman Filter once (independent of rolling window)
    df['beta'] = kalman_hedge_ratio(df['log_y'], df['log_x'])
    
    for window in [24, 48, 100, 200]:
        df_temp = df.copy()
        
        df_temp['spread'] = df_temp['log_y'] - (df_temp['beta'] * df_temp['log_x'])
        
        logging.info(f"Calculating OU MLE optimal thresholds (window={window})...")
        df_temp['z_score'] = rolling_ou_zscore(df_temp['spread'], window=window)
        df_temp.dropna(inplace=True)
        
        for z_entry in [1.5, 2.0, 2.5]:
            for z_tp in [0.0, 0.5, 1.0]:
                trades, equity = backtest(df_temp, y_sym, x_sym, z_entry=z_entry, z_tp=z_tp, z_sl=4.0)
                total_return = (equity[-1] - 10000.0) / 10000.0
                total_trades = len(trades)
                win_rate = len([t for t in trades if t > 0]) / total_trades if total_trades > 0 else 0
                
                if total_return > best_return and total_trades > 5:
                    best_return = total_return
                    best_params = {
                        'window': window,
                        'z_entry': z_entry,
                        'z_tp': z_tp,
                        'trades': total_trades,
                        'win_rate': win_rate,
                        'return': total_return
                    }

    print("\n==================================================")
    print("STATISTICAL ARBITRAGE BACKTEST (AVAX vs SOL)")
    print("==================================================")
    print(f"Optimal Window:  {best_params.get('window', 'N/A')} hours")
    print(f"Optimal Z-Entry: {best_params.get('z_entry', 'N/A')}")
    print(f"Optimal Z-TakeP: {best_params.get('z_tp', 'N/A')}")
    print(f"Fixed Z-StopL:   4.0")
    print(f"Total Trades:    {best_params.get('trades', 0)}")
    print(f"Win Rate:        {best_params.get('win_rate', 0):.2%}")
    print(f"Total Return:    {best_params.get('return', 0):.2%}")
    print("==================================================\n")

if __name__ == "__main__":
    main()

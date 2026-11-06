import os
import ccxt
import time
import pandas as pd
import numpy as np
import logging

from stat_arb_backtester import kalman_hedge_ratio, rolling_ou_zscore
from walk_forward_statarb import fetch_large_data

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def backtest_hmm(df, y_col, x_col, z_entry=2.0, z_tp=0.5, z_sl=4.0, starting_capital=250.0, beta_stable_threshold=0.0):
    in_trade = 0 # 1 for Long Spread, -1 for Short Spread
    trades = []
    capital = starting_capital
    allocated_capital = 0.0
    
    entry_price_y = 0.0
    entry_price_x = 0.0
    qty_y = 0.0
    qty_x = 0.0
    
    fee_rate = 0.0002 # 0.02% maker fee on Binance Futures
    equity_curve = [capital]
    
    for i in range(1, len(df)):
        z = df['z_score'].iloc[i-1] 
        state = df['hmm_state'].iloc[i-1] # Predicted Regime
        high_vol_state = df['high_vol_state'].iloc[i-1]
        
        price_y = df[y_col].iloc[i]
        price_x = df[x_col].iloc[i]
        beta = df['beta'].iloc[i-1]
        beta_var = df['beta_variance'].iloc[i-1] if 'beta_variance' in df.columns else 999.0
        
        if pd.isna(z) or pd.isna(beta) or pd.isna(state):
            equity_curve.append(capital)
            continue
            
        # Entry Logic
        if in_trade == 0:
            # ONLY TRADE IF IN LOW VOLATILITY REGIME (SAFE, RANGING MARKET)
            if state != high_vol_state:
                leverage = 10.0 # 10x leverage on the allocated portion
                
                # Dynamic Sizing based on Extreme Kalman Beta Confidence
                if beta_var < beta_stable_threshold:
                    initial_capital = capital * 0.50 # 50% sizing for extreme confidence
                else:
                    initial_capital = capital * 0.30 # 30% sizing standard
                
                allocated_capital = initial_capital
                
                if z > z_entry:
                    # Short Spread: Short Y, Long X
                    in_trade = -1
                    qty_y = -(initial_capital * leverage) / price_y
                    qty_x = (initial_capital * leverage * beta) / price_x
                    entry_price_y = price_y
                    entry_price_x = price_x
                    fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
                    capital -= fees
                    
                elif z < -z_entry:
                    # Long Spread: Long Y, Short X
                    in_trade = 1
                    qty_y = (initial_capital * leverage) / price_y
                    qty_x = -(initial_capital * leverage * beta) / price_x
                    entry_price_y = price_y
                    entry_price_x = price_x
                    fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
                    capital -= fees
                
        # Exit Logic (Can exit in any regime to secure capital)
        elif in_trade != 0:
            current_unrealized_pnl = qty_y * (price_y - entry_price_y) + qty_x * (price_x - entry_price_x)
            hard_stop = current_unrealized_pnl <= -0.60 * allocated_capital
            
            if in_trade == -1 and (z <= z_tp or z >= z_sl or state == high_vol_state or hard_stop):
                # Close Short Spread (Take Profit, Stop Loss, Panic Exit, or Hard 60% Stop Loss)
                pnl_y = qty_y * (price_y - entry_price_y)
                pnl_x = qty_x * (price_x - entry_price_x)
                
                fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
                trade_pnl = pnl_y + pnl_x - fees
                capital += trade_pnl
                trades.append(trade_pnl)
                in_trade = 0
                
            elif in_trade == 1 and (z >= -z_tp or z <= -z_sl or state == high_vol_state or hard_stop):
                # Close Long Spread
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
            
    equity_series = pd.Series(equity_curve, index=df.index)
    return trades, equity_series

def main():
    exchange = ccxt.binanceusdm()
    y_sym = 'AVAX/USDT:USDT'
    x_sym = 'SOL/USDT:USDT'
    
    # Fetch 2 years of data (17520 hours) for a 1-Year Train / 1-Year Test split
    logging.info(f"Fetching 17520 bars of {y_sym} data...")
    y_prices = fetch_large_data(y_sym, exchange, '1h', 17520)
    
    logging.info(f"Fetching 17520 bars of {x_sym} data...")
    x_prices = fetch_large_data(x_sym, exchange, '1h', 17520)
    
    df = pd.DataFrame({
        y_sym: y_prices,
        x_sym: x_prices
    }).dropna()
    
    print("\n==================================================")
    print("MACHINE LEARNING WALK-FORWARD (HMM REGIME CLASSIFICATION)")
    print("==================================================")
    
    df['log_y'] = np.log(df[y_sym])
    df['log_x'] = np.log(df[x_sym])
    df['beta'] = kalman_hedge_ratio(df['log_y'], df['log_x'])
    df['beta_variance'] = df['beta'].rolling(window=72).var()
    df['spread'] = df['log_y'] - (df['beta'] * df['log_x'])
    
    # Feature Engineering for HMM
    df['spread_volatility'] = df['spread'].rolling(24).std()
    df['spread_drift'] = df['spread'].diff(1)
    df.dropna(inplace=True)
    
    # ---------------------------------------------------------
    # ROLLING WALK-FORWARD OPTIMIZATION
    # ---------------------------------------------------------
    logging.info("Starting Rolling Walk-Forward Optimization (1-Month Train / 1-Week Test)...")
    
    train_bars = 730 # Approx 1 month
    test_bars = 168  # Approx 1 week
    
    master_equity = []
    master_trades = []
    
    current_capital = 250.0
    start_idx = 0
    total_bars = len(df)
    
    while start_idx + train_bars + test_bars <= total_bars:
        train_end = start_idx + train_bars
        test_end = train_end + test_bars
        
        train_df = df.iloc[start_idx:train_end].copy()
        test_df = df.iloc[train_end:test_end].copy()
        
        # 1. Train Volatility Threshold
        vol_threshold = train_df['spread_volatility'].quantile(0.80)
        train_df['hmm_state'] = np.where(train_df['spread_volatility'] > vol_threshold, 1, 0)
        train_df['high_vol_state'] = 1
        
        # 2. Grid Search Train
        best_return = -999.0
        best_params = {'window': 24, 'z_entry': 2.0}
        
        for window in [24, 48, 100]:
            train_temp = train_df.copy()
            train_temp['z_score'] = rolling_ou_zscore(train_temp['spread'], window=window)
            train_temp.dropna(inplace=True)
            
            for z_entry in [1.5, 2.0, 2.5]:
                # Temporary backtest just to find the best return (always starts at 250.0)
                trades, equity = backtest_hmm(train_temp, y_sym, x_sym, z_entry=z_entry, z_tp=0.5, z_sl=4.0, starting_capital=250.0)
                ret = (equity.iloc[-1] - 250.0) / 250.0
                if ret > best_return and len(trades) > 2:
                    best_return = ret
                    best_params = {'window': window, 'z_entry': z_entry}
                    
        # 3. Test on Out-of-Sample Window
        test_df['hmm_state'] = np.where(test_df['spread_volatility'] > vol_threshold, 1, 0)
        test_df['high_vol_state'] = 1
        
        # Calculate beta stability threshold from the training window (bottom 25% variance)
        beta_stable_threshold = train_df['beta_variance'].quantile(0.25)
        
        opt_window = best_params['window']
        opt_z_entry = best_params['z_entry']
        
        test_df['z_score'] = rolling_ou_zscore(test_df['spread'], window=opt_window)
        test_df.dropna(inplace=True)
        
        # Pass the running current_capital into backtest_hmm
        trades, equity = backtest_hmm(
            test_df, y_sym, x_sym, 
            z_entry=opt_z_entry, z_tp=0.5, z_sl=4.0, 
            starting_capital=current_capital,
            beta_stable_threshold=beta_stable_threshold
        )
        
        # Update current capital for next run
        current_capital = equity.iloc[-1]
        
        # Append to master
        if len(master_equity) == 0:
            master_equity.append(equity)
        else:
            master_equity.append(equity.iloc[1:])
            
        master_trades.extend(trades)
        
        # Move forward by 1 month
        start_idx += test_bars

    # Concat master equity
    master_equity_series = pd.concat(master_equity)
    
    total_return = (master_equity_series.iloc[-1] - 250.0) / 250.0
    total_trades = len(master_trades)
    win_rate = len([t for t in master_trades if t > 0]) / total_trades if total_trades > 0 else 0
    
    print("\n==================================================")
    print("ROLLING WALK-FORWARD OPTIMIZATION RESULTS")
    print("==================================================")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate:     {win_rate:.2%}")
    print(f"Total Return: {total_return:.2%}")
    
    print("\n[TEST] MONTHLY RETURNS:")
    try:
        monthly_equity = master_equity_series.resample('ME').last()
    except ValueError:
        monthly_equity = master_equity_series.resample('M').last()
        
    monthly_returns = monthly_equity.pct_change().dropna()
    for date, ret in monthly_returns.items():
        print(f"{date.strftime('%Y-%b')}: {ret:+.2%}")
    print("==================================================\n")

if __name__ == "__main__":
    main()

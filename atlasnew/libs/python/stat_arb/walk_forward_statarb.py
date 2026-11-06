import os
import ccxt
import time
import pandas as pd
import numpy as np
import logging

from stat_arb_backtester import kalman_hedge_ratio, rolling_ou_zscore, backtest
from copula_backtester import rolling_copula_prob, backtest_copula

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def fetch_large_data(symbol, exchange, timeframe='1h', total_limit=4320):
    logging.info(f"Fetching {total_limit} bars of {symbol} data...")
    all_bars = []
    since = None
    
    # Calculate starting timestamp roughly
    if timeframe == '1h':
        ms_per_bar = 60 * 60 * 1000
    else:
        ms_per_bar = 60 * 60 * 1000 # default
        
    since = exchange.milliseconds() - (total_limit * ms_per_bar)
    
    while len(all_bars) < total_limit:
        limit = min(1500, total_limit - len(all_bars))
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit, since=since)
        if not bars:
            break
            
        all_bars.extend(bars)
        since = bars[-1][0] + 1
        time.sleep(exchange.rateLimit / 1000.0)
        
    df = pd.DataFrame(all_bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.drop_duplicates(subset=['timestamp'], inplace=True)
    df.set_index('timestamp', inplace=True)
    return df['close']

def run_core_spread_walk_forward(df, y_sym, x_sym):
    print("\n==================================================")
    print("WALK-FORWARD ANALYSIS: KALMAN + OU SPREAD")
    print("==================================================")
    
    df = df.copy()
    df['log_y'] = np.log(df[y_sym])
    df['log_x'] = np.log(df[x_sym])
    df['beta'] = kalman_hedge_ratio(df['log_y'], df['log_x'])
    df['spread'] = df['log_y'] - (df['beta'] * df['log_x'])
    
    # Split Data: Train (first 50%), Test (last 50%)
    split_idx = len(df) // 2
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    
    logging.info(f"Train Dataset: {len(train_df)} bars. Test Dataset: {len(test_df)} bars.")
    
    # --- TRAIN PHASE ---
    logging.info("Running In-Sample Training Sweep...")
    best_return = -999.0
    best_params = {}
    
    for window in [24, 48, 100, 200]:
        train_temp = train_df.copy()
        train_temp['z_score'] = rolling_ou_zscore(train_temp['spread'], window=window)
        train_temp.dropna(inplace=True)
        
        for z_entry in [1.5, 2.0, 2.5]:
            for z_tp in [0.0, 0.5, 1.0]:
                trades, equity = backtest(train_temp, y_sym, x_sym, z_entry=z_entry, z_tp=z_tp, z_sl=4.0)
                total_return = (equity[-1] - 10000.0) / 10000.0
                total_trades = len(trades)
                
                if total_return > best_return and total_trades > 2:
                    best_return = total_return
                    best_params = {'window': window, 'z_entry': z_entry, 'z_tp': z_tp}
                    
    print("\n[TRAIN] Best In-Sample Parameters Found:")
    print(f"Window: {best_params['window']}h | Z-Entry: {best_params['z_entry']} | Z-TakeProfit: {best_params['z_tp']}")
    print(f"[TRAIN] In-Sample Return: {best_return:.2%}")
    
    # --- TEST PHASE ---
    logging.info("Running Out-Of-Sample Testing with Locked Parameters...")
    opt_window = best_params['window']
    opt_z_entry = best_params['z_entry']
    opt_z_tp = best_params['z_tp']
    
    test_temp = test_df.copy()
    test_temp['z_score'] = rolling_ou_zscore(test_temp['spread'], window=opt_window)
    test_temp.dropna(inplace=True)
    
    trades, equity = backtest(test_temp, y_sym, x_sym, z_entry=opt_z_entry, z_tp=opt_z_tp, z_sl=4.0)
    
    total_return = (equity[-1] - 10000.0) / 10000.0
    total_trades = len(trades)
    win_rate = len([t for t in trades if t > 0]) / total_trades if total_trades > 0 else 0
    
    print("\n[TEST] OUT-OF-SAMPLE RESULTS (Unseen Data):")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate:     {win_rate:.2%}")
    print(f"Total Return: {total_return:.2%}")
    print("==================================================\n")

def run_copula_walk_forward(df, y_sym, x_sym):
    print("\n==================================================")
    print("WALK-FORWARD ANALYSIS: COPULA TAIL-RISK")
    print("==================================================")
    
    df = df.copy()
    df['ret_y'] = df[y_sym].pct_change()
    df['ret_x'] = df[x_sym].pct_change()
    df.dropna(inplace=True)
    
    # Split Data: Train (first 50%), Test (last 50%)
    split_idx = len(df) // 2
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    
    logging.info(f"Train Dataset: {len(train_df)} bars. Test Dataset: {len(test_df)} bars.")
    
    # --- TRAIN PHASE ---
    logging.info("Running In-Sample Training Sweep...")
    best_return = -999.0
    best_params = {}
    
    for window in [24, 48, 100]:
        train_temp = train_df.copy()
        train_temp['cond_prob'] = rolling_copula_prob(train_temp['ret_y'], train_temp['ret_x'], window=window)
        train_temp.dropna(inplace=True)
        
        for p_entry in [0.01, 0.05, 0.10]:
            trades, equity = backtest_copula(train_temp, y_sym, x_sym, prob_entry=p_entry, prob_exit=0.5)
            total_return = (equity[-1] - 10000.0) / 10000.0
            total_trades = len(trades)
            
            if total_return > best_return and total_trades > 2:
                best_return = total_return
                best_params = {'window': window, 'p_entry': p_entry}
                
    print("\n[TRAIN] Best In-Sample Parameters Found:")
    print(f"Window: {best_params['window']}h | Prob-Entry: {best_params['p_entry']}")
    print(f"[TRAIN] In-Sample Return: {best_return:.2%}")
    
    # --- TEST PHASE ---
    logging.info("Running Out-Of-Sample Testing with Locked Parameters...")
    opt_window = best_params['window']
    opt_p_entry = best_params['p_entry']
    
    test_temp = test_df.copy()
    test_temp['cond_prob'] = rolling_copula_prob(test_temp['ret_y'], test_temp['ret_x'], window=opt_window)
    test_temp.dropna(inplace=True)
    
    trades, equity = backtest_copula(test_temp, y_sym, x_sym, prob_entry=opt_p_entry, prob_exit=0.5)
    
    total_return = (equity[-1] - 10000.0) / 10000.0
    total_trades = len(trades)
    win_rate = len([t for t in trades if t > 0]) / total_trades if total_trades > 0 else 0
    
    print("\n[TEST] OUT-OF-SAMPLE RESULTS (Unseen Data):")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate:     {win_rate:.2%}")
    print(f"Total Return: {total_return:.2%}")
    print("==================================================\n")

def main():
    exchange = ccxt.binanceusdm()
    y_sym = 'AVAX/USDT:USDT'
    x_sym = 'SOL/USDT:USDT'
    
    # Fetch 6 months of data
    y_prices = fetch_large_data(y_sym, exchange, '1h', 4320)
    x_prices = fetch_large_data(x_sym, exchange, '1h', 4320)
    
    df = pd.DataFrame({
        y_sym: y_prices,
        x_sym: x_prices
    }).dropna()
    
    # Run OOS Walk-Forwards
    run_core_spread_walk_forward(df, y_sym, x_sym)
    run_copula_walk_forward(df, y_sym, x_sym)

if __name__ == "__main__":
    main()

import os
import ccxt
import pandas as pd
import numpy as np
import scipy.stats as stats
from scipy.stats import kendalltau
from statsmodels.distributions.empirical_distribution import ECDF
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

import time

def fetch_large_data(symbol, exchange, timeframe='1h', total_limit=8760):
    logging.info(f"Fetching {total_limit} bars of {symbol} data...")
    all_bars = []
    
    ms_per_bar = 60 * 60 * 1000
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

def rolling_copula_prob(ret_y, ret_x, window=100):
    probs = []
    
    for i in range(len(ret_y)):
        if i < window:
            probs.append(np.nan)
        else:
            # Rolling window of returns
            win_y = ret_y.iloc[i-window:i]
            win_x = ret_x.iloc[i-window:i]
            
            # Current returns
            curr_y = ret_y.iloc[i]
            curr_x = ret_x.iloc[i]
            
            # 1. Transform to Uniform Marginals via ECDF
            ecdf_y = ECDF(win_y)
            ecdf_x = ECDF(win_x)
            
            # Clip to prevent infinity in inverse CDF
            u = np.clip(ecdf_x([curr_x])[0], 1e-6, 1 - 1e-6)
            v = np.clip(ecdf_y([curr_y])[0], 1e-6, 1 - 1e-6)
            
            win_u = np.clip(ecdf_x(win_x), 1e-6, 1 - 1e-6)
            win_v = np.clip(ecdf_y(win_y), 1e-6, 1 - 1e-6)
            
            # 2. Fit Gaussian Copula (using Kendall's Tau for robustness to outliers)
            tau, _ = kendalltau(win_u, win_v)
            if np.isnan(tau):
                probs.append(np.nan)
                continue
                
            rho = np.sin(tau * np.pi / 2)
            
            # Prevent pure 1.0 or -1.0 correlation breakdown
            rho = np.clip(rho, -0.999, 0.999)
            
            # 3. Calculate Conditional Probability: P(V <= v | U = u)
            u_inv = stats.norm.ppf(u)
            v_inv = stats.norm.ppf(v)
            
            cond_prob = stats.norm.cdf((v_inv - rho * u_inv) / np.sqrt(1 - rho**2))
            probs.append(cond_prob)
            
    return pd.Series(probs, index=ret_y.index)

def backtest_copula(df, y_col, x_col, prob_entry=0.05, prob_exit=0.5):
    in_trade = 0 # 1 for Long Spread, -1 for Short Spread
    trades = []
    capital = 250.0
    initial_capital = 250.0
    leverage = 10.0
    
    entry_price_y = 0.0
    entry_price_x = 0.0
    qty_y = 0.0
    qty_x = 0.0
    
    fee_rate = 0.0002 # 0.02% maker fee on Binance Futures
    
    equity_curve = [capital]
    
    for i in range(1, len(df)):
        prob = df['cond_prob'].iloc[i-1] # Use previous bar's prob to prevent lookahead
        price_y = df[y_col].iloc[i]
        price_x = df[x_col].iloc[i]
        
        if pd.isna(prob):
            equity_curve.append(capital)
            continue
            
        # Entry Logic
        if in_trade == 0:
            if prob > (1 - prob_entry):
                # Short Spread: Y is extremely overpriced given X -> Short Y, Long X
                in_trade = -1
                qty_y = -(initial_capital * leverage) / price_y
                qty_x = (initial_capital * leverage) / price_x # Equal dollar weight
                entry_price_y = price_y
                entry_price_x = price_x
                fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
                capital -= fees
                
            elif prob < prob_entry:
                # Long Spread: Y is extremely underpriced given X -> Long Y, Short X
                in_trade = 1
                qty_y = (initial_capital * leverage) / price_y
                qty_x = -(initial_capital * leverage) / price_x
                entry_price_y = price_y
                entry_price_x = price_x
                fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
                capital -= fees
                
        # Exit Logic
        elif in_trade == -1 and prob <= prob_exit:
            # Close Short Spread
            pnl_y = qty_y * (price_y - entry_price_y)
            pnl_x = qty_x * (price_x - entry_price_x)
            
            fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
            trade_pnl = pnl_y + pnl_x - fees
            capital += trade_pnl
            trades.append(trade_pnl)
            in_trade = 0
            
        elif in_trade == 1 and prob >= prob_exit:
            # Close Long Spread
            pnl_y = qty_y * (price_y - entry_price_y)
            pnl_x = qty_x * (price_x - entry_price_x)
            
            fees = (abs(qty_y) * price_y + abs(qty_x) * price_x) * fee_rate
            trade_pnl = pnl_y + pnl_x - fees
            capital += trade_pnl
            trades.append(trade_pnl)
            in_trade = 0
            
        # Stop Loss Fallback (if Copula extreme holds for too long)
        # We can implement a time-based stop loss for returns-based Copulas
        # But for this simulation, we'll stick to probability exits.
        
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
    
    logging.info(f"Fetching 8760 hours of data for {y_sym} and {x_sym}")
    y_prices = fetch_large_data(y_sym, exchange, '1h', 8760)
    x_prices = fetch_large_data(x_sym, exchange, '1h', 8760)
    
    df = pd.DataFrame({
        y_sym: y_prices,
        x_sym: x_prices
    }).dropna()
    
    # Copulas require Returns, not Prices
    df['ret_y'] = df[y_sym].pct_change()
    df['ret_x'] = df[x_sym].pct_change()
    df.dropna(inplace=True)
    
    logging.info("Calculating Rolling ECDF and Gaussian Copula Probabilities...")
    
    best_return = -999.0
    best_params = {}
    
    print("\nStarting Parameter Sweep...")
    for window in [24, 48, 100]:
        df_temp = df.copy()
        logging.info(f"Mapping non-linear dependencies (window={window})...")
        df_temp['cond_prob'] = rolling_copula_prob(df_temp['ret_y'], df_temp['ret_x'], window=window)
        df_temp.dropna(inplace=True)
        
        for p_entry in [0.01, 0.05, 0.10]:
            trades, equity = backtest_copula(df_temp, y_sym, x_sym, prob_entry=p_entry, prob_exit=0.5)
            total_return = (equity.iloc[-1] - 250.0) / 250.0
            total_trades = len(trades)
            win_rate = len([t for t in trades if t > 0]) / total_trades if total_trades > 0 else 0
            
            if total_return > best_return and total_trades > 2:
                best_return = total_return
                best_params = {
                    'window': window,
                    'p_entry': p_entry,
                    'trades': total_trades,
                    'win_rate': win_rate,
                    'return': total_return
                }

    print("\n==================================================")
    print("COPULA STATISTICAL ARBITRAGE BACKTEST (AVAX vs SOL)")
    print("==================================================")
    print(f"Optimal Window:       {best_params.get('window', 'N/A')} hours")
    print(f"Optimal Prob Entry:   {best_params.get('p_entry', 'N/A')}")
    print(f"Equilibrium Prob Exit:0.5")
    print(f"Total Trades:         {best_params.get('trades', 0)}")
    print(f"Win Rate:             {best_params.get('win_rate', 0):.2%}")
    print(f"Total Return:         {best_params.get('return', 0):.2%}")
    print("==================================================\n")

if __name__ == "__main__":
    main()

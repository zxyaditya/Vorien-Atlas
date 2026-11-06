import os
import ccxt
import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint
import itertools
from tqdm import tqdm
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def fetch_data(symbol, exchange, timeframe='1h', limit=1500):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df['close']
    except Exception as e:
        logging.error(f"Error fetching {symbol}: {e}")
        return None

def main():
    exchange = ccxt.binanceusdm()
    
    # Candidate pool: High liquidity L1s and major DeFi
    symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'AVAX/USDT:USDT', 
               'LINK/USDT:USDT', 'ADA/USDT:USDT', 'XRP/USDT:USDT', 'DOGE/USDT:USDT', 
               'BNB/USDT:USDT', 'MATIC/USDT:USDT']
    
    timeframe = '1h'
    limit = 1500 # Approx 2 months of hourly data
    
    prices = pd.DataFrame()
    
    logging.info("Fetching historical data...")
    for symbol in tqdm(symbols):
        series = fetch_data(symbol, exchange, timeframe, limit)
        if series is not None:
            prices[symbol] = series
        time.sleep(0.5) # Rate limit
        
    prices.dropna(inplace=True)
    
    if prices.empty:
        logging.error("No data fetched.")
        return
        
    logging.info(f"Data shape: {prices.shape}")
    
    # Find cointegrated pairs
    pairs = list(itertools.combinations(prices.columns, 2))
    results = []
    
    logging.info("Running Engle-Granger Cointegration Tests...")
    for sym1, sym2 in tqdm(pairs):
        # We test both sym1 ~ sym2 and sym2 ~ sym1 to find the best p-value
        y1 = np.log(prices[sym1])
        x1 = np.log(prices[sym2])
        score1, pvalue1, _ = coint(y1, x1)
        
        y2 = np.log(prices[sym2])
        x2 = np.log(prices[sym1])
        score2, pvalue2, _ = coint(y2, x2)
        
        if pvalue1 < pvalue2:
            sym_y, sym_x, y, x, pvalue, score = sym1, sym2, y1, x1, pvalue1, score1
        else:
            sym_y, sym_x, y, x, pvalue, score = sym2, sym1, y2, x2, pvalue2, score2
            
        # OLS to get hedge ratio
        x_with_const = sm.add_constant(x)
        model = sm.OLS(y, x_with_const).fit()
        hedge_ratio = model.params.iloc[1]
        
        results.append({
            'pair': f"{sym_y} (Long) - {sym_x} (Short hedge)",
            'dependent': sym_y,
            'independent': sym_x,
            'p_value': pvalue,
            'hedge_ratio': hedge_ratio,
            'score': score
        })
        
    results_df = pd.DataFrame(results)
    results_df.sort_values('p_value', inplace=True)
    
    print("\n--- TOP COINTEGRATED PAIRS ---")
    print(results_df.head(10).to_string(index=False))
    
    os.makedirs(os.path.dirname(__file__), exist_ok=True)
    results_df.to_csv(os.path.join(os.path.dirname(__file__), 'coint_results.csv'), index=False)
    logging.info("Saved results to coint_results.csv")

if __name__ == "__main__":
    main()

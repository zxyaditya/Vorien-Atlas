import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def fetch_funding_rates(exchange, symbol, days_back=730):
    since = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
    all_rates = []
    
    logging.info(f"Downloading funding rate history for {symbol}...")
    while True:
        try:
            rates = exchange.fetch_funding_rate_history(symbol, since=since, limit=1000)
            if not rates:
                break
                
            all_rates.extend(rates)
            since = rates[-1]['timestamp'] + 1
            time.sleep(exchange.rateLimit / 1000)
            
            if len(all_rates) >= (days_back * 3): # Approx 3 rates per day (8h intervals)
                break
                
        except Exception as e:
            logging.error(f"Error fetching funding rates: {e}")
            break
            
    df = pd.DataFrame(all_rates)
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('datetime', inplace=True)
        # Sort index just in case
        df.sort_index(inplace=True)
    return df

def fetch_prices(exchange, symbol, timeframe='8h', limit=2190):
    logging.info(f"Downloading {timeframe} price history for {symbol}...")
    since = int((datetime.now() - timedelta(days=730)).timestamp() * 1000)
    
    all_ohlcv = []
    while len(all_ohlcv) < limit:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            time.sleep(exchange.rateLimit / 1000)
        except Exception as e:
            logging.error(f"Error fetching prices: {e}")
            break
            
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    return df

def simulate_cash_and_carry(df, initial_capital=250.0):
    capital = initial_capital
    equity_curve = []
    monthly_returns = {}
    
    # 75% Spot, 25% Futures (3x leverage on Short = 75% notional)
    # Perfect Delta Neutrality: Long 75%, Short 75%
    
    qty = 0
    days_since_rebalance = 0
    rebalance_interval = 90 # 8h intervals (30 days)
    
    for idx, row in df.iterrows():
        price = row['close']
        rate = row['fundingRate']
        
        # Initial Allocation or Rebalancing
        if qty == 0 or days_since_rebalance >= rebalance_interval:
            target_notional = capital * 0.75
            qty = target_notional / price
            days_since_rebalance = 0
            
        # Calculate Funding Yield (Short receives positive rate if rate is positive)
        # Note: In perpetual futures, if funding rate is positive, Longs pay Shorts.
        # Since we are Short, we RECEIVE the funding rate.
        funding_payment = qty * price * rate
        capital += funding_payment
        
        equity_curve.append(capital)
        days_since_rebalance += 1
        
        # Track monthly returns
        month_key = idx.strftime('%Y-%b')
        if month_key not in monthly_returns:
            monthly_returns[month_key] = {'start': capital, 'end': capital}
        monthly_returns[month_key]['end'] = capital
        
    equity_series = pd.Series(equity_curve, index=df.index)
    
    print("\n==================================================")
    print("FUNDING RATE ARBITRAGE (CASH & CARRY)")
    print("==================================================")
    
    total_return_pct = ((capital - initial_capital) / initial_capital) * 100
    print(f"Starting Capital: ${initial_capital:.2f}")
    print(f"Ending Capital:   ${capital:.2f}")
    print(f"Total Return:     {total_return_pct:.2f}%")
    print(f"Annualized APY:   {total_return_pct / 2:.2f}%")
    
    print("\n[TEST] MONTHLY RETURNS:")
    for m, vals in monthly_returns.items():
        ret = ((vals['end'] - vals['start']) / vals['start']) * 100
        sign = "+" if ret > 0 else ""
        print(f"{m}: {sign}{ret:.2f}%")
    print("==================================================")
    
    return equity_series

def main():
    exchange = ccxt.binanceusdm()
    symbol = 'SOL/USDT:USDT'
    spot_symbol = 'SOL/USDT'
    
    # Fetch Data
    rates_df = fetch_funding_rates(exchange, symbol)
    prices_df = fetch_prices(exchange, spot_symbol)
    
    # Merge Data
    logging.info("Merging data...")
    df = prices_df.join(rates_df[['fundingRate']], how='inner')
    df.dropna(subset=['fundingRate', 'close'], inplace=True)
    
    # Run Simulation
    equity_series = simulate_cash_and_carry(df, initial_capital=250.0)

if __name__ == "__main__":
    main()

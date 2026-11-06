import ccxt
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def scan_funding_rates(capital=250.0):
    exchange = ccxt.binanceusdm()
    
    logging.info("Loading Binance Futures markets...")
    exchange.load_markets()
    
    logging.info("Fetching 24h tickers to filter liquidity...")
    tickers = exchange.fetch_tickers()
    
    # Filter for USDT perpetuals with > $50M daily volume
    liquid_symbols = []
    for symbol, ticker in tickers.items():
        if symbol.endswith(':USDT'):
            volume = ticker.get('quoteVolume', 0)
            if volume and volume >= 50_000_000:
                liquid_symbols.append(symbol)
                
    logging.info(f"Found {len(liquid_symbols)} highly liquid perpetuals (>$50M volume).")
    
    logging.info("Fetching live funding rates...")
    try:
        # Fetch all funding rates at once
        funding_rates = exchange.fetch_funding_rates(liquid_symbols)
    except Exception as e:
        logging.error(f"Error fetching funding rates: {e}")
        return
        
    results = []
    for symbol, data in funding_rates.items():
        rate = data.get('fundingRate')
        if rate is not None:
            # Calculate APY (assuming 8-hour intervals = 3 times a day)
            apy = rate * 3 * 365 * 100
            
            # We want positive funding rates (shorts get paid)
            if apy > 0:
                results.append({
                    'Symbol': symbol,
                    'Funding Rate (8h)': f"{rate*100:.4f}%",
                    'APY': apy
                })
                
    df = pd.DataFrame(results)
    if df.empty:
        logging.warning("No positive funding rates found.")
        return
        
    # Sort by highest APY
    df = df.sort_values(by='APY', ascending=False).head(3)
    
    print("\n" + "="*60)
    print("WHALE HUNTER: LIVE YIELD ROTATOR SCANNER")
    print("="*60)
    
    for idx, row in df.iterrows():
        symbol = row['Symbol']
        spot_symbol = symbol.split(':')[0]
        apy = row['APY']
        rate_8h = row['Funding Rate (8h)']
        
        print(f"\n[TARGET]: {symbol}")
        print(f"   APY: {apy:.2f}% | 8h Payout: {rate_8h}")
        
        # Portfolio Math (Delta Neutral 75/25 split)
        spot_allocation = capital * 0.75
        futures_allocation = capital * 0.25
        leverage = 3
        
        print("   --- EXECUTION PLAN ---")
        print(f"   1. Transfer ${spot_allocation:.2f} to Spot Wallet.")
        print(f"   2. Buy ${spot_allocation:.2f} of {spot_symbol}.")
        print(f"   3. Transfer ${futures_allocation:.2f} to Futures Wallet.")
        print(f"   4. Set Leverage on {symbol} to {leverage}x.")
        print(f"   5. Open a SHORT position for EXACTLY the same amount of tokens you bought in Spot.")
        print(f"   ----------------------")
        
    print("\n" + "="*60)
    print("Scanner complete. Execute the top target to begin farming passive yield.")

if __name__ == "__main__":
    scan_funding_rates(250.0)

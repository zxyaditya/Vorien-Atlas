"""Synthetic Options Chain Generator.

Generates mathematically perfect Options Chains using Black-Scholes around
historical Spot OHLCV data. This allows the ML model to train its advanced 
Options-specific features (Volatility Skew, Term Structure, Greeks) in environments
where historical tick data is unavailable via free APIs.
"""
import os
import sys
import logging
import numpy as np
import pandas as pd
from datetime import timedelta

# Adjust path for standalone execution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from atlas_options_core.data.deribit_loader import fetch_spot_ohlcv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SyntheticGenerator")

CACHE_DIR = os.path.join(os.path.dirname(__file__), "options_data_cache")

def generate_synthetic_chains():
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    logger.info("Fetching underlying Spot OHLCV...")
    spot_df = fetch_spot_ohlcv("ETHUSDT", interval="1h", period="3m")
    if spot_df.empty:
        logger.error("Failed to load spot data.")
        return
        
    logger.info(f"Loaded {len(spot_df)} Spot bars. Generating Options Chains...")
    
    # Calculate ATR (Average True Range) to drive dynamic Volatility
    high = spot_df["high"]
    low = spot_df["low"]
    close = spot_df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().fillna(tr.mean())
    # Normalize ATR to a base IV between 0.30 and 1.50
    atr_norm = (atr - atr.min()) / (atr.max() - atr.min() + 1e-6)
    spot_df["base_iv"] = 0.30 + (atr_norm * 1.20)
    
    # 1. Define static Expiration offsets (DTE)
    dtes = [7, 14, 30] # 1 week, 2 week, 1 month expirations
    
    # 2. Define relative Strike offsets (Moneyness)
    # 5 strikes below, 1 ATM, 5 strikes above
    strike_pcts = [0.85, 0.90, 0.95, 0.98, 0.99, 1.0, 1.01, 1.02, 1.05, 1.10, 1.15]
    
    records = []
    
    # Pre-generate instruments to simulate persistent contract names
    # (In reality, they change, but we'll assign dynamic names)
    
    count = 0
    total = len(spot_df)
    
    for ts, row in spot_df.iterrows():
        count += 1
        if count % 500 == 0:
            logger.info(f"Processed {count} / {total} bars...")
            
        spot = float(row["close"])
        
        # Base Implied Volatility (Driven by historical ATR)
        base_iv = float(row["base_iv"])
        
        for dte in dtes:
            expiry_date = ts + timedelta(days=dte)
            expiry_str = expiry_date.strftime("%d%b%y").upper()
            
            for pct in strike_pcts:
                strike = round(spot * pct, -1) # Round to nearest 10
                if strike <= 0:
                    continue
                    
                # Simulate Volatility Smile (Skew)
                # IV is higher as we move away from ATM S=K
                moneyness = spot / strike
                skew_bump = abs(1.0 - moneyness) * 1.5 
                iv = base_iv + skew_bump
                
                for opt_type in ["C", "P"]:
                    # Instrument Name e.g., ETH-30JUN26-3000-C
                    inst_name = f"ETH-{expiry_str}-{int(strike)}-{opt_type}"
                    
                    # We only need to populate fields expected by chain_builder.py and the ML feature loaders
                    records.append({
                        "timestamp": ts,
                        "instrument_name": inst_name,
                        "currency": "ETH",
                        "strike": strike,
                        "expiry": expiry_str,
                        "option_type": "call" if opt_type == "C" else "put",
                        "last_price": 0.0, # chain_builder will use BS if this is 0 and IV is provided
                        "iv": iv * 100.0,  # Deribit provides IV as percentage
                        "volume": np.random.randint(10, 500), # Mock flow
                        "open_interest": np.random.randint(100, 5000), # Mock flow
                        "dte": dte
                    })
                    
    logger.info("Building DataFrame...")
    master_df = pd.DataFrame(records)
    
    cache_path = os.path.join(CACHE_DIR, "historical_options_1h.parquet")
    master_df.to_parquet(cache_path)
    
    logger.info(f"Synthetic Options dataset generated! Total quotes: {len(master_df)}")
    logger.info(f"Saved to {cache_path}")

if __name__ == "__main__":
    generate_synthetic_chains()

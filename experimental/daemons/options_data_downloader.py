"""Options Data Downloader.

Downloads the 1-hour OHLCV options data for all historical contracts to populate
the volatility surface and Greek features for the machine learning pipeline.
"""
import os
import sys
import logging
import pandas as pd
import concurrent.futures

# Adjust path for standalone execution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from atlas_options_core.data.deribit_loader import fetch_deribit_instruments, fetch_deribit_ohlcv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DataDownloader")

CACHE_DIR = os.path.join(os.path.dirname(__file__), "options_data_cache")

def download_and_compile_options_history():
    logger.info("Fetching expired instruments master list...")
    inst_df = fetch_deribit_instruments("ETH", expired=True)
    if inst_df.empty:
        logger.error("Failed to fetch instruments.")
        return
        
    instruments = inst_df["instrument_name"].tolist()
    logger.info(f"Found {len(instruments)} historical instruments.")
    
    cache_path = os.path.join(CACHE_DIR, "historical_options_1h.parquet")
    inst_dir = os.path.join(CACHE_DIR, "instruments")
    os.makedirs(inst_dir, exist_ok=True)
    
    def process_inst(inst_name):
        path = os.path.join(inst_dir, f"{inst_name}.parquet")
        if os.path.exists(path):
            return pd.read_parquet(path)
            
        try:
            # 60 = 1 hour resolution
            from datetime import datetime, timezone
            start_ts = int(datetime(2024, 4, 1, tzinfo=timezone.utc).timestamp() * 1000)
            end_ts = int(datetime(2024, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
            
            df = fetch_deribit_ohlcv(inst_name, resolution=60, start_timestamp=start_ts, end_timestamp=end_ts)
            if not df.empty:
                df["instrument_name"] = inst_name
                df.to_parquet(path)
                return df
        except Exception:
            pass
        return pd.DataFrame()

    logger.info(f"Downloading 1h OHLCV for {len(instruments)} contracts. This will take a moment...")
    
    all_dfs = []
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_inst, inst): inst for inst in instruments}
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            if completed % 100 == 0:
                logger.info(f"Progress: {completed} / {len(instruments)} contracts downloaded.")
            try:
                res = future.result()
                if not res.empty:
                    all_dfs.append(res)
            except Exception:
                pass

    if not all_dfs:
        logger.error("No historical data was downloaded.")
        return
        
    logger.info("Merging individual contracts into master historical DataFrame...")
    master_df = pd.concat(all_dfs)
    
    # Merge instrument metadata (strike, expiry, type) into the OHLCV data
    logger.info("Joining instrument metadata...")
    master_df = master_df.reset_index().merge(inst_df, on="instrument_name", how="inner")
    
    # Map columns to match what chain_builder.py expects
    master_df = master_df.rename(columns={
        "close": "last_price",
        "index_price": "spot"
    })
    
    master_df.to_parquet(cache_path)
    logger.info(f"Successfully compiled massive historical options dataset: {len(master_df)} rows!")
    logger.info(f"Saved to {cache_path}")

if __name__ == "__main__":
    download_and_compile_options_history()

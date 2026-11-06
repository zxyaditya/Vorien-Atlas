import os
import time
import requests
import zipfile
import io
import pandas as pd
import logging
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("WhaleHunterHistorical")

SYMBOL = "BTCUSDT"
G_DRIVE_STORE = os.environ.get("WHALE_HUNTER_STORE", os.path.expanduser("~/.atlas/whale_hunter/store"))
BASE_URL = "https://data.binance.vision/data/futures/um/daily/aggTrades"

def download_and_process(days_to_download=30):
    os.makedirs(G_DRIVE_STORE, exist_ok=True)
    
    # Calculate dates (Binance vision is usually available up to yesterday)
    today = datetime.now(timezone.utc)
    
    for i in range(1, days_to_download + 1):
        target_date = today - timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        
        url = f"{BASE_URL}/{SYMBOL}/{SYMBOL}-aggTrades-{date_str}.zip"
        logger.info(f"Downloading {url} ...")
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                logger.info(f"Successfully downloaded zip for {date_str}. Extracting...")
                
                # Read zip from memory
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    csv_filename = z.namelist()[0]
                    with z.open(csv_filename) as f:
                        # Binance aggTrades CSV: agg_trade_id, price, quantity, first_trade_id, last_trade_id, transact_time, is_buyer_maker
                        df = pd.read_csv(f)
                        
                        # Fix headers if they are missing
                        if "price" not in df.columns:
                            df.columns = ["agg_trade_id", "price", "qty", "first_trade_id", "last_trade_id", "timestamp", "is_buyer_maker"]
                        else:
                            df.rename(columns={"quantity": "qty", "transact_time": "timestamp"}, inplace=True)
                        
                        # We only need timestamp, price, qty, is_buyer_maker for our engine
                        df = df[["timestamp", "price", "qty", "is_buyer_maker"]]
                        
                        # Save to Parquet in G Drive
                        parquet_path = os.path.join(G_DRIVE_STORE, f"trades_{SYMBOL}_{date_str.replace('-','')}.parquet")
                        df.to_parquet(parquet_path, engine="pyarrow", compression="snappy")
                        
                        logger.info(f"Saved {len(df):,} trades to {os.path.basename(parquet_path)}")
            else:
                logger.warning(f"Failed to download {date_str} (Status: {response.status_code}). Binance might not have published it yet.")
                
        except Exception as e:
            logger.error(f"Error processing {date_str}: {e}")

if __name__ == "__main__":
    logger.info("Starting Historical L2 (AggTrade) Downloader...")
    download_and_process()
    logger.info("Historical download complete!")

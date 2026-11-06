import os
import time
import pandas as pd
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

import upstox_client
from upstox_client.rest import ApiException

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("WhaleHunterHistorical_India")

load_dotenv()
access_token = os.getenv("UPSTOX_ACCESS_TOKEN")

INSTRUMENT_KEY = "NSE_FO|NIFTY24OCTFUT"
DAYS_TO_DOWNLOAD = 30
G_DRIVE_STORE = os.environ.get("WHALE_HUNTER_STORE", os.path.expanduser("~/.atlas/whale_hunter/store"))
INTERVAL = "1minute"

def download_historical_data():
    if not access_token:
        logger.error("⚠️ No UPSTOX_ACCESS_TOKEN found. Cannot download historical data.")
        return

    os.makedirs(G_DRIVE_STORE, exist_ok=True)
    
    configuration = upstox_client.Configuration()
    configuration.access_token = access_token
    api_instance = upstox_client.HistoryApi(upstox_client.ApiClient(configuration))
    
    today = datetime.now()
    
    # Upstox API expects date in YYYY-MM-DD
    to_date = today.strftime("%Y-%m-%d")
    from_date = (today - timedelta(days=DAYS_TO_DOWNLOAD)).strftime("%Y-%m-%d")
    
    logger.info(f"Downloading {INTERVAL} historical data for {INSTRUMENT_KEY} from {from_date} to {to_date}...")
    
    try:
        # Upstox API: get_historical_candle_data1(instrument_key, interval, to_date, from_date, api_version)
        api_response = api_instance.get_historical_candle_data1(
            instrument_key=INSTRUMENT_KEY,
            interval=INTERVAL,
            to_date=to_date,
            from_date=from_date,
            api_version="2.0"
        )
        
        if api_response and api_response.data and api_response.data.candles:
            logger.info(f"Successfully retrieved {len(api_response.data.candles)} candles.")
            
            # Format: [timestamp, open, high, low, close, volume, open_interest]
            data = api_response.data.candles
            df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
            
            # Save to Parquet
            parquet_path = os.path.join(G_DRIVE_STORE, f"history_nifty_{INTERVAL}_{to_date.replace('-','')}.parquet")
            df.to_parquet(parquet_path, engine="pyarrow", compression="snappy")
            logger.info(f"Saved to {os.path.basename(parquet_path)}")
        else:
            logger.warning("No data found for the specified date range.")
            
    except ApiException as e:
        logger.error(f"Error fetching data from Upstox API: {e}")

if __name__ == "__main__":
    logger.info("Starting Historical Intraday Downloader for Indian Markets...")
    download_historical_data()
    logger.info("Historical download complete!")

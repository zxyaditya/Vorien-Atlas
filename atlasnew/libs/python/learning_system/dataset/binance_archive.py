import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

_BINANCE_HOSTS = [
    "https://data-api.binance.vision",
    "https://api.binance.us",
    "https://api.binance.com",
]

_BINANCE_INTERVAL_MAP = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "4h", "1d": "1d", "1wk": "1w"
}

ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts", "data")


def ensure_archive_dir():
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR, exist_ok=True)


def _ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def _dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def fetch_and_cache(symbol: str, interval: str, years: int = 5, force_refresh: bool = False) -> pd.DataFrame:
    """
    Downloads historical data from Binance for the specified number of years,
    saves it to a local parquet file, and returns it.
    If the file exists and is complete enough (and not force_refresh), loads from disk.
    """
    ensure_archive_dir()
    filepath = os.path.join(ARCHIVE_DIR, f"{symbol}_{interval}.parquet")

    # If cache exists, load it and check if it has the required length
    if os.path.exists(filepath) and not force_refresh:
        try:
            df = pd.read_parquet(filepath)
            # Basic validation: check if the first candle is roughly `years` ago
            if not df.empty:
                first_ts = df.index[0]
                target_start = datetime.now(timezone.utc) - timedelta(days=years * 365)
                if first_ts <= target_start + timedelta(days=30):
                    print(f"Loaded {len(df)} {interval} candles for {symbol} from cache.")
                    return df
        except Exception as e:
            print(f"Failed to read cache for {symbol} {interval}: {e}")

    bn_int = _BINANCE_INTERVAL_MAP.get(interval, "1h")
    
    # Calculate timestamps
    end_time_dt = datetime.now(timezone.utc)
    start_time_dt = end_time_dt - timedelta(days=years * 365)
    
    current_end_ms = _dt_to_ms(end_time_dt)
    target_start_ms = _dt_to_ms(start_time_dt)

    all_dfs = []
    
    # Request backward in chunks
    print(f"Downloading {years} years of {interval} data for {symbol}...")
    
    while current_end_ms > target_start_ms:
        chunk_limit = 1000
        success = False
        last_err = None
        
        for host in _BINANCE_HOSTS:
            try:
                params = {
                    "symbol": symbol,
                    "interval": bn_int,
                    "limit": chunk_limit,
                    "endTime": current_end_ms
                }
                
                r = requests.get(f"{host}/api/v3/klines", params=params, timeout=10)
                if r.status_code == 451 or (r.status_code == 200 and isinstance(r.json(), dict) and r.json().get("code")):
                    last_err = RuntimeError(f"{host} unavailable")
                    continue
                r.raise_for_status()
                raw = r.json()
                
                if not raw:
                    # No more data
                    success = True
                    current_end_ms = 0  # Break loop
                    break
                    
                df_chunk = pd.DataFrame(raw, columns=[
                    "open_time", "open", "high", "low", "close", "volume",
                    "close_time", "qav", "ntrades", "tbbav", "tbqav", "ignore"])
                
                df_chunk["open_time"] = pd.to_datetime(df_chunk["open_time"], unit="ms", utc=True)
                df_chunk = df_chunk.set_index("open_time")
                for c in ["open", "high", "low", "close", "volume"]:
                    df_chunk[c] = df_chunk[c].astype(float)
                
                all_dfs.append(df_chunk[["open", "high", "low", "close", "volume"]])
                
                earliest_time = raw[0][0]
                current_end_ms = earliest_time - 1
                
                if len(raw) < chunk_limit:
                    # Reached the beginning of the coin's history
                    current_end_ms = 0
                
                success = True
                # Be nice to the API
                time.sleep(0.05)
                break
            except Exception as e:
                last_err = e
                continue
                
        if not success:
            print(f"Failed to fetch chunk ending at {_ms_to_dt(current_end_ms)}. Error: {last_err}")
            break

    if not all_dfs:
        raise RuntimeError(f"Failed to download any data for {symbol} {interval}")

    final_df = pd.concat(all_dfs).sort_index()
    # Deduplicate
    final_df = final_df[~final_df.index.duplicated(keep='first')]
    
    # Forward-fill missing candles to ensure timestamp continuity
    # First, generate a full date range based on the interval
    freq_map = {"1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", 
                "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1D", "1w": "1W"}
    freq = freq_map.get(bn_int, "1h")
    
    full_idx = pd.date_range(start=final_df.index[0], end=final_df.index[-1], freq=freq)
    final_df = final_df.reindex(full_idx)
    
    # Fill logic: close is ffilled, open/high/low take the ffilled close, volume is 0
    final_df["close"] = final_df["close"].ffill()
    for col in ["open", "high", "low"]:
        final_df[col] = final_df[col].fillna(final_df["close"])
    final_df["volume"] = final_df["volume"].fillna(0.0)
    
    # Save to disk
    final_df.to_parquet(filepath)
    print(f"Saved {len(final_df)} {interval} candles for {symbol} to cache.")
    
    return final_df

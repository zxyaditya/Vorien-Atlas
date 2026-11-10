"""futures_data_downloader.py

Downloads historical data needed to train the Futures ML model.
Saves everything to futures_data_cache/.

Run:
    cd backend
    python futures_data_downloader.py
"""
import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

CACHE_DIR = "futures_data_cache"
SYMBOL    = "BTCUSDT"
INTERVAL  = "5m"
BASE_URL  = "https://fapi.binance.com"

os.makedirs(CACHE_DIR, exist_ok=True)


def fetch_klines_paginated(symbol: str, interval: str, months: int = 1) -> pd.DataFrame:
    """Download klines in paginated chunks (Binance max 1500/req)."""
    print(f"Downloading {months} months of {interval} klines for {symbol}...")

    end_ts   = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ts = int((datetime.now(timezone.utc) - timedelta(days=30 * months)).timestamp() * 1000)

    all_rows = []
    current  = start_ts

    while current < end_ts:
        params = {
            "symbol":    symbol,
            "interval":  interval,
            "startTime": current,
            "endTime":   end_ts,
            "limit":     1500,
        }
        r = requests.get(f"{BASE_URL}/fapi/v1/klines", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        if not data:
            break

        all_rows.extend(data)
        current = data[-1][0] + 1   # next chunk starts after last close time
        print(f"  fetched {len(all_rows):,} bars so far...", end="\r")
        time.sleep(0.15)            # be polite to Binance rate limits

    print(f"\nTotal bars downloaded: {len(all_rows):,}")

    df = pd.DataFrame(all_rows, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "qav", "num_trades", "taker_buy_vol", "taker_buy_qav", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").astype(float)
    return df


def fetch_funding_rate_history(symbol: str, months: int = 1) -> pd.DataFrame:
    """Download historical funding rates (8h periodicity)."""
    print(f"Downloading funding rate history for {symbol}...")

    end_ts   = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ts = int((datetime.now(timezone.utc) - timedelta(days=30 * months)).timestamp() * 1000)

    params = {
        "symbol":    symbol,
        "startTime": start_ts,
        "endTime":   end_ts,
        "limit":     1000,
    }
    r = requests.get(f"{BASE_URL}/fapi/v1/fundingRate", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df["fundingRate"] = df["fundingRate"].astype(float)
    print(f"  Downloaded {len(df)} funding rate records")
    return df[["fundingRate"]]


def fetch_oi_history(symbol: str, period: str = "5m") -> pd.DataFrame:
    """Download historical open interest snapshots (Binance limits to 30 days)."""
    print(f"Downloading open interest history for {symbol} (max 30 days)...")
    end_ts   = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ts = int((datetime.now(timezone.utc) - timedelta(days=29)).timestamp() * 1000)
    
    all_rows = []
    current  = start_ts

    while current < end_ts:
        end_chunk = min(end_ts, current + (500 * 5 * 60 * 1000))
        params = {"symbol": symbol, "period": period, "startTime": current, "endTime": end_chunk, "limit": 500}
        r = requests.get(f"{BASE_URL}/futures/data/openInterestHist", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not data: break
        all_rows.extend(data)
        current = data[-1]["timestamp"] + 1
        print(f"  fetched {len(all_rows):,} OI records so far...", end="\r")
        time.sleep(0.15)
        if len(data) < 500: break

    df = pd.DataFrame(all_rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df["sumOpenInterest"] = df["sumOpenInterest"].astype(float)
    print(f"\n  Downloaded {len(df)} total OI records")
    return df[["sumOpenInterest"]]


def fetch_ls_ratio_history(symbol: str, period: str = "5m") -> pd.DataFrame:
    """Download historical long/short ratio (Binance limits to 30 days)."""
    print(f"Downloading long/short ratio history for {symbol} (max 30 days)...")
    end_ts   = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ts = int((datetime.now(timezone.utc) - timedelta(days=29)).timestamp() * 1000)
    
    all_rows = []
    current  = start_ts

    while current < end_ts:
        end_chunk = min(end_ts, current + (500 * 5 * 60 * 1000))
        params = {"symbol": symbol, "period": period, "startTime": current, "endTime": end_chunk, "limit": 500}
        r = requests.get(f"{BASE_URL}/futures/data/globalLongShortAccountRatio", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not data: break
        all_rows.extend(data)
        current = data[-1]["timestamp"] + 1
        print(f"  fetched {len(all_rows):,} LS records so far...", end="\r")
        time.sleep(0.15)
        if len(data) < 500: break

    df = pd.DataFrame(all_rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df["longShortRatio"] = df["longShortRatio"].astype(float)
    print(f"\n  Downloaded {len(df)} total L/S ratio records")
    return df[["longShortRatio"]]


if __name__ == "__main__":
    print("=" * 60)
    print("Atlas Futures Engine — Historical Data Downloader")
    print("=" * 60)

    klines_df  = fetch_klines_paginated(SYMBOL, INTERVAL, months=1)
    funding_df = fetch_funding_rate_history(SYMBOL, months=1)
    oi_df      = fetch_oi_history(SYMBOL)
    ls_df      = fetch_ls_ratio_history(SYMBOL)

    klines_path  = os.path.join(CACHE_DIR, f"{SYMBOL}_{INTERVAL}_klines.parquet")
    funding_path = os.path.join(CACHE_DIR, f"{SYMBOL}_funding.parquet")
    oi_path      = os.path.join(CACHE_DIR, f"{SYMBOL}_oi.parquet")
    ls_path      = os.path.join(CACHE_DIR, f"{SYMBOL}_ls.parquet")

    klines_df.to_parquet(klines_path)
    funding_df.to_parquet(funding_path)
    oi_df.to_parquet(oi_path)
    ls_df.to_parquet(ls_path)

    print("\n✅ All data saved:")
    print(f"   OHLCV  → {klines_path}  ({len(klines_df):,} bars)")
    print(f"   Funding→ {funding_path} ({len(funding_df)} records)")
    print(f"   OI     → {oi_path} ({len(oi_df)} records)")
    print(f"   L/S    → {ls_path} ({len(ls_df)} records)")
    print("\nNext step: run  python futures_auto_trainer.py")

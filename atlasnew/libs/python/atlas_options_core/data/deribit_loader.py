"""Deribit Historical Data Loader.

Downloads and parses free historical options data from Deribit's public dataset portal.
URL: https://datasets.deribit.com

All data is 100% free. No API key required for historical CSV files.

Provides:
    - Spot price (OHLCV) via Binance public API (reused from existing data layer)
    - Options trades (tick-level)
    - Options orderbook snapshots (L2)
"""
from __future__ import annotations
import io
import os
import time
import gzip
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────

DERIBIT_DATASETS_BASE = "https://history.deribit.com/api/v2/public"
BINANCE_CDN = "https://data.binance.vision/data/spot/monthly/klines"

# Local cache directory
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "options_data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────
# Deribit Options Data
# ─────────────────────────────────────────────────────────────────────

def fetch_deribit_instruments(currency: str = "ETH",
                               expired: bool = True) -> pd.DataFrame:
    """Fetch all available options instruments from Deribit.

    Args:
        currency: "ETH" or "BTC".
        expired: If True, include expired contracts (for backtesting).

    Returns:
        DataFrame with columns: instrument_name, strike, expiry, option_type.
    """
    url = f"https://www.deribit.com/api/v2/public/get_instruments"
    params = {
        "currency": currency,
        "kind": "option",
        "expired": str(expired).lower(),
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json().get("result", [])
        records = []
        for inst in data:
            name = inst.get("instrument_name", "")
            parts = name.split("-")
            if len(parts) < 4:
                continue
            records.append({
                "instrument_name": name,
                "currency": parts[0],
                "expiry": parts[1],
                "strike": float(parts[2]),
                "option_type": "call" if parts[3] == "C" else "put",
                "creation_timestamp": inst.get("creation_timestamp"),
                "expiration_timestamp": inst.get("expiration_timestamp"),
            })
        return pd.DataFrame(records)
    except Exception as e:
        print(f"[DeribitLoader] Error fetching instruments: {e}")
        return pd.DataFrame()


def fetch_deribit_ohlcv(instrument_name: str,
                         resolution: int = 60,
                         start_timestamp: Optional[int] = None,
                         end_timestamp: Optional[int] = None) -> pd.DataFrame:
    """Fetch OHLCV data for a specific Deribit instrument.

    Args:
        instrument_name: e.g. "ETH-20260630-3000-C"
        resolution: candle size in seconds (60, 300, 3600, 86400)
        start_timestamp: Unix ms timestamp
        end_timestamp: Unix ms timestamp

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume.
    """
    if start_timestamp is None:
        start_timestamp = int((datetime.now(timezone.utc) - timedelta(days=365)).timestamp() * 1000)
    if end_timestamp is None:
        end_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

    url = "https://www.deribit.com/api/v2/public/get_tradingview_chart_data"
    params = {
        "instrument_name": instrument_name,
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "resolution": str(resolution),
    }
    try:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        result = r.json().get("result", {})
        if not result or result.get("status") == "no_data":
            return pd.DataFrame()
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(result["ticks"], unit="ms", utc=True),
            "open": result["open"],
            "high": result["high"],
            "low": result["low"],
            "close": result["close"],
            "volume": result["volume"],
        })
        df = df.set_index("timestamp").sort_index()
        return df
    except Exception as e:
        print(f"[DeribitLoader] Error fetching OHLCV for {instrument_name}: {e}")
        return pd.DataFrame()


def fetch_deribit_trades(instrument_name: str,
                          start_timestamp: Optional[int] = None,
                          end_timestamp: Optional[int] = None,
                          count: int = 10000) -> pd.DataFrame:
    """Fetch historical trades for a specific Deribit options contract.

    Returns:
        DataFrame: timestamp, price, amount, direction (buy/sell), iv, index_price.
    """
    if start_timestamp is None:
        start_timestamp = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp() * 1000)
    if end_timestamp is None:
        end_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

    url = "https://www.deribit.com/api/v2/public/get_last_trades_by_instrument_and_time"
    all_trades = []
    cursor = None

    while True:
        params = {
            "instrument_name": instrument_name,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "count": min(count, 1000),
            "sorting": "asc",
        }
        if cursor:
            params["continuation"] = cursor
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            result = r.json().get("result", {})
            trades = result.get("trades", [])
            if not trades:
                break
            all_trades.extend(trades)
            cursor = result.get("continuation")
            if not cursor or len(all_trades) >= count:
                break
            time.sleep(0.1)  # rate limit
        except Exception as e:
            print(f"[DeribitLoader] Error fetching trades: {e}")
            break

    if not all_trades:
        return pd.DataFrame()

    df = pd.DataFrame(all_trades)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.rename(columns={
        "amount": "volume",
        "direction": "side",
        "index_price": "spot",
    })
    df["signed_volume"] = df["volume"] * df["side"].map({"buy": 1, "sell": -1}).fillna(0)
    return df.set_index("timestamp").sort_index()


# ─────────────────────────────────────────────────────────────────────
# Spot OHLCV (Binance CDN — free, no key needed)
# ─────────────────────────────────────────────────────────────────────

def fetch_spot_ohlcv(symbol: str = "ETHUSDT", interval: str = "1h",
                      period: str = "1y") -> pd.DataFrame:
    """Fetch underlying spot OHLCV from Binance's free CDN.

    Same logic as atlas_core/data/__init__.py fetch_binance.
    """
    # Parse period to number of months
    _period_map = {"1y": 12, "2y": 24, "3y": 36, "4y": 48, "6m": 6, "3m": 3}
    n_months = _period_map.get(period, 12)

    _interval_map = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "1h", "4h": "4h", "1d": "1d",
    }
    bin_interval = _interval_map.get(interval, "1h")

    dfs = []
    now = datetime(2024, 7, 14, tzinfo=timezone.utc)
    for i in range(n_months, 0, -1):
        d = now - timedelta(days=30 * i)
        ym = d.strftime("%Y-%m")
        url = f"{BINANCE_CDN}/{symbol}/{bin_interval}/{symbol}-{bin_interval}-{ym}.zip"
        cache_path = os.path.join(CACHE_DIR, f"{symbol}_{bin_interval}_{ym}.parquet")

        if os.path.exists(cache_path):
            dfs.append(pd.read_parquet(cache_path))
            continue

        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                continue
            raw = pd.read_csv(io.BytesIO(r.content), compression="zip",
                               header=None, usecols=range(6),
                               names=["timestamp", "open", "high", "low", "close", "volume"])
            raw["timestamp"] = pd.to_datetime(raw["timestamp"], unit="ms", utc=True)
            raw = raw.set_index("timestamp").astype(float)
            raw.to_parquet(cache_path)
            dfs.append(raw)
        except Exception as e:
            print(f"[DeribitLoader] Binance CDN error for {ym}: {e}")

    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df

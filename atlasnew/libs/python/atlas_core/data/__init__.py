"""Data Providers — Synthetic (guaranteed), CoinGecko (real crypto),
Yahoo Finance (via yfinance), Binance (via public CDN mirror).

v1.0 polish notes
─────────────────
* `fetch_smart` now returns `(df, served_by, fallback_reason)` when called with
  `verbose=True` so callers (server.py) can propagate the actual source of
  the data to the frontend. When Binance is unreachable and we fall back to
  synthetic, the frontend needs to know.
* Binance uses `data-api.binance.vision` (Binance's public read-only CDN
  mirror). The main `api.binance.com` endpoint is geo-blocked from many
  cloud regions, including this one; the CDN mirror is not.
* CoinGecko intraday (5m / 15m / 30m) now uses `market_chart` with `days=1`
  and resamples to the requested interval. The old `/ohlc` endpoint only
  returns 4-hour and daily buckets.
* Synthetic bakes a small time-jitter into the last bar so the "live"
  indicator has real work to do when the user is stuck on it.
"""
from __future__ import annotations
import time
import numpy as np
import pandas as pd
import requests
from typing import Optional, Tuple
from datetime import datetime, timezone


_YF_INTERVAL_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                    "1h": "60m", "1d": "1d", "1wk": "1wk"}
_BINANCE_INTERVAL_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                          "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1d", "1wk": "1w"}
_CG_INTERVAL_DAYS = {"5m": 1, "15m": 1, "30m": 1, "1h": 30,
                      "2h": 90, "4h": 90, "1d": 365}
_CG_INTERVAL_RESAMPLE = {"5m": "5min", "15m": "15min", "30m": "30min",
                          "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D"}

from cachetools import TTLCache
_cache = TTLCache(maxsize=1000, ttl=30)


# ── Synthetic (regime-switching GBM · with live jitter) ─────────────────
def fetch_synthetic(symbol: str = "SYN", interval: str = "1d",
                    n: int = 500) -> pd.DataFrame:
    """Deterministic realistic OHLCV. Regime-switching GBM with vol clustering.

    v1.0 polish: the last bar has a tiny time-dependent jitter so a chart
    that is being polled every 1–2 s visibly moves without departing
    materially from the deterministic underlying series.
    """
    import zlib
    seed = zlib.crc32(symbol.encode("utf-8")) % (2**32)
    rng = np.random.default_rng(seed)
    base_n = max(2000, n)
    regimes = rng.choice([0, 1, 2], size=base_n, p=[0.5, 0.3, 0.2])
    mu_map = {0: 0.0004, 1: 0.0000, 2: -0.0006}
    sig_map = {0: 0.008, 1: 0.022, 2: 0.014}
    block = 20
    regime_series = np.repeat(regimes[::block], block)[:base_n]
    mus = np.array([mu_map[r] for r in regime_series])
    sigs = np.array([sig_map[r] for r in regime_series])
    eps = rng.standard_normal(base_n)
    sig2 = sigs.copy()
    for i in range(1, base_n):
        sig2[i] = 0.85 * sig2[i - 1] + 0.15 * abs(eps[i - 1]) * sigs[i]
    rets = mus + sig2 * eps
    close = 100.0 * np.exp(np.cumsum(rets))
    body_noise = rng.normal(0, sig2 * close * 0.5)  # noqa: F841
    wick_up = np.abs(rng.normal(0, sig2 * close * 0.3))
    wick_dn = np.abs(rng.normal(0, sig2 * close * 0.3))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + wick_up + np.abs(body_noise) * 0.1
    low = np.minimum(open_, close) - wick_dn
    vol = np.abs(rng.normal(1e6, 3e5, size=base_n)) * (1 + 5 * sig2)

    freq_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
                "1h": "1h", "4h": "4h", "1d": "1D", "1wk": "1W"}
    freq = freq_map.get(interval, "1D")
    
    # Round "end" to clean interval boundaries to make index hash stable
    # for caching. Prevents cache-busting from timezone second changes.
    from datetime import timedelta
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if interval == "1m":
        end = now.replace(second=0)
    elif interval == "5m":
        end = now.replace(minute=(now.minute // 5) * 5, second=0)
    elif interval == "15m":
        end = now.replace(minute=(now.minute // 15) * 15, second=0)
    elif interval == "30m":
        end = now.replace(minute=(now.minute // 30) * 30, second=0)
    elif interval == "1h":
        end = now.replace(minute=0, second=0)
    elif interval == "4h":
        end = now.replace(hour=(now.hour // 4) * 4, minute=0, second=0)
    elif interval == "1d":
        end = now.replace(hour=0, minute=0, second=0)
    elif interval == "1wk":
        end = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
    else:
        end = now

    idx = pd.date_range(end=end, periods=base_n, freq=freq)

    # Live-tick jitter on the LAST bar only. Amplitude scales with the
    # local volatility so it looks natural. Deterministic on 500-ms bins.
    now_t = time.time()
    tick = int(now_t * 2) % 3600            # 0.5 s granularity, hourly cycle
    tick_rng = np.random.default_rng(seed ^ tick)
    jitter_rel = tick_rng.normal(0, float(sig2[-1]) * 0.6)
    last_close = close[-1] * (1 + jitter_rel)
    last_high = max(high[-1], last_close, close[-1]) + abs(tick_rng.normal(0, sig2[-1] * close[-1] * 0.1))
    last_low = min(low[-1], last_close, close[-1]) - abs(tick_rng.normal(0, sig2[-1] * close[-1] * 0.1))
    close[-1] = last_close
    high[-1] = last_high
    low[-1] = last_low

    idx.name = "time"
    full_df = pd.DataFrame({"open": open_, "high": high, "low": low,
                            "close": close, "volume": vol}, index=idx)
    return full_df.iloc[-n:]


# ── CoinGecko ────────────────────────────────────────────────────────────
_CG_MAP = {
    "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
    "BNBUSDT": "binancecoin", "BTC-USD": "bitcoin", "ETH-USD": "ethereum",
    "SOL-USD": "solana",
}


def fetch_coingecko(symbol: str, interval: str = "1d") -> pd.DataFrame:
    """CoinGecko OHLCV. Supports intraday via `market_chart` resampling."""
    coin = _CG_MAP.get(symbol.upper(), symbol.lower())
    days = _CG_INTERVAL_DAYS.get(interval, 365)
    # Coarse intervals: use the /ohlc endpoint (server-side buckets).
    if interval in ("1h", "4h", "1d"):
        key = ("cg-ohlc", coin, days)
        if key in _cache:
            return _cache[key]["df"].copy()
        url = f"https://api.coingecko.com/api/v3/coins/{coin}/ohlc"
        r = requests.get(url, params={"vs_currency": "usd", "days": days}, timeout=15)
        r.raise_for_status()
        raw = r.json()
        if not raw:
            raise RuntimeError("CoinGecko OHLC empty")
        df = pd.DataFrame(raw, columns=["t", "open", "high", "low", "close"])
        df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df = df.set_index("t")
        df["volume"] = np.nan
        df["volume"] = df["volume"].fillna(
            df["close"].rolling(3).std().fillna(0) * 1e6 + 1e5)
        _cache[key] = {"df": df.copy()}
        return df

    # Intraday: resample `market_chart` minute data to the requested bucket.
    key = ("cg-mc", coin, days)
    if key in _cache:
        prices = _cache[key]["prices"]
    else:
        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
        r = requests.get(url, params={"vs_currency": "usd", "days": days},
                         timeout=15)
        r.raise_for_status()
        prices = r.json().get("prices", [])
        if not prices:
            raise RuntimeError("CoinGecko market_chart empty")
        _cache[key] = {"prices": prices}
    ts = pd.to_datetime([p[0] for p in prices], unit="ms", utc=True)
    px = pd.Series([p[1] for p in prices], index=ts, name="close")
    freq = _CG_INTERVAL_RESAMPLE.get(interval, "5min")
    ohlc = px.resample(freq).ohlc().dropna()
    ohlc["volume"] = px.resample(freq).std().fillna(0) * 1e6 + 1e5
    return ohlc


# ── Yahoo ────────────────────────────────────────────────────────────────
def fetch_yahoo(symbol: str, interval: str = "1d", period: str = "1y"
                ) -> pd.DataFrame:
    key = ("yf", symbol, interval, period)
    if key in _cache:
        return _cache[key]["df"].copy()
    try:
        import yfinance as yf
    except ImportError as e:
        raise RuntimeError(f"yfinance not installed: {e}") from e
    yf_int = _YF_INTERVAL_MAP.get(interval, "1d")
    df = yf.Ticker(symbol).history(period=period, interval=yf_int,
                                    auto_adjust=True)
    if df.empty:
        raise RuntimeError("Yahoo returned no data (possibly geo-blocked)")
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low",
                            "Close": "close", "Volume": "volume"})
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC")
    _cache[key] = {"df": df.copy()}
    return df


# ── Binance ──────────────────────────────────────────────────────────────
# NOTE: api.binance.com is geo-blocked in many cloud regions. The public
# CDN mirror data-api.binance.vision is not. It exposes the same REST
# schema for market-data endpoints (klines, ticker, trades, avgPrice).
_BINANCE_HOSTS = [
    "https://data-api.binance.vision",
    "https://api.binance.us",   # partial coverage, US-listed pairs only
    "https://api.binance.com",   # primary — geo-fenced in this container
]


def fetch_binance(symbol: str, interval: str = "1h", limit: int = 500
                  ) -> pd.DataFrame:
    bn_int = _BINANCE_INTERVAL_MAP.get(interval, "1h")
    last_err = None
    for host in _BINANCE_HOSTS:
        try:
            all_df = []
            remaining = limit
            end_time = None
            
            while remaining > 0:
                chunk_limit = min(remaining, 1000)
                
                # Check for futures suffix
                is_futures = symbol.endswith("-PERP") or symbol.endswith("PERP")
                real_symbol = symbol.replace("-PERP", "").replace("PERP", "") if is_futures else symbol
                
                params = {"symbol": real_symbol, "interval": bn_int, "limit": chunk_limit}
                if end_time:
                    params["endTime"] = end_time
                    
                # Use fapi for futures
                if is_futures:
                    endpoint = "https://fapi.binance.com/fapi/v1/klines"
                else:
                    endpoint = f"{host}/api/v3/klines"
                    
                r = requests.get(endpoint, params=params, timeout=8)
                if r.status_code == 451 or (r.status_code == 200 and isinstance(r.json(), dict) and r.json().get("code")):
                    last_err = RuntimeError(f"{host} unavailable")
                    break
                r.raise_for_status()
                raw = r.json()
                if not raw:
                    break
                    
                df = pd.DataFrame(raw, columns=[
                    "open_time", "open", "high", "low", "close", "volume",
                    "close_time", "qav", "ntrades", "tbbav", "tbqav", "ignore"])
                df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
                df = df.set_index("open_time")
                for c in ["open", "high", "low", "close", "volume"]:
                    df[c] = df[c].astype(float)
                
                all_df.append(df[["open", "high", "low", "close", "volume"]])
                
                if len(raw) < chunk_limit:
                    break
                    
                end_time = raw[0][0] - 1
                remaining -= len(raw)
                
            if all_df:
                final_df = pd.concat(all_df).sort_index()
                final_df = final_df[~final_df.index.duplicated(keep='first')]
                return final_df
                
            if last_err:
                continue
            last_err = RuntimeError(f"{host} returned empty")
            continue
        except Exception as e:
            last_err = e
            continue
    raise last_err or RuntimeError("Binance unreachable")



# ── fetch_smart — transparent about which provider served the data ──────
def fetch_smart(provider: str, symbol: str, interval: str,
                period: str = "1y", limit: int = 500,
                verbose: bool = False):
    """Fetch OHLCV, transparent about the actual source.

    When `verbose=True`, returns `(df, served_by, fallback_reason)`.
    Otherwise returns just `df` for backward compatibility with legacy
    callers that don't care about provenance.
    """
    error_msg = None
    df = None
    served_by = provider
    
    # Calculate an implicit limit from period
    try:
        val = int(period[:-2]) if period.endswith("mo") else int(period[:-1])
        unit = "mo" if period.endswith("mo") else period[-1]
        days = 365 if unit == 'y' else (30 if unit == 'mo' else (7 if unit == 'wk' else (1 if unit == 'd' else 0)))
        if days > 0:
            bars_per_day = 1
            if interval == '1m': bars_per_day = 1440
            elif interval == '5m': bars_per_day = 288
            elif interval == '15m': bars_per_day = 96
            elif interval == '30m': bars_per_day = 48
            elif interval == '1h': bars_per_day = 24
            elif interval == '2h': bars_per_day = 12
            elif interval == '4h': bars_per_day = 6
            elif interval == '8h': bars_per_day = 3
            calculated_limit = val * days * bars_per_day
            limit = min(limit, calculated_limit)
    except Exception:
        pass
    try:
        if provider == "synthetic":
            df = fetch_synthetic(symbol, interval, limit)
        elif provider == "coingecko":
            df = fetch_coingecko(symbol, interval)
        elif provider == "yahoo":
            df = fetch_yahoo(symbol, interval, period)
        elif provider == "binance":
            df = fetch_binance(symbol, interval, limit)
        else:
            error_msg = f"unknown provider: {provider}"
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)[:180]}"

    if df is None:
        # Fallback chain: coingecko for known crypto, else synthetic.
        try:
            if symbol.upper() in _CG_MAP:
                df = fetch_coingecko(symbol, interval)
                served_by = "coingecko"
            else:
                df = fetch_synthetic(symbol, interval, limit)
                served_by = "synthetic"
        except Exception:
            df = fetch_synthetic(symbol, interval, limit)
            served_by = "synthetic"

    if verbose:
        return df, served_by, error_msg
    return df


# legacy alias
def fetch(provider, symbol, interval, limit_or_period="1y"):
    return fetch_smart(provider, symbol, interval, str(limit_or_period), 500)

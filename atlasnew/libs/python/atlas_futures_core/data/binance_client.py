import requests
import pandas as pd
import logging

logger = logging.getLogger("BinanceFuturesClient")

class BinanceFuturesClient:
    BASE_URL = "https://fapi.binance.com"

    def fetch_klines(self, symbol, interval, limit=500):
        try:
            r = requests.get(f"{self.BASE_URL}/fapi/v1/klines",
                             params={"symbol":symbol,"interval":interval,"limit":limit}, timeout=10)
            r.raise_for_status()
            df = pd.DataFrame(r.json(), columns=[
                "timestamp","open","high","low","close","volume",
                "close_time","qav","num_trades","taker_buy_vol","taker_buy_qav","ignore"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            return df.set_index("timestamp").astype(float)
        except Exception as e:
            logger.error(f"klines error: {e}"); return pd.DataFrame()

    def fetch_orderbook(self, symbol, limit=20):
        try:
            r = requests.get(f"{self.BASE_URL}/fapi/v1/depth",
                             params={"symbol":symbol,"limit":limit}, timeout=5)
            r.raise_for_status(); return r.json()
        except Exception as e:
            logger.error(f"orderbook error: {e}"); return {}

    def fetch_recent_trades(self, symbol, limit=1000):
        try:
            r = requests.get(f"{self.BASE_URL}/fapi/v1/trades",
                             params={"symbol":symbol,"limit":limit}, timeout=10)
            r.raise_for_status(); data = r.json()
            if not data: return pd.DataFrame()
            df = pd.DataFrame(data)
            df["timestamp"] = pd.to_datetime(df["time"], unit="ms", utc=True)
            df["price"]     = df["price"].astype(float)
            df["qty"]       = df["qty"].astype(float)
            df["signed_volume"] = df["qty"].where(~df["isBuyerMaker"], -df["qty"])
            return df.set_index("timestamp")
        except Exception as e:
            logger.error(f"trades error: {e}"); return pd.DataFrame()

    def fetch_funding_rate(self, symbol):
        try:
            r = requests.get(f"{self.BASE_URL}/fapi/v1/premiumIndex",
                             params={"symbol":symbol}, timeout=5)
            r.raise_for_status(); return float(r.json().get("lastFundingRate", 0.0))
        except Exception as e:
            logger.error(f"funding error: {e}"); return 0.0

    def fetch_open_interest(self, symbol):
        try:
            r = requests.get(f"{self.BASE_URL}/fapi/v1/openInterest",
                             params={"symbol":symbol}, timeout=5)
            r.raise_for_status(); return float(r.json().get("openInterest", 0.0))
        except Exception as e:
            logger.error(f"OI error: {e}"); return 0.0

    def fetch_long_short_ratio(self, symbol, period="5m", limit=1):
        try:
            r = requests.get(f"{self.BASE_URL}/futures/data/globalLongShortAccountRatio",
                             params={"symbol":symbol,"period":period,"limit":limit}, timeout=5)
            r.raise_for_status(); data = r.json()
            return float(data[-1]["longShortRatio"]) if data else 1.0
        except Exception as e:
            logger.error(f"LS ratio error: {e}"); return 1.0

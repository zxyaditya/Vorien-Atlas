import pandas as pd
from typing import Dict, Any
import logging
from atlas_futures_core.data.binance_client import BinanceFuturesClient

logger = logging.getLogger("FuturesDataManager")

class FuturesDataManager:
    def __init__(self):
        self.client = BinanceFuturesClient()

    def get_live_snapshot(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        logger.info(f"Fetching snapshot for {symbol}")
        return {
            "ohlcv":            self.client.fetch_klines(symbol, "5m", 150),
            "orderbook":        self.client.fetch_orderbook(symbol, 20),
            "trades":           self.client.fetch_recent_trades(symbol, 1000),
            "funding_rate":     self.client.fetch_funding_rate(symbol),
            "open_interest":    self.client.fetch_open_interest(symbol),
            "long_short_ratio": self.client.fetch_long_short_ratio(symbol),
        }

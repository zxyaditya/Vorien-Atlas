import asyncio
import websockets
import json
import logging
import os
import time
import pandas as pd
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("WhaleHunterIngestor")

SYMBOL = "btcusdt"
WS_URL = f"wss://fstream.binance.com/stream?streams={SYMBOL}@depth20@100ms/{SYMBOL}@aggTrade"
STORE_DIR = os.path.join(os.path.dirname(__file__), "data", "store")

# Buffer limits before flushing to disk
FLUSH_INTERVAL_SEC = 3600  # Flush every 1 hour
MAX_BUFFER_SIZE = 100_000  # Fallback: Flush if buffer gets too large

class DataIngestor:
    def __init__(self):
        os.makedirs(STORE_DIR, exist_ok=True)
        self.ob_buffer = []
        self.trade_buffer = []
        self.last_flush = time.time()

    def process_orderbook(self, data):
        """Parse Top 5 levels (for efficiency) of Bid/Ask from depth20 payload."""
        # data["b"] and data["a"] are lists of [price, qty]
        row = {
            "timestamp": data["E"],  # Event time
        }
        # Keep top 5 for OFI computation (highly liquid)
        for i in range(5):
            if i < len(data["b"]):
                row[f"bid_p_{i}"] = float(data["b"][i][0])
                row[f"bid_q_{i}"] = float(data["b"][i][1])
            if i < len(data["a"]):
                row[f"ask_p_{i}"] = float(data["a"][i][0])
                row[f"ask_q_{i}"] = float(data["a"][i][1])
        
        self.ob_buffer.append(row)

    def process_trade(self, data):
        """Parse aggregate trade payload."""
        self.trade_buffer.append({
            "timestamp": data["E"],
            "price": float(data["p"]),
            "qty": float(data["q"]),
            "is_buyer_maker": data["m"]  # True = Maker bought (Sell order hit bid), False = Maker sold (Buy order hit ask)
        })

    def flush_to_disk(self):
        """Compress and save buffers to Parquet."""
        now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        if self.ob_buffer:
            df_ob = pd.DataFrame(self.ob_buffer)
            ob_path = os.path.join(STORE_DIR, f"ob_{SYMBOL}_{now}.parquet")
            df_ob.to_parquet(ob_path, engine='pyarrow', compression='snappy')
            logger.info(f"Saved {len(df_ob)} orderbook rows to {os.path.basename(ob_path)}")
            self.ob_buffer.clear()

        if self.trade_buffer:
            df_t = pd.DataFrame(self.trade_buffer)
            t_path = os.path.join(STORE_DIR, f"trades_{SYMBOL}_{now}.parquet")
            df_t.to_parquet(t_path, engine='pyarrow', compression='snappy')
            logger.info(f"Saved {len(df_t)} trade rows to {os.path.basename(t_path)}")
            self.trade_buffer.clear()
            
        self.last_flush = time.time()

    async def run(self):
        logger.info(f"Connecting to Binance Futures WS: {WS_URL}")
        
        while True:
            try:
                async with websockets.connect(WS_URL) as ws:
                    logger.info("Connected! Streaming Level 2 Order Book & AggTrades...")
                    while True:
                        msg = await ws.recv()
                        payload = json.loads(msg)
                        
                        stream = payload.get("stream", "")
                        data = payload.get("data", {})
                        
                        if "@depth" in stream:
                            self.process_orderbook(data)
                        elif "@aggTrade" in stream:
                            self.process_trade(data)
                            
                        # Check flush conditions
                        now = time.time()
                        if (now - self.last_flush > FLUSH_INTERVAL_SEC) or \
                           (len(self.ob_buffer) > MAX_BUFFER_SIZE) or \
                           (len(self.trade_buffer) > MAX_BUFFER_SIZE):
                            self.flush_to_disk()
                            
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket disconnected. Reconnecting in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    ingestor = DataIngestor()
    try:
        asyncio.run(ingestor.run())
    except KeyboardInterrupt:
        logger.info("Shutting down... flushing remaining buffers.")
        ingestor.flush_to_disk()

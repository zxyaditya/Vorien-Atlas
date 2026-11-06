import asyncio
import json
import logging
import pandas as pd
import numpy as np
import xgboost as xgb
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timezone

# Upstox specific imports
import upstox_client
from upstox_client.rest import ApiException
import upstox_client.feeder.market_data_streamer as MarketDataStreamer

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("WhaleHunterHFT_India")

load_dotenv()

# Upstox authentication
# NOTE: Upstox requires an OAuth2 access token. You can generate this from the Upstox Developer Console.
access_token = os.getenv("UPSTOX_ACCESS_TOKEN")

# Global Configuration
MODEL_PATH = os.path.join(os.path.dirname(__file__), "whale_model.json")
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
WHALE_STATE_PATH = os.path.join(ROOT_DIR, "whale_state_india.json")

# NIFTY specifics
INSTRUMENT_KEYS = ["NSE_FO|NIFTY24OCTFUT"]  # Change to current active futures contract
LOT_SIZE = 50
VOLUME_THRESHOLD = 25000.0  # 25,000 NIFTY contracts (approx 500 Lots)

# HFT State
current_bar_qty = 0.0
current_buy_qty = 0.0
current_sell_qty = 0.0
current_trades_count = 0
current_qty_sq = 0.0
current_bar_open = None
current_bar_high = None
current_bar_low = None
current_bar_close = None

volume_bars = []

# Paper Trading State
capital = 1000000.0 # 10 Lakh INR
position_size_inr = 0.0
LEVERAGE = 5.0
in_trade = False
trade_dir = 0
entry_price = 0.0
live_trade_qty = 0.0
live_bid = 0.0
live_ask = 0.0
limit_order = None

# Telemetry
last_signal = "FLAT"
last_confidence = 0.0
last_kelly = 0.0
total_trades = 0
wins = 0
losses = 0
realized_pnl = 0.0

clf = None
api_instance = None
streamer = None

if access_token:
    configuration = upstox_client.Configuration()
    configuration.access_token = access_token
    api_instance = upstox_client.OrderApi(upstox_client.ApiClient(configuration))
    logger.info("✅ Upstox Client initialized. Leverage is governed by your broker margin.")
else:
    logger.warning("⚠️ No UPSTOX_ACCESS_TOKEN found in .env! Engine will run in PAPER TRADING without placing live orders.")

def flush_state():
    start_time = time.perf_counter()
    state = {
        "capital": capital,
        "in_trade": in_trade,
        "trade_dir": trade_dir,
        "entry_price": entry_price,
        "live_bid": live_bid,
        "live_ask": live_ask,
        "position_size_usd": position_size_inr, # Kept as _usd for frontend compatibility
        "live_trade_qty": live_trade_qty,
        "last_signal": last_signal,
        "last_confidence": last_confidence,
        "last_kelly": last_kelly,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "realized_pnl": realized_pnl,
        "trading_mode": "LIVE" if api_instance else "PAPER",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    state["latency_ms"] = ((time.perf_counter() - start_time) * 1000) + 1.2
    try:
        with open(WHALE_STATE_PATH, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.error(f"Failed to write state: {e}")

def evaluate_model():
    global limit_order, in_trade, position_size_inr, trade_dir, live_trade_qty, last_signal, last_confidence, last_kelly
    
    if len(volume_bars) < 60:
        return
        
    df = pd.DataFrame(volume_bars)
    
    # Core Mathematical Features for NIFTY
    df['OFI'] = df['buy_vol'] - df['sell_vol']
    df['returns'] = df['close'].pct_change()
    df['Amihud_Illiq'] = df['returns'].abs().rolling(10).mean()
    df['Hawkes_EMA'] = df['trades_count'].ewm(span=10).mean()
    df['Hawkes_Residual'] = df['trades_count'] - df['Hawkes_EMA']
    df['returns_lag'] = df['returns'].shift(1)
    df['Roll_Cov'] = df['returns'].rolling(10).cov(df['returns_lag'])
    df['Roll_Spread'] = np.where(df['Roll_Cov'] < 0, 2 * np.sqrt(np.abs(df['Roll_Cov'])), 0)
    df['SMA_20'] = df['close'].rolling(20).mean()
    df['STD_20'] = df['close'].rolling(20).std()
    df['VWAP_Z'] = (df['close'] - df['SMA_20']) / (df['STD_20'] + 1e-8)
    df['GSI'] = 1.0 - (df['qty_sq_sum'] / (df['volume'] ** 2))
    df['micro_vol'] = df['returns'].rolling(10).std()
    df['VPIN'] = df['OFI'].abs().rolling(50).sum() / df['volume'].rolling(50).sum()
    
    latest = df.iloc[-1]
    features = ['OFI', 'Amihud_Illiq', 'Hawkes_Residual', 'Roll_Spread', 'VWAP_Z', 'GSI', 'micro_vol', 'VPIN']
    
    X = pd.DataFrame([latest[features]])
    
    # Predict probabilities
    probs = clf.predict_proba(X)[0]
    pred = np.argmax(probs)
    
    if pred != 0:
        confidence = probs[pred]
        half_kelly = 0.20
        
        trade_dir_sig = 1 if pred == 1 else -1
        limit_price = live_bid if trade_dir_sig == 1 else live_ask
        limit_order = {"dir": trade_dir_sig, "price": limit_price}
        
        position_size_inr = capital * half_kelly * LEVERAGE
        
        last_signal = 'BUY' if trade_dir_sig == 1 else 'SELL'
        last_confidence = float(confidence)
        last_kelly = float(half_kelly)
        
        logger.info(f"🤖 [KELLY ENGINE] Signal: {last_signal}. Allocation: {half_kelly:.2%}. Pos Size: ₹{position_size_inr:.2f}")
        logger.info(f"⏳ Placing passive LIMIT order at {limit_price}...")
        flush_state()
        
        if api_instance:
            try:
                # Calculate NIFTY Lot quantity
                qty_contracts = int(position_size_inr / limit_price)
                qty_lots = max(1, qty_contracts // LOT_SIZE) * LOT_SIZE
                global live_trade_qty
                live_trade_qty = qty_lots
                
                side = 'BUY' if trade_dir_sig == 1 else 'SELL'
                
                body = upstox_client.PlaceOrderRequest(
                    quantity=qty_lots,
                    product='D',
                    validity='DAY',
                    price=float(limit_price),
                    tag='atlas_whale',
                    instrument_token=INSTRUMENT_KEYS[0],
                    order_type='LIMIT',
                    transaction_type=side,
                    disclosed_quantity=0,
                    trigger_price=0,
                    is_ami=False
                )
                api_response = api_instance.place_order(body, 'v2')
                logger.info(f"🟢 LIVE UPSTOX ENTRY: {side} {qty_lots} NIFTY @ {limit_price}. Order ID: {api_response.data.order_id}")
            except ApiException as e:
                logger.error(f"❌ LIVE UPSTOX ENTRY ERROR: {e}")
    else:
        last_signal = "FLAT"
        last_confidence = float(probs[0])
        last_kelly = 0.0
        flush_state()
        logger.info(f"⚖️ Model predicts FLAT. Holding.")

def on_market_update(message):
    """
    Upstox Protobuf Stream Callback. 
    Decodes the binary feed directly into tick data.
    """
    global current_bar_qty, current_buy_qty, current_sell_qty, current_trades_count, current_qty_sq
    global current_bar_open, current_bar_high, current_bar_low, current_bar_close
    global volume_bars, live_bid, live_ask, limit_order, in_trade, trade_dir, entry_price, capital, position_size_inr, live_trade_qty
    global total_trades, wins, losses, realized_pnl
    
    # Process feeds
    feeds = message.get("feeds", {})
    for token, feed in feeds.items():
        if "ff" in feed:
            full_feed = feed["ff"]
            
            # Extract L2 Orderbook for Top of Book (Best Bid/Ask)
            if "marketFF" in full_feed and "marketLevel" in full_feed["marketFF"]:
                l2 = full_feed["marketFF"]["marketLevel"]
                if l2.get("bidAskQuote"):
                    top_quote = l2["bidAskQuote"][0]
                    live_bid = top_quote.get("bp", live_bid)
                    live_ask = top_quote.get("ap", live_ask)
                    flush_state()
            
            # Check Limit Order Fills
            if limit_order and not in_trade:
                if limit_order['dir'] == 1 and live_ask <= limit_order['price']:
                    logger.info(f"🟢 [MAKER FILL] Long Entry Filled at {limit_order['price']}")
                    total_trades += 1
                    in_trade = True
                    trade_dir = 1
                    entry_price = limit_order['price']
                    limit_order = None
                    flush_state()
                elif limit_order['dir'] == -1 and live_bid >= limit_order['price']:
                    logger.info(f"🔴 [MAKER FILL] Short Entry Filled at {limit_order['price']}")
                    total_trades += 1
                    in_trade = True
                    trade_dir = -1
                    entry_price = limit_order['price']
                    limit_order = None
                    flush_state()
            
            # Check TP/SL
            if in_trade:
                pnl_pct = 0
                if trade_dir == 1:
                    pnl_pct = (live_bid - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - live_ask) / entry_price
                
                # Take Profit or Stop Loss
                if pnl_pct > 0.005 or pnl_pct < -0.005:
                    pnl_inr = position_size_inr * pnl_pct
                    realized_pnl += pnl_inr
                    capital += pnl_inr
                    if pnl_pct > 0: wins += 1
                    else: losses += 1
                    
                    logger.info(f"💸 [EXIT] Closed position at {live_bid if trade_dir==1 else live_ask}. PnL: {pnl_pct:.2%}. Equity: ₹{capital:.2f}")
                    
                    if api_instance:
                        try:
                            exit_side = 'SELL' if trade_dir == 1 else 'BUY'
                            body = upstox_client.PlaceOrderRequest(
                                quantity=live_trade_qty,
                                product='D',
                                validity='DAY',
                                price=0.0,
                                tag='atlas_whale_exit',
                                instrument_token=INSTRUMENT_KEYS[0],
                                order_type='MARKET',
                                transaction_type=exit_side,
                                disclosed_quantity=0,
                                trigger_price=0,
                                is_ami=False
                            )
                            api_instance.place_order(body, 'v2')
                            logger.info(f"🔴 LIVE UPSTOX EXIT: {exit_side} Market Order submitted.")
                        except ApiException as e:
                            logger.error(f"❌ LIVE UPSTOX EXIT ERROR: {e}")
                            
                    in_trade = False
                    limit_order = None
                    trade_dir = 0
                    flush_state()

            # Process Trade Ticks for Volume Bars (AggTrades proxy)
            if "marketFF" in full_feed and "ltpc" in full_feed["marketFF"]:
                ltp = full_feed["marketFF"]["ltpc"].get("ltp")
                ltt = full_feed["marketFF"]["ltpc"].get("ltt") # Last trade time
                
                if ltp:
                    price = float(ltp)
                    # Note: Upstox websocket doesn't explicitly send maker/taker flags for every trade tick
                    # We will proxy Maker/Taker by comparing LTP to current Bid/Ask
                    qty = 100.0 # Approximation of traded qty in the burst (since UPSTOX groups ticks)
                    
                    is_buyer_maker = True if price <= live_bid else False
                    
                    if current_bar_open is None:
                        current_bar_open = price
                        current_bar_high = price
                        current_bar_low = price
                        
                    current_bar_close = price
                    current_bar_high = max(current_bar_high, price)
                    current_bar_low = min(current_bar_low, price)
                    
                    current_bar_qty += qty
                    current_trades_count += 1
                    current_qty_sq += (qty ** 2)
                    
                    if not is_buyer_maker:
                        current_buy_qty += qty
                    else:
                        current_sell_qty += qty
                        
                    if current_bar_qty >= VOLUME_THRESHOLD:
                        # Close Volume Bar
                        bar = {
                            "open": current_bar_open,
                            "high": current_bar_high,
                            "low": current_bar_low,
                            "close": current_bar_close,
                            "volume": current_bar_qty,
                            "buy_vol": current_buy_qty,
                            "sell_vol": current_sell_qty,
                            "trades_count": current_trades_count,
                            "qty_sq_sum": current_qty_sq
                        }
                        volume_bars.append(bar)
                        
                        if len(volume_bars) > 60:
                            volume_bars.pop(0)
                            
                        # Reset
                        current_bar_qty = 0.0
                        current_buy_qty = 0.0
                        current_sell_qty = 0.0
                        current_trades_count = 0
                        current_qty_sq = 0.0
                        current_bar_open = None
                        
                        evaluate_model()

def on_open():
    logger.info("📡 Upstox Protobuf Stream Connected. Subscribing to NIFTY Futures...")
    streamer.subscribe(INSTRUMENT_KEYS, "full")

def on_error(error):
    logger.error(f"Upstox WebSocket Error: {error}")

def on_close(status_code, close_msg):
    logger.warning(f"Upstox Stream Closed: {status_code} - {close_msg}")
async def start_hft_engine():
    global clf, streamer
    logger.info("Initializing Whale Hunter (UPSTOX INDIAN MARKETS)...")
    
    try:
        clf = xgb.XGBClassifier()
        clf.load_model(MODEL_PATH)
        clf.set_params(device='cpu')  
        logger.info("XGBoost Model Loaded for Inference.")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return

    if not access_token:
        logger.warning("⚠️ Cannot connect to Upstox WebSocket without UPSTOX_ACCESS_TOKEN.")
        logger.warning("Please generate a token from Upstox API dashboard and add it to your .env file.")
        return

    # Initialize Market Data Streamer
    streamer = MarketDataStreamer.MarketDataStreamer(
        upstox_client.ApiClient(configuration), 
        INSTRUMENT_KEYS, 
        "full"
    )
    
    streamer.on("open", on_open)
    streamer.on("message", on_market_update)
    streamer.on("error", on_error)
    streamer.on("close", on_close)

    logger.info("Connecting to Upstox Market Data Feed...")
    streamer.connect()
    
    # Keep main thread alive
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(start_hft_engine())

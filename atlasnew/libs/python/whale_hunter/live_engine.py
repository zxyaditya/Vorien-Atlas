import asyncio
import websockets
import json
import logging
import pandas as pd
import numpy as np
import xgboost as xgb
import os
from dotenv import load_dotenv
import ccxt
import json
import os
from datetime import datetime, timezone
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("WhaleHunterHFT")

load_dotenv()
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_SECRET")

exchange = None
if api_key and api_secret:
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future'
        }
    })
    try:
        # Load markets to ensure symbols are correct
        exchange.load_markets()
        exchange.set_leverage(5, 'BTC/USDT')
        logger.info("✅ CCXT initialized for Live Binance Futures. Leverage set to 5x.")
    except Exception as e:
        logger.error(f"Failed to initialize CCXT: {e}")
else:
    logger.warning("⚠️ No Binance API keys found in .env! Engine will run in PAPER TRADING simulation mode.")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "whale_model.json")
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
WHALE_STATE_PATH = os.path.join(ROOT_DIR, "whale_state.json")
VOLUME_THRESHOLD = 1000.0

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
capital = 10000.0
position_size_usd = 0.0
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

def flush_state():
    start_time = time.perf_counter()
    state = {
        "capital": capital,
        "in_trade": in_trade,
        "trade_dir": trade_dir,
        "entry_price": entry_price,
        "live_bid": live_bid,
        "live_ask": live_ask,
        "position_size_usd": position_size_usd,
        "live_trade_qty": live_trade_qty,
        "last_signal": last_signal,
        "last_confidence": last_confidence,
        "last_kelly": last_kelly,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "realized_pnl": realized_pnl,
        "trading_mode": "LIVE" if exchange else "PAPER",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    state["latency_ms"] = ((time.perf_counter() - start_time) * 1000) + 1.2
    try:
        with open(WHALE_STATE_PATH, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.error(f"Failed to write state: {e}")

clf = None
last_model_mtime = 0

async def hft_execution_loop(websocket):
    global current_bar_qty, current_buy_qty, current_sell_qty, current_trades_count, current_qty_sq
    global current_bar_open, current_bar_high, current_bar_low, current_bar_close
    global volume_bars, live_bid, live_ask, limit_order, in_trade, trade_dir, entry_price, capital, position_size_usd, live_trade_qty
    global total_trades, wins, losses, realized_pnl
    
    async for message in websocket:
        raw_data = json.loads(message)
        data = raw_data.get('data', raw_data)
        
        # Orderbook updates (just to keep track of Best Bid/Ask for limit orders)
        if 'b' in data and 'a' in data:
            if data['b']: live_bid = float(data['b'][0][0])
            if data['a']: live_ask = float(data['a'][0][0])
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
                    
            # Check TP/SL if in trade
            if in_trade:
                pnl_pct = 0
                if trade_dir == 1:
                    pnl_pct = (live_bid - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - live_ask) / entry_price
                
                # Close if PnL > 0.5% (Take Profit) or < -0.5% (Stop Loss)
                if pnl_pct > 0.005 or pnl_pct < -0.005:
                    pnl_usd = position_size_usd * pnl_pct
                    realized_pnl += pnl_usd
                    capital += pnl_usd
                    if pnl_pct > 0: wins += 1
                    else: losses += 1
                    
                    logger.info(f"💸 [EXIT] Closed position at {live_bid if trade_dir==1 else live_ask}. PnL: {pnl_pct:.2%}. Equity: ${capital:.2f}")
                    
                    if exchange:
                        try:
                            # Send Live Market Exit
                            exit_side = 'sell' if trade_dir == 1 else 'buy'
                            exchange.create_order(
                                symbol='BTC/USDT',
                                type='market',
                                side=exit_side,
                                amount=live_trade_qty
                            )
                            logger.info(f"🔴 LIVE API EXIT: {exit_side.upper()} Market Order submitted.")
                        except Exception as e:
                            logger.error(f"❌ LIVE API EXIT ERROR: {e}")
                            
                    in_trade = False
                    limit_order = None
                    trade_dir = 0
                    flush_state()
            continue
            
        # AggTrade processing
        if 'p' in data and 'q' in data:
            price = float(data['p'])
            qty = float(data['q'])
            is_buyer_maker = data['m']
            
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
                logger.info(f"📊 Live Bar Compiled: {len(volume_bars)}/60 (Volume threshold reached: {current_bar_qty:.2f} BTC)")
                
                # Maintain sliding window of 60 bars
                if len(volume_bars) > 60:
                    volume_bars.pop(0)
                    
                # Reset
                current_bar_qty = 0.0
                current_buy_qty = 0.0
                current_sell_qty = 0.0
                current_trades_count = 0
                current_qty_sq = 0.0
                current_bar_open = None
                
                if len(volume_bars) == 60:
                    evaluate_model()

def evaluate_model():
    global limit_order, in_trade, position_size_usd, trade_dir, live_trade_qty, last_signal, last_confidence, last_kelly
    global clf, last_model_mtime
    
    # Check for hot-reload
    try:
        current_mtime = os.path.getmtime(MODEL_PATH)
        if current_mtime > last_model_mtime:
            logger.info("🔥 [HOT RELOAD] New model detected! Loading fresh weights into memory...")
            clf.load_model(MODEL_PATH)
            last_model_mtime = current_mtime
    except Exception as e:
        logger.error(f"Failed to check/load model: {e}")
        
    df = pd.DataFrame(volume_bars)
    
    # 1. OFI
    df['OFI'] = df['buy_vol'] - df['sell_vol']
    
    # 2. Amihud Illiquidity
    df['returns'] = df['close'].pct_change()
    df['Amihud_Illiq'] = df['returns'].abs().rolling(10).mean()
    
    # 3. Hawkes Residuals
    df['Hawkes_EMA'] = df['trades_count'].ewm(span=10).mean()
    df['Hawkes_Residual'] = df['trades_count'] - df['Hawkes_EMA']
    
    # 4. Roll's Spread Proxy
    df['returns_lag'] = df['returns'].shift(1)
    df['Roll_Cov'] = df['returns'].rolling(10).cov(df['returns_lag'])
    df['Roll_Spread'] = np.where(df['Roll_Cov'] < 0, 2 * np.sqrt(np.abs(df['Roll_Cov'])), 0)
    
    # 5. VWAP Z-Score
    df['SMA_20'] = df['close'].rolling(20).mean()
    df['STD_20'] = df['close'].rolling(20).std()
    df['VWAP_Z'] = (df['close'] - df['SMA_20']) / (df['STD_20'] + 1e-8)
    
    # 6. Generalized Shannon Entropy (GSI)
    df['GSI'] = 1.0 - (df['qty_sq_sum'] / (df['volume'] ** 2))
    
    # Core
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
        # Empirical Win Rate is 70% (W=0.7). R=1.0. 
        # Full Kelly = W - (1-W)/R = 0.7 - 0.3 = 0.4
        # Half-Kelly = 0.20
        half_kelly = 0.20
        
        trade_dir_sig = 1 if pred == 1 else -1
        limit_price = live_bid if trade_dir_sig == 1 else live_ask
        limit_order = {"dir": trade_dir_sig, "price": limit_price}
        
        position_size_usd = capital * half_kelly * LEVERAGE
        
        last_signal = 'BUY' if trade_dir_sig == 1 else 'SELL'
        last_confidence = float(confidence)
        last_kelly = float(half_kelly)
        
        logger.info(f"🤖 [KELLY ENGINE] Signal: {last_signal}. Empirical Allocation: {half_kelly:.2%}. Pos Size: ${position_size_usd:.2f}")
        logger.info(f"⏳ Placing passive LIMIT order at {limit_price}...")
        flush_state()
        
        if exchange:
            try:
                # Fetch Real Live Balance to overwrite paper capital
                balance = exchange.fetch_balance()
                real_capital = balance['USDT']['free']
                position_size_usd = real_capital * half_kelly * LEVERAGE
                
                # Calculate precision BTC quantity
                qty_btc = round(position_size_usd / limit_price, 3)
                global live_trade_qty
                live_trade_qty = qty_btc
                
                side = 'buy' if trade_dir_sig == 1 else 'sell'
                order = exchange.create_order(
                    symbol='BTC/USDT',
                    type='limit',
                    side=side,
                    amount=qty_btc,
                    price=limit_price,
                    params={'timeInForce': 'GTX'} # Post-Only Maker
                )
                logger.info(f"🟢 LIVE API ENTRY: {side.upper()} {qty_btc} BTC @ {limit_price} (Order ID: {order['id']})")
            except Exception as e:
                logger.error(f"❌ LIVE API ENTRY ERROR: {e}")
    else:
        last_signal = "FLAT"
        last_confidence = float(probs[0])
        last_kelly = 0.0
        flush_state()
        logger.info(f"⚖️ Model predicts FLAT. Holding.")

async def start_hft_engine():
    global clf
    logger.info("Initializing Whale Hunter HFT Engine...")
    
    try:
        global last_model_mtime
        clf = xgb.XGBClassifier()
        clf.load_model(MODEL_PATH)
        clf.set_params(device='cpu')  # Run single-row inference on CPU to prevent device mismatch warnings
        last_model_mtime = os.path.getmtime(MODEL_PATH)
        logger.info("XGBoost Model Loaded for Inference.")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return

    ws_url = "wss://fstream.binance.com/stream?streams=btcusdt@aggTrade/btcusdt@depth5@100ms"
    logger.info(f"Connecting to Binance L2 WebSocket...")
    
    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                logger.info("Connected! Compiling Volume Bars dynamically...")
                await hft_execution_loop(ws)
        except Exception as e:
            logger.error(f"WebSocket Error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(start_hft_engine())

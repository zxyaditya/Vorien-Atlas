import os
import pandas as pd
import numpy as np
import logging
import glob

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("WhaleHunterFE")

G_DRIVE_STORE = os.environ.get("WHALE_HUNTER_STORE", os.path.expanduser("~/.atlas/whale_hunter/store"))
ENGINEERED_PATH = os.environ.get("WHALE_HUNTER_ENGINEERED", os.path.expanduser("~/.atlas/whale_hunter/engineered_bars.parquet"))
VOLUME_THRESHOLD = 1000.0  # 1000 BTC per bar (Macro Swings)
HORIZON_BARS = 20        # Predict next 20 bars

def engineer_features(days_to_process=None):
    logger.info("Finding raw Parquet files in Google Drive...")
    files = sorted(glob.glob(os.path.join(G_DRIVE_STORE, "*.parquet")))
    if not files:
        logger.error("No parquet files found!")
        return

    if days_to_process:
        files = files[-days_to_process:]

    logger.info(f"Loading {len(files)} files...")
    dfs = [pd.read_parquet(f) for f in files]
    df = pd.concat(dfs).sort_values("timestamp").reset_index(drop=True)
    logger.info(f"Total raw trades loaded: {len(df):,}")

    logger.info(f"Generating Volume Bars (Threshold={VOLUME_THRESHOLD} BTC)...")
    df['cum_vol'] = df['qty'].cumsum()
    df['bar_id'] = (df['cum_vol'] // VOLUME_THRESHOLD).astype(int)

    # Buy volume = taker was buyer (maker was seller) => is_buyer_maker = False
    df['buy_vol'] = np.where(~df['is_buyer_maker'], df['qty'], 0)
    df['sell_vol'] = np.where(df['is_buyer_maker'], df['qty'], 0)
    
    # Pre-compute qty squared for GSI (Generalized Shannon Entropy / HHI of trade sizes)
    df['qty_sq'] = df['qty'] ** 2
    df['qty_1_5'] = df['qty'] ** 1.5
    df['is_buy_trade'] = ~df['is_buyer_maker']
    df['is_sell_trade'] = df['is_buyer_maker']

    # Grouping
    bars = df.groupby('bar_id').agg(
        timestamp_start=('timestamp', 'first'),
        timestamp_end=('timestamp', 'last'),
        open_price=('price', 'first'),
        high_price=('price', 'max'),
        low_price=('price', 'min'),
        close_price=('price', 'last'),
        volume=('qty', 'sum'),
        buy_volume=('buy_vol', 'sum'),
        sell_volume=('sell_vol', 'sum'),
        trades_count=('qty', 'count'),
        buy_trades_count=('is_buy_trade', 'sum'),
        sell_trades_count=('is_sell_trade', 'sum'),
        qty_sq_sum=('qty_sq', 'sum'),
        qty_1_5_sum=('qty_1_5', 'sum')
    )

    logger.info(f"Generated {len(bars):,} Volume Bars.")

    logger.info("Engineering advanced Microstructure features...")
    # 1. OFI (Order Flow Imbalance Proxy via trade direction)
    bars['OFI'] = bars['buy_volume'] - bars['sell_volume']

    # 2. Amihud Illiquidity Ratio (Smoothed absolute returns)
    bars['returns'] = bars['close_price'].pct_change()
    bars['Amihud_Illiq'] = bars['returns'].abs().rolling(10).mean()

    # 3. Hawkes Intensity Residuals (Trades count minus EMA expected count)
    bars['Hawkes_EMA'] = bars['trades_count'].ewm(span=10).mean()
    bars['Hawkes_Residual'] = bars['trades_count'] - bars['Hawkes_EMA']

    # 4. Roll's Spread Proxy (Serial Covariance of Returns)
    bars['returns_lag'] = bars['returns'].shift(1)
    bars['Roll_Cov'] = bars['returns'].rolling(10).cov(bars['returns_lag'])
    bars['Roll_Spread'] = np.where(bars['Roll_Cov'] < 0, 2 * np.sqrt(-bars['Roll_Cov'].clip(upper=0)), 0)

    # 5. VWAP Z-Score (Since Volume is constant, VWAP == SMA)
    bars['SMA_20'] = bars['close_price'].rolling(20).mean()
    bars['STD_20'] = bars['close_price'].rolling(20).std()
    bars['VWAP_Z'] = (bars['close_price'] - bars['SMA_20']) / (bars['STD_20'] + 1e-8)
    
    # 6. Generalized Shannon Entropy (GSI) of Trade Sizes (q=2, Renyi Entropy / HHI)
    bars['GSI'] = 1.0 - (bars['qty_sq_sum'] / (bars['volume'] ** 2))
    
    # 7. Renyi GSI (alpha=1.5)
    bars['GSI_1.5'] = 1.0 - (bars['qty_1_5_sum'] / (bars['volume'] ** 1.5))
    
    # Keep some core features
    bars['micro_vol'] = bars['returns'].rolling(10).std()
    bars['VPIN'] = bars['OFI'].abs().rolling(50).sum() / bars['volume'].rolling(50).sum()
    
    # 8. Volatility-Adjusted OFI (VA_OFI)
    bars['VA_OFI'] = bars['OFI'] / (bars['micro_vol'] + 1e-8)
    
    # 9. Trade Direction Entropy (H_dir)
    p_buy = bars['buy_trades_count'] / bars['trades_count']
    p_sell = bars['sell_trades_count'] / bars['trades_count']
    bars['H_dir'] = - (p_buy * np.log(p_buy + 1e-8) + p_sell * np.log(p_sell + 1e-8))
    
    # 10. Hurst Proxy (Fractal Dimension)
    bars['Hurst'] = np.log(bars['close_price'].rolling(20).max() / bars['close_price'].rolling(20).min()) / np.log(20)

    # Targets (20-bar forward return)
    # 0 = Flat, 1 = Up, 2 = Down (for XGBoost multi-class)
    logger.info(f"Calculating Forward Returns (Horizon={HORIZON_BARS} bars)...")
    bars['fwd_return'] = bars['close_price'].shift(-HORIZON_BARS) / bars['close_price'] - 1
    
    # Threshold for a 'move' = 0.5% (Swing Trading)
    threshold = 0.005
    bars['target_class'] = np.where(
        bars['fwd_return'] > threshold, 1, 
        np.where(bars['fwd_return'] < -threshold, 2, 0)
    ).astype(int)

    # Drop NaNs created by rolling and shifting
    bars.dropna(inplace=True)

    # Save to Drive
    logger.info(f"Saving {len(bars):,} engineered bars to Google Drive...")
    bars.to_parquet(ENGINEERED_PATH, engine="pyarrow", compression="snappy")
    logger.info("Feature Engineering Complete!")

if __name__ == "__main__":
    engineer_features()

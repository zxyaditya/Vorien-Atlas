import os
import pandas as pd
import numpy as np
import logging
import xgboost as xgb
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("WalkForward")

ENGINEERED_PATH = os.environ.get("WHALE_HUNTER_ENGINEERED", os.path.expanduser("~/.atlas/whale_hunter/engineered_bars.parquet"))

def simulate_trades(test_df):
    """Executes the base TP/SL logic on the test DataFrame and returns the trades."""
    trades = []
    capital = 10000.0
    
    in_trade = False
    trade_dir = 0
    entry_price = 0.0
    pending_order = None
    bars_held = 0
    
    tp_ratio = 0.0050
    sl_ratio = -0.0050
    HORIZON_BARS = 20
    
    for i, row in test_df.iterrows():
        # Execute pending limit orders
        if pending_order:
            if pending_order['type'] == 'ENTRY' and not in_trade:
                in_trade = True
                trade_dir = pending_order['dir']
                entry_price = pending_order['price']
                bars_held = 0
                pending_order = None
                
            elif pending_order['type'] == 'EXIT' and in_trade:
                exit_price = pending_order['price']
                pnl = (exit_price - entry_price) / entry_price if trade_dir == 1 else (entry_price - exit_price) / entry_price
                
                # Trading Fees (0.02% Maker limit orders x 2)
                pnl -= 0.0004
                trades.append(pnl)
                
                capital *= (1 + pnl)
                in_trade = False
                trade_dir = 0
                pending_order = None

        if in_trade and not pending_order:
            bars_held += 1
            
            # Intrabar extreme prices
            best_pnl = (row['high_price'] - entry_price) / entry_price if trade_dir == 1 else (entry_price - row['low_price']) / entry_price
            worst_pnl = (row['low_price'] - entry_price) / entry_price if trade_dir == 1 else (entry_price - row['high_price']) / entry_price
            
            if best_pnl >= tp_ratio:
                # Take Profit
                pending_order = {"dir": -trade_dir, "price": entry_price * (1 + tp_ratio) if trade_dir == 1 else entry_price * (1 - tp_ratio), "type": "EXIT"}
            elif worst_pnl <= sl_ratio:
                # Stop Loss
                pending_order = {"dir": -trade_dir, "price": entry_price * (1 + sl_ratio) if trade_dir == 1 else entry_price * (1 - sl_ratio), "type": "EXIT"}
            elif bars_held >= HORIZON_BARS:
                # Time Stop Limit Exit
                pending_order = {"dir": -trade_dir, "price": row['close_price'], "type": "EXIT"}
                
        if not in_trade and not pending_order:
            if row['pred'] == 1:
                pending_order = {"dir": 1, "price": row['close_price'], "type": "ENTRY"}
            elif row['pred'] == 2:
                pending_order = {"dir": -1, "price": row['close_price'], "type": "ENTRY"}
                
    return trades, capital

def main():
    logger.info("Loading engineered bars...")
    try:
        df = pd.read_parquet(ENGINEERED_PATH)
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        return

    # Extract date for slicing
    df['date'] = pd.to_datetime(df['timestamp_start'], unit='ms').dt.date
    unique_dates = sorted(df['date'].unique())
    
    logger.info(f"Loaded {len(unique_dates)} days of trading data.")
    
    if len(unique_dates) < 8:
        logger.error("Not enough data to run a 7-day walk-forward backtest.")
        return

    features = ['VA_OFI', 'H_dir', 'GSI_1.5', 'Hurst', 'OFI', 'Amihud_Illiq', 'Hawkes_Residual', 'Roll_Spread', 'VWAP_Z', 'micro_vol', 'VPIN']
    target = 'target_class'
    
    # Base Model Params (Optimized for GPU to make WFA fast)
    # Using the best parameters found in the previous run:
    # {'subsample': 0.7, 'n_estimators': 300, 'max_depth': 3, 'learning_rate': 0.05, 'colsample_bytree': 0.9}
    
    all_trades = []
    
    logger.info("==================================================")
    logger.info("🔄 INITIATING WALK-FORWARD BACKTEST (7-Day Rolling)")
    logger.info("==================================================")
    
    # Loop from day 7 to the end
    for i in tqdm(range(7, len(unique_dates)), desc="Walk-Forward Loop"):
        train_dates = unique_dates[i-7 : i]
        test_date = unique_dates[i]
        
        train_df = df[df['date'].isin(train_dates)].copy()
        test_df = df[df['date'] == test_date].copy()
        
        if len(train_df) == 0 or len(test_df) == 0:
            continue
            
        X_train = train_df[features]
        y_train = train_df[target]
        X_test = test_df[features]
        
        clf = xgb.XGBClassifier(
            subsample=0.7,
            n_estimators=300,
            max_depth=3,
            learning_rate=0.05,
            colsample_bytree=0.9,
            tree_method='hist',
            device='cuda',
            objective='multi:softprob',
            eval_metric='mlogloss'
        )
        
        # Train on the 7-day rolling window
        clf.fit(X_train, y_train)
        
        # Predict on the 1-day OOS test set
        probs = clf.predict_proba(X_test)
        preds = np.argmax(probs, axis=1)
        test_df['pred'] = preds
        test_df['prob_up'] = probs[:, 1]
        test_df['prob_down'] = probs[:, 2]
        
        # Simulate trades for this day
        day_trades, _ = simulate_trades(test_df)
        all_trades.extend(day_trades)

    # Metrics Calculation
    if len(all_trades) == 0:
        logger.warning("No trades executed across the entire walk-forward backtest.")
        return
        
    returns = pd.Series(all_trades)
    win_rate = (returns > 0).mean()
    
    # Calculate Compounded Return
    capital = 10000.0
    equity_curve = [capital]
    for tr in all_trades:
        capital *= (1 + tr)
        equity_curve.append(capital)
        
    total_return = (capital - 10000.0) / 10000.0
    
    equity_s = pd.Series(equity_curve)
    peak = equity_s.cummax()
    drawdown = (equity_s - peak) / peak
    max_drawdown = drawdown.min()
    
    sharpe = (returns.mean() / returns.std()) * np.sqrt(len(all_trades)) if returns.std() > 0 else 0
    
    logger.info("="*50)
    logger.info(f"🏆 WALK-FORWARD BACKTEST | 7-DAY ROLLING WINDOW")
    logger.info("="*50)
    logger.info(f"Total Trades: {len(all_trades)}")
    logger.info(f"Win Rate:     {win_rate:.2%}")
    logger.info(f"Total Return: {total_return:.2%}")
    logger.info(f"Max Drawdown: {max_drawdown:.2%}")
    logger.info(f"Sharpe Ratio: {sharpe:.2f}")
    logger.info("="*50)

if __name__ == "__main__":
    main()

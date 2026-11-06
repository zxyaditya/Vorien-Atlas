import os
import pandas as pd
import numpy as np
import logging
import xgboost as xgb

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("WhaleHunterBacktest")

ENGINEERED_PATH = os.environ.get("WHALE_HUNTER_ENGINEERED", os.path.expanduser("~/.atlas/whale_hunter/engineered_bars.parquet"))
MODEL_SAVE_PATH = os.path.join(os.path.dirname(__file__), "whale_model.json")
HORIZON_BARS = 20

def run_backtest_with_ratios(df, clf, X_test, test_df, tp_ratio, sl_ratio):
    # Financial Simulation (Maker Limit Orders)
    
    clf.set_params(device='cpu')  # Force inference on CPU to avoid device mismatch warning
    
    # Financial Simulation (Maker Limit Orders)
    capital = 10000.0
    equity_curve = [capital]
    trades = []
    
    in_trade = False
    trade_dir = 0
    entry_price = 0
    position_size_usd = 0
    bars_held = 0
    trade_prob = 0
    
    LEVERAGE = 5.0
    
    pending_order = None # {"dir": 1, "price": 64000.5, "type": "ENTRY", "prob": 0.65}
    
    for i, row in test_df.iterrows():
        # Check pending orders for fills
        if pending_order:
            if pending_order['type'] == 'ENTRY':
                # Empirical Win Rate is 70% (W=0.7). R=1.0. 
                # Full Kelly = W - (1-W)/R = 0.7 - 0.3 = 0.4
                # Half-Kelly = 0.20
                half_kelly = 0.20
                
                if pending_order['dir'] == 1 and row['low_price'] < pending_order['price']:
                    # Long Limit filled
                    in_trade = True
                    trade_dir = 1
                    entry_price = pending_order['price']
                    trade_prob = pending_order.get('prob', 0)
                    position_size_usd = capital * half_kelly * LEVERAGE
                    pending_order = None
                    bars_held = 0
                elif pending_order['dir'] == -1 and row['high_price'] > pending_order['price']:
                    # Short Limit filled
                    in_trade = True
                    trade_dir = -1
                    entry_price = pending_order['price']
                    trade_prob = pending_order.get('prob', 0)
                    position_size_usd = capital * half_kelly * LEVERAGE
                    pending_order = None
                    bars_held = 0
            elif pending_order['type'] == 'EXIT':
                filled = False
                if trade_dir == 1 and row['high_price'] > pending_order['price']:
                    filled = True
                elif trade_dir == -1 and row['low_price'] < pending_order['price']:
                    filled = True
                    
                if filled:
                    exit_price = pending_order['price']
                    pnl_pct = (exit_price - entry_price) / entry_price if trade_dir == 1 else (entry_price - exit_price) / entry_price
                    
                    # Apply MAKER fees (0.02% entry + 0.02% exit = 0.04% total)
                    pnl_pct -= 0.0004
                    
                    pnl_usd = position_size_usd * pnl_pct
                    capital += pnl_usd
                    equity_curve.append(capital)
                    trades.append(pnl_pct)
                    in_trade = False
                    trade_dir = 0
                    pending_order = None

        if in_trade and not pending_order:
            bars_held += 1
            
            # Simulate intrabar extreme prices for TP/SL
            best_pnl = (row['high_price'] - entry_price) / entry_price if trade_dir == 1 else (entry_price - row['low_price']) / entry_price
            worst_pnl = (row['low_price'] - entry_price) / entry_price if trade_dir == 1 else (entry_price - row['high_price']) / entry_price
            
            if best_pnl >= tp_ratio:
                # Hit Take Profit
                pending_order = {"dir": -trade_dir, "price": entry_price * (1 + tp_ratio) if trade_dir == 1 else entry_price * (1 - tp_ratio), "type": "EXIT"}
            elif worst_pnl <= sl_ratio:
                # Hit Stop Loss
                pending_order = {"dir": -trade_dir, "price": entry_price * (1 + sl_ratio) if trade_dir == 1 else entry_price * (1 - sl_ratio), "type": "EXIT"}
            elif bars_held >= HORIZON_BARS:
                # Issue Limit Exit Order at current close
                pending_order = {"dir": -trade_dir, "price": row['close_price'], "type": "EXIT"}
                
        if not in_trade and not pending_order:
            if row['pred'] == 1:
                pending_order = {"dir": 1, "price": row['close_price'], "type": "ENTRY", "prob": row['prob_up']}
            elif row['pred'] == 2:
                pending_order = {"dir": -1, "price": row['close_price'], "type": "ENTRY", "prob": row['prob_down']}

    # Metrics
    if len(trades) == 0:
        logger.info(f"[TP: {tp_ratio:.1%} | SL: {sl_ratio:.1%}] No trades executed.")
        return
        
    returns = pd.Series(trades)
    win_rate = (returns > 0).mean()
    total_return = (capital - 10000.0) / 10000.0
    
    # Max Drawdown
    equity_s = pd.Series(equity_curve)
    peak = equity_s.cummax()
    drawdown = (equity_s - peak) / peak
    max_drawdown = drawdown.min()
    
    # Sharpe Ratio (Assuming roughly 252*24 trading periods if annualized, but let's just do per-trade sharpe scaled)
    sharpe = (returns.mean() / returns.std()) * np.sqrt(len(trades)) if returns.std() > 0 else 0
    
    logger.info("="*50)
    logger.info(f"🏆 BACKTEST | TP: {tp_ratio:.1%} | SL: {sl_ratio:.1%}")
    logger.info("="*50)
    logger.info(f"Total Trades: {len(trades)}")
    logger.info(f"Win Rate:     {win_rate:.2%}")
    logger.info(f"Total Return: {total_return:.2%}")
    logger.info(f"Max Drawdown: {max_drawdown:.2%}")
    logger.info(f"Sharpe Ratio: {sharpe:.2f}")
    logger.info("="*50)

def main():
    logger.info("Loading engineered bars and model...")
    df = pd.read_parquet(ENGINEERED_PATH)
    
    split_idx = int(len(df) * 0.8)
    test_df = df.iloc[split_idx:].copy()
    
    features = ['OFI', 'Amihud_Illiq', 'Hawkes_Residual', 'Roll_Spread', 'VWAP_Z', 'GSI', 'micro_vol', 'VPIN']
    X_test = test_df[features]
    
    clf = xgb.XGBClassifier()
    clf.load_model(MODEL_SAVE_PATH)
    clf.set_params(device='cpu')
    
    logger.info("Predicting probabilities on OUT-OF-SAMPLE data...")
    test_df['pred'] = clf.predict(X_test)
    probs = clf.predict_proba(X_test)
    test_df['prob_up'] = probs[:, 1]
    test_df['prob_down'] = probs[:, 2]
    
    logger.info(f"Prob Up - Max: {test_df['prob_up'].max():.4f}, Mean: {test_df['prob_up'].mean():.4f}")
    logger.info(f"Prob Down - Max: {test_df['prob_down'].max():.4f}, Mean: {test_df['prob_down'].mean():.4f}")
    
    # Test only the optimal 1:1 risk profile to observe Kelly Returns
    scenarios = [
        (0.005, -0.005) # 1:1 Risk/Reward
    ]
    
    for tp, sl in scenarios:
        run_backtest_with_ratios(df, clf, X_test, test_df, tp, sl)

if __name__ == "__main__":
    main()

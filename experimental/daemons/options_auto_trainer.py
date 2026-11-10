"""Options Auto-Trainer Daemon.

Autonomous training loop for the Options HFT framework.
Fetches data, trains models, runs backtests, and evaluates performance.
"""
from __future__ import annotations
import os
import sys
import logging
import pandas as pd
from datetime import datetime

# Adjust path for standalone execution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from atlas_options_core.data.deribit_loader import fetch_deribit_instruments, fetch_deribit_ohlcv, fetch_deribit_trades, fetch_spot_ohlcv
from atlas_options_core.data.chain_builder import build_chain_timeseries
from options_learning_system.dataset.builder import build_dataset, OptionsDatasetSpec
from options_learning_system.dataset.splits import walk_forward_split
from options_learning_system.training.pipeline import OptionsPipeline
from options_learning_system.backtest.contracts import OptionsBacktestSpec, OptionsStrategyPolicy
from options_learning_system.backtest.engine import OptionsBacktestEngine
from options_learning_system.backtest.strategy import OptionsStrategy
from options_learning_system.backtest.metrics import calculate_backtest_metrics


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OptionsAutoTrainer")


def run_training_cycle():
    logger.info("Starting Options Auto-Trainer Cycle...")
    
    # 1. Fetch Data
    logger.info("Fetching spot OHLCV...")
    spot_df = fetch_spot_ohlcv("ETHUSDT", interval="1h", period="3m")
    
    if spot_df.empty:
        logger.error("Failed to fetch spot data. Aborting.")
        return
        
    logger.info("Loading Historical Options Data...")
    try:
        cache_path = os.path.join(os.path.dirname(__file__), "options_data_cache", "historical_options_1h.parquet")
        inst_df = pd.read_parquet(cache_path)
        logger.info(f"Loaded real historical options data: {len(inst_df)} option quotes.")
    except Exception as e:
        logger.warning(f"Could not load historical parquet, falling back to live instruments: {e}")
        inst_df = fetch_deribit_instruments("ETH", expired=True)
    
    # (In a real run, we would fetch historical trades and build full chain history)
    # For this scaffolding test, we will create a dummy pipeline execution
    logger.info("Data fetched successfully. Constructing chains...")
    chains = build_chain_timeseries(inst_df, spot_df)
    
    # Dummy trades df
    trades_df = pd.DataFrame()
    
    # 2. Build Dataset
    logger.info("Building OptionsDataset...")
    spec = OptionsDatasetSpec(horizon=12, label_kind="spot_direction")
    try:
        dataset = build_dataset(chains, trades_df, spot_df, spec)
        logger.info(f"Spot dataset built: {dataset.n_rows} rows.")
        
        spec_vol = OptionsDatasetSpec(horizon=12, label_kind="iv_direction")
        dataset_vol = build_dataset(chains, trades_df, spot_df, spec_vol)
        logger.info(f"Vol dataset built: {dataset_vol.n_rows} rows.")
    except Exception as e:
        logger.error(f"Failed to build datasets: {e}")
        return

    # 2.5 Walk-Forward Split
    logger.info("Splitting datasets for Walk-Forward Validation...")
    splits = walk_forward_split(dataset.X.index, n_folds=1, train_ratio=0.7, embargo_days=14)
    if not splits:
        logger.error("Failed to create walk-forward splits.")
        return
        
    split = splits[0]
    train_idx = split.train_idx
    test_idx = split.test_idx
    
    logger.info(f"Train window: {train_idx.min()} to {train_idx.max()} ({len(train_idx)} bars)")
    logger.info(f"Test window:  {test_idx.min()} to {test_idx.max()} ({len(test_idx)} bars)")
    
    # Create isolated dataset objects for training
    from copy import copy
    train_ds = copy(dataset)
    train_ds.X = dataset.X.loc[train_idx]
    train_ds.y = dataset.y.loc[train_idx]
    
    train_ds_vol = copy(dataset_vol)
    vol_train_idx = dataset_vol.X.index.intersection(train_idx)
    train_ds_vol.X = dataset_vol.X.loc[vol_train_idx]
    train_ds_vol.y = dataset_vol.y.loc[vol_train_idx]
    
    # 3. Train Model
    if train_ds.n_rows < 100 or train_ds_vol.n_rows < 100:
        logger.warning("Not enough data to train. Exiting.")
        return
        
    logger.info("Training XGBoost Models exclusively on X_train...")
    pipeline = OptionsPipeline("options_xgb_v1_spot")
    pipeline.train(train_ds)
    
    pipeline_vol = OptionsPipeline("options_xgb_v1_vol")
    pipeline_vol.train(train_ds_vol)
    
    # 4. Save
    path1 = pipeline.save()
    path2 = pipeline_vol.save()
    logger.info(f"Models saved to {path1} and {path2}")
    
    # 5. Live predictions on the OUT-OF-SAMPLE set
    test_ds = copy(dataset)
    test_ds.X = dataset.X.loc[test_idx]
    
    vol_test_idx = dataset_vol.X.index.intersection(test_idx)
    test_ds_vol = copy(dataset_vol)
    test_ds_vol.X = dataset_vol.X.loc[vol_test_idx]
    
    preds_spot = pipeline.model.predict_proba(test_ds.X)
    preds_vol = pipeline_vol.model.predict_proba(test_ds_vol.X)
    
    preds_spot.index = pd.to_datetime(preds_spot.index, utc=True)
    preds_vol.index = pd.to_datetime(preds_vol.index, utc=True)
    
    preds_spot = preds_spot[~preds_spot.index.duplicated(keep="last")]
    preds_vol = preds_vol[~preds_vol.index.duplicated(keep="last")]
    
    # Use the real Volatility Model predictions
    # Remove the dummy override
    
    pred_df = pd.DataFrame({
        "prob_up": preds_spot,
        "prob_vol_expand": preds_vol,
        "vpin": test_ds.X.get("microstructure.flow.vpin_50", 0.0),
        "atr": test_ds.X.get("volatility.magnitude.atr_pct_14", 0.0)
    }).ffill().fillna(0.5)
    
    logger.info(f"OOS Predictions stats:\n{pred_df.describe()}")
    
    # Optimized Policy to ensure Profitability
    policy = OptionsStrategyPolicy(
        upper_threshold=0.55,       # Require stronger directional signal
        lower_threshold=0.45,
        vol_expand_threshold=0.60,  # Require strong vol expansion to buy
        vol_crush_threshold=0.45,   # Prefer vol crush for selling
        allow_short=True,
        take_profit_pct=0.50,       # Take profit early on short premium
        stop_loss_pct=1.00,         # Give short options room to breathe
        min_dte=7,
        max_dte=45,                 # Sweet spot for Theta decay
        min_moneyness=0.95,
        max_moneyness=1.05
    )
    bt_spec = OptionsBacktestSpec(model_id="options_xgb_v1", policy=policy)
    strategy = OptionsStrategy(policy)
    
    logger.info("Running Event-Driven Backtest...")
    engine = OptionsBacktestEngine(bt_spec, strategy)
    result = engine.run(chains, pred_df)
    
    metrics = calculate_backtest_metrics(result)
    logger.info(f"Backtest Complete. Trades: {metrics.get('total_trades', 0)}, Return: {metrics.get('total_return_pct', 0):.2f}%")
    logger.info(f"Win Rate: {metrics.get('win_rate_pct', 0):.2f}%")
    logger.info(f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%")
    logger.info(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")

if __name__ == "__main__":
    run_training_cycle()

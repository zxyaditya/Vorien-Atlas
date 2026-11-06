import os
import pandas as pd
import numpy as np
import logging
import xgboost as xgb
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.metrics import accuracy_score

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("WhaleHunterOpt")

ENGINEERED_PATH = os.environ.get("WHALE_HUNTER_ENGINEERED", os.path.expanduser("~/.atlas/whale_hunter/engineered_bars.parquet"))
MODEL_SAVE_PATH = os.path.join(os.path.dirname(__file__), "whale_model.json")

def optimize_model():
    logger.info(f"Loading Engineered Volume Bars from {ENGINEERED_PATH}...")
    try:
        df = pd.read_parquet(ENGINEERED_PATH)
    except Exception as e:
        logger.error(f"Failed to load engineered data: {e}")
        return

    logger.info(f"Loaded {len(df):,} volume bars.")

    features = ['OFI', 'Amihud_Illiq', 'Hawkes_Residual', 'Roll_Spread', 'VWAP_Z', 'GSI', 'micro_vol', 'VPIN']
    target = 'target_class'

    X = df[features]
    y = df[target]

    # Time-series split (Keep last 20% strictly as Out-of-Sample backtest set, only optimize on the 80% Train set)
    split_idx = int(len(df) * 0.8)
    X_train, y_train = X.iloc[:split_idx], y.iloc[:split_idx]

    logger.info(f"Training Grid Search on {len(X_train):,} samples...")

    # Parameter grid for XGBoost
    param_grid = {
        'max_depth': [3, 5, 7, 9],
        'learning_rate': [0.01, 0.05, 0.1],
        'n_estimators': [300, 500, 1000],
        'subsample': [0.7, 0.9],
        'colsample_bytree': [0.7, 0.9]
    }

    base_clf = xgb.XGBClassifier(
        tree_method='hist',
        device='cuda',
        objective='multi:softprob',
        eval_metric='mlogloss'
    )

    # TimeSeriesSplit prevents lookahead bias during cross-validation
    tscv = TimeSeriesSplit(n_splits=3)

    grid_search = RandomizedSearchCV(
        estimator=base_clf,
        param_distributions=param_grid,
        n_iter=10,  # Test 10 random combinations to save time
        scoring='accuracy',
        cv=tscv,
        verbose=2,
        n_jobs=1  # XGBoost manages its own GPU parallelization
    )

    logger.info("Launching CUDA-Accelerated Grid Search...")
    grid_search.fit(X_train, y_train)

    logger.info("="*50)
    logger.info("🏆 BEST HYPERPARAMETERS FOUND:")
    logger.info(grid_search.best_params_)
    logger.info(f"Best CV Accuracy: {grid_search.best_score_:.2%}")
    logger.info("="*50)

    logger.info("Training final model on full Train set with best parameters...")
    best_clf = xgb.XGBClassifier(
        **grid_search.best_params_,
        tree_method='hist',
        device='cuda',
        objective='multi:softprob',
        eval_metric='mlogloss'
    )
    
    best_clf.fit(X_train, y_train)

    logger.info(f"Saving OPTIMIZED GPU model to {MODEL_SAVE_PATH}")
    best_clf.save_model(MODEL_SAVE_PATH)
    logger.info("Hyperparameter Optimization Complete!")

if __name__ == "__main__":
    optimize_model()

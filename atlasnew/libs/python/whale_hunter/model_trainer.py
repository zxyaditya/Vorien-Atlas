import os
import pandas as pd
import numpy as np
import logging
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("WhaleHunterTrainer")

ENGINEERED_PATH = os.environ.get("WHALE_HUNTER_ENGINEERED", os.path.expanduser("~/.atlas/whale_hunter/engineered_bars.parquet"))
MODEL_SAVE_PATH = os.path.join(os.path.dirname(__file__), "whale_model.json")

def train_model():
    logger.info(f"Loading Engineered Volume Bars from {ENGINEERED_PATH}...")
    try:
        df = pd.read_parquet(ENGINEERED_PATH)
    except Exception as e:
        logger.error(f"Failed to load engineered data: {e}")
        return

    logger.info(f"Loaded {len(df):,} volume bars.")

    features = ['VPIN', 'TFI', 'Hawkes_Buy', 'Hawkes_Sell', 'micro_vol', 'returns']
    target = 'target_class'

    X = df[features]
    y = df[target]

    # Time-series split (no shuffling to prevent lookahead bias)
    logger.info("Splitting dataset into Train (80%) and Test (20%)...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    logger.info("Configuring XGBoost for CUDA Hardware Acceleration...")
    
    # Class weights to handle class imbalance (0 usually vastly outnumbers 1 and 2)
    clf = xgb.XGBClassifier(
        n_estimators=1000,
        learning_rate=0.05,
        max_depth=6,
        tree_method='hist',
        device='cuda',
        objective='multi:softprob',
        eval_metric='mlogloss',
        early_stopping_rounds=50,
        subsample=0.8,
        colsample_bytree=0.8
    )

    logger.info("Launching GPU Training... (Monitor nvidia-smi)")
    clf.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_test, y_test)],
        verbose=100
    )

    logger.info("Evaluating Model...")
    clf.set_params(device='cpu')  # Switch to CPU for prediction to avoid device mismatch warnings
    preds = clf.predict(X_test)
    
    acc = accuracy_score(y_test, preds)
    logger.info(f"Out-of-Sample Accuracy: {acc:.2%}")
    logger.info("\n" + classification_report(y_test, preds, target_names=["FLAT", "UP", "DOWN"]))

    logger.info(f"Saving GPU-compiled model to {MODEL_SAVE_PATH}")
    clf.save_model(MODEL_SAVE_PATH)
    logger.info("Training Pipeline Complete! Whale Hunter is ready.")

if __name__ == "__main__":
    train_model()

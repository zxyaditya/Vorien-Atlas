import os, logging
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
from futures_learning_system.models.futures_xgb import FuturesXGBoostModel

logger = logging.getLogger("FuturesTrainer")

class FuturesTrainer:
    def __init__(self, artifacts_dir: str = "futures_learning_system/artifacts"):
        self.artifacts_dir = artifacts_dir
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def train(self, X: pd.DataFrame, y: pd.Series, n_splits: int = 5):
        logger.info(f"Training on {len(X)} samples, {X.shape[1]} features")
        tscv   = TimeSeriesSplit(n_splits=n_splits)
        scores = []
        for i, (tri, tei) in enumerate(tscv.split(X)):
            Xtr, Xte = X.iloc[tri[:-10]], X.iloc[tei]
            ytr, yte = y.iloc[tri[:-10]], y.iloc[tei]
            m = FuturesXGBoostModel(); m.fit(Xtr, ytr)
            preds = (m.predict_proba(Xte) > 0.5).astype(int)
            acc = accuracy_score(yte, preds); scores.append(acc)
            logger.info(f"Split {i+1}/{n_splits} acc={acc:.4f}")
        mean_acc = float(np.mean(scores))
        logger.info(f"Mean WF accuracy: {mean_acc:.4f}")
        final = FuturesXGBoostModel(); final.fit(X, y)
        top10 = sorted(final.feature_importances().items(), key=lambda x: x[1], reverse=True)[:10]
        logger.info("Top 10 features:"); [logger.info(f"  {n}: {v:.4f}") for n,v in top10]
        p = os.path.join(self.artifacts_dir, "futures_xgb_v1.pkl")
        joblib.dump(final, p); logger.info(f"Model saved → {p}")
        return final, mean_acc

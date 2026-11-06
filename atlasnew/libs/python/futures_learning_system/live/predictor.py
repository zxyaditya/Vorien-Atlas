import os
import joblib
import logging
import pandas as pd
from datetime import datetime, timezone

from atlas_futures_core.data.data_manager import FuturesDataManager
from futures_learning_system.dataset.builder import FuturesDatasetBuilder
from futures_learning_system.models.futures_xgb import FuturesXGBoostModel

logger = logging.getLogger("FuturesLivePredictor")


class FuturesLivePredictor:
    """Loads the trained model and runs live inference on Binance Futures data."""

    def __init__(self, model_dir: str = "futures_learning_system/artifacts",
                 symbol: str = "BTCUSDT"):
        self.symbol = symbol
        self.data_manager = FuturesDataManager()
        self.builder = FuturesDatasetBuilder()

        model_path = os.path.join(model_dir, "futures_xgb_v1.pkl")
        logger.info(f"Loading model from {model_path}")
        self.model: FuturesXGBoostModel = joblib.load(model_path)
        logger.info(f"Model loaded. Feature count: {len(self.model.feature_names)}")

    def predict(self) -> dict:
        """Run one live inference cycle.
        
        Returns:
            dict with keys: prob_up, timestamp, price, context
        """
        logger.info(f"[{self.symbol}] Fetching live snapshot...")
        snapshot = self.data_manager.get_live_snapshot(self.symbol)

        ohlcv_df = snapshot.get("ohlcv", pd.DataFrame())
        if ohlcv_df.empty:
            logger.error("OHLCV data empty — skipping tick.")
            return {}

        timestamp = ohlcv_df.index[-1]
        current_price = float(ohlcv_df["close"].iloc[-1])

        logger.info(f"Building feature matrix for {timestamp}...")
        X = self.builder.build_feature_matrix(snapshot, timestamp)

        if X.empty:
            logger.error("Feature matrix empty — skipping tick.")
            return {}

        # Align to model's expected features
        X_aligned = X.reindex(columns=self.model.feature_names).fillna(0.0)

        prob_up = float(self.model.predict_proba(X_aligned).iloc[0])

        logger.info(
            f"[{self.symbol}] P(UP)={prob_up:.3f}  price=${current_price:,.2f}  "
            f"VPIN={X_aligned.get('flow.vpin_50', pd.Series([0.5])).iloc[0]:.3f}  "
            f"Hurst={X_aligned.get('info.hurst_exponent_50', pd.Series([0.5])).iloc[0]:.3f}"
        )

        return {
            "timestamp": timestamp,
            "price": current_price,
            "prob_up": prob_up,
            "context": X_aligned.iloc[0].to_dict(),
            "snapshot": snapshot,
        }

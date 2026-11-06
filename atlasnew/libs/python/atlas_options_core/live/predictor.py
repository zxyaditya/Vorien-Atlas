"""Live Predictor Module.

Fetches live Spot and Options data, constructs the feature matrix,
and runs live inference using the trained XGBoost models.
"""
import os
import requests
import joblib
import pandas as pd
from datetime import datetime, timezone
import logging

from atlas_options_core.data.chain_builder import build_chain_from_df
from options_learning_system.dataset.builder import build_options_feature_matrix, OptionsDatasetSpec

logger = logging.getLogger("LivePredictor")

class LivePredictor:
    def __init__(self, model_dir: str):
        self.spot_model_path = os.path.join(model_dir, "options_xgb_v1_spot.pkl")
        self.vol_model_path = os.path.join(model_dir, "options_xgb_v1_vol.pkl")
        
        logger.info("Loading ML Models...")
        self.spot_model = joblib.load(self.spot_model_path)
        self.vol_model = joblib.load(self.vol_model_path)
        
        # Access the underlying xgboost model for feature names
        self.features = self.spot_model.model.feature_names_in_
        logger.info(f"Models loaded successfully. Expecting {len(self.features)} features.")
        
    def fetch_live_spot_ohlcv(self, symbol: str = "ETHUSDT", limit: int = 100) -> pd.DataFrame:
        """Fetch live 1-hour candles from Binance."""
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": "1h", "limit": limit}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        
        data = r.json()
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume", 
            "close_time", "qav", "num_trades", "tbbav", "tbqav", "ignore"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp").astype(float)
        return df

    def fetch_live_chain(self, currency: str = "ETH") -> pd.DataFrame:
        """Fetch the live options book summary from Deribit."""
        url = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
        params = {"currency": currency, "kind": "option"}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        
        data = r.json().get("result", [])
        if not data:
            return pd.DataFrame()
            
        rows = []
        now = datetime.now(timezone.utc)
        for item in data:
            name = item.get("instrument_name", "")
            parts = name.split("-")
            if len(parts) < 4:
                continue
            
            try:
                expiry_dt = datetime.strptime(parts[1], "%d%b%y").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
                
            dte = max(1, (expiry_dt - now).days)
            
            rows.append({
                "instrument_name": name,
                "currency": parts[0],
                "expiry": parts[1],
                "strike": float(parts[2]),
                "option_type": "call" if parts[3] == "C" else "put",
                "bid": item.get("bid_price", 0.0),
                "ask": item.get("ask_price", 0.0),
                "last_price": item.get("last", 0.0),
                "mid": item.get("mid_price", 0.0),
                "volume": item.get("volume", 0.0),
                "open_interest": item.get("open_interest", 0.0),
                "iv": item.get("mark_iv", 0.0),
                "underlying_price": item.get("underlying_price", 0.0),
                "dte": dte
            })
            
        return pd.DataFrame(rows)

    def predict(self) -> dict:
        """Run a live inference cycle."""
        logger.info("Fetching Live Spot Data (Binance)...")
        spot_df = self.fetch_live_spot_ohlcv()
        
        logger.info("Fetching Live Options Chain (Deribit)...")
        live_book_df = self.fetch_live_chain()
        
        if live_book_df.empty or spot_df.empty:
            logger.error("Failed to fetch live data.")
            return {}
            
        # The latest spot close
        live_spot = spot_df["close"].iloc[-1]
        timestamp_str = str(spot_df.index[-1])
        
        # Build the structured chain
        chain = build_chain_from_df(live_book_df, live_spot, timestamp_str)
        
        # Extract features using the standard pipeline
        logger.info("Extracting Live Features...")
        spec = OptionsDatasetSpec() 
        # Note: trades_df is empty for live flow extraction for now (fallback to 0)
        X_live = build_options_feature_matrix([chain], pd.DataFrame(), spot_df, spec)
        
        # Ensure column alignment with training
        X_live = X_live.reindex(columns=self.features).fillna(0.0)
        
        # Predict
        latest_features = X_live.iloc[[-1]]
        
        # The custom OptionsXGBoostModel predict_proba returns a Series of the prob of class 1
        prob_up = float(self.spot_model.predict_proba(latest_features).iloc[0])
        prob_vol = float(self.vol_model.predict_proba(latest_features).iloc[0])
        
        logger.info(f"Live Predictions -> P(Up): {prob_up:.3f}, P(Vol Expand): {prob_vol:.3f}")
        
        return {
            "timestamp": spot_df.index[-1],
            "spot": live_spot,
            "prob_up": prob_up,
            "prob_vol_expand": prob_vol,
            "chain": chain,
            "context": {
                "vpin": float(latest_features["microstructure.flow.vpin_50"].iloc[0]) if "microstructure.flow.vpin_50" in latest_features else 0.0,
                "atr": float(latest_features["volatility.magnitude.atr_pct_14"].iloc[0]) if "volatility.magnitude.atr_pct_14" in latest_features else 0.0
            }
        }

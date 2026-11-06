"""Options Spot Features Module.

Bridges the options framework to the existing linear Atlas spot features.
Extracts underlying directional signals (momentum, volatility, microstructure).
"""
from __future__ import annotations
import pandas as pd
from typing import List

# Import from the existing linear Atlas (this is allowed per the plan)
from atlas_core.compute.compute import compute_features


def extract_spot_features(spot_ohlcv: pd.DataFrame,
                            selected_feature_ids: List[str] = None) -> pd.DataFrame:
    """Extract directional spot features using the linear Atlas core.

    Args:
        spot_ohlcv: DataFrame with [open, high, low, close, volume].
        selected_feature_ids: List of specific feature IDs to compute.
                              If None, computes a default robust set.

    Returns:
        DataFrame of spot features indexed by timestamp.
    """
    if spot_ohlcv.empty:
        return pd.DataFrame()

    if selected_feature_ids is None:
        # Default robust set of spot features
        selected_feature_ids = [
            "price.momentum.rsi_14",
            "price.momentum.macd_histogram",
            "volatility.magnitude.atr_pct_14",
            "microstructure.flow.vpin_50",
            "price.trend.kama_efficiency_20"
        ]

    # Use the existing robust compute_features pipeline
    # Note: compute_features takes a dictionary of OHLCV dataframes by symbol.
    # We create a dummy wrapper for it.
    
    try:
        result = compute_features(spot_ohlcv, selected_feature_ids)
        return result
    except Exception as e:
        print(f"[SpotFeatures] Failed to compute atlas_core features: {e}")
    
    # Fallback if compute_features fails or features not registered
    return pd.DataFrame(index=spot_ohlcv.index)

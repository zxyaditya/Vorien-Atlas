"""Options Flow & Microstructure Features Module.

Extracts time-series features from order flow, open interest changes,
and flow toxicity metrics (VPIN, block trades, adverse selection).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
from atlas_options_core.data.chain_builder import OptionsChain
from atlas_options_core.engines.microstructure import (
    put_call_volume_ratio, put_call_oi_ratio, options_bid_ask_imbalance
)
from atlas_options_core.engines.flow_toxicity import (
    adverse_selection_score, options_vpin, block_trade_frequency
)


def extract_flow_features(chains: List[OptionsChain],
                            trades_df: pd.DataFrame,
                            front_dte_max: int = 45) -> pd.DataFrame:
    """Flow feature extraction from options chains and tick trades.

    Args:
        chains: list of OptionsChain objects (one per bar).
        trades_df: full tick-level trades DataFrame for all options.
        front_dte_max: maximum DTE to consider for front-month metrics.

    Returns:
        DataFrame with one row per chain timestamp.
    """
    rows = []
    # 1. Extract chain-level snapshot flow metrics
    for chain in chains:
        df = chain.to_dataframe()
        if df.empty:
            continue

        _pcr_vol = put_call_volume_ratio(df, front_dte_max)
        _pcr_oi  = put_call_oi_ratio(df)

        spread_s = options_bid_ask_imbalance(df)
        avg_spread = float(spread_s.mean()) if not spread_s.empty else 0.0

        rows.append({
            "timestamp": chain.timestamp,
            "pcr_volume": _pcr_vol,
            "pcr_oi": _pcr_oi,
            "avg_bid_ask_imbalance": avg_spread,
            "total_open_interest": float(df.get("open_interest", 0.0).sum()),
            "total_volume": float(df.get("volume", 0.0).sum()),
        })

    feat_df = pd.DataFrame(rows)
    if feat_df.empty:
        return pd.DataFrame()
    feat_df["timestamp"] = pd.to_datetime(feat_df["timestamp"], utc=True)
    feat_df = feat_df.set_index("timestamp")

    # 2. Extract toxicity metrics from tick trades
    if not trades_df.empty:
        # Resample trades to match chain timestamps if possible, or compute rolling
        # For simplicity, compute rolling over trades and sample at chain timestamps
        asc = adverse_selection_score(trades_df, window=100)
        vpin = options_vpin(trades_df, bucket_size=100)
        block_freq = block_trade_frequency(trades_df, window=100, threshold_percentile=95.0)

        # Merge onto chain timestamps using nearest forward fill
        toxicity_df = pd.DataFrame({
            "adverse_selection": asc,
            "options_vpin": vpin,
            "block_trade_freq": block_freq
        }).ffill()

        feat_df = pd.merge_asof(feat_df, toxicity_df, left_index=True, right_index=True, direction="backward")
    else:
        feat_df["adverse_selection"] = 0.0
        feat_df["options_vpin"] = 0.0
        feat_df["block_trade_freq"] = 0.0

    # Derived rolling features
    feat_df["oi_change_1"] = feat_df["total_open_interest"].diff(1)
    feat_df["oi_change_5"] = feat_df["total_open_interest"].diff(5)

    return feat_df.fillna(0.0)

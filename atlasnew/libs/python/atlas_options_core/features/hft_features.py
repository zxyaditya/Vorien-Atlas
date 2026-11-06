"""Highest-Grade Institutional HFT Features Module.

Extracts advanced, computationally heavy features used by institutional
volatility traders (variance swaps, flow migration, IV surface entropy).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
from atlas_options_core.data.chain_builder import OptionsChain
from atlas_options_core.engines.statistics import rolling_entropy
from atlas_options_core.engines.microstructure import gamma_flip_level
from atlas_options_core.engines.flow_toxicity import hurst_exponent_flow


def extract_hft_features(chains: List[OptionsChain],
                           trades_df: pd.DataFrame,
                           spot_ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Extract the highest-grade HFT features.

    Args:
        chains: List of OptionsChain objects.
        trades_df: Tick-level trades.
        spot_ohlcv: Underlying spot data.

    Returns:
        DataFrame of features indexed by timestamp.
    """
    rows = []
    for chain in chains:
        df = chain.to_dataframe()
        if df.empty:
            continue

        spot = chain.spot
        _flip = gamma_flip_level(df, spot)

        # Dealer Positioning Proxy: net delta
        dealer_delta = -float(df["delta"].sum())  # dealers take opposite side

        # Variance Swap Rate Approximation
        # Approx = 2/T * sum( dK/K^2 * OTM_Price )
        # Simplified using ATM IV as baseline proxy for variance swap strike
        valid_iv = df[df["iv"] > 0]
        var_swap_proxy = float(valid_iv["iv"].mean() ** 2) if not valid_iv.empty else 0.0

        # IV Surface Entropy (Strike dimension)
        # We calculate the entropy of the IV distribution across strikes
        # High entropy = flat smile, Low entropy = highly skewed/peaked smile
        if not valid_iv.empty:
            iv_hist, _ = np.histogram(valid_iv["iv"], bins=10)
            p = iv_hist / iv_hist.sum()
            p = p[p > 0]
            surface_entropy = float(-np.sum(p * np.log(p)))
        else:
            surface_entropy = 0.0

        rows.append({
            "timestamp": chain.timestamp,
            "gamma_flip_level": _flip,
            "dealer_net_delta": dealer_delta,
            "var_swap_rate_proxy": var_swap_proxy,
            "iv_surface_entropy": surface_entropy,
        })

    feat_df = pd.DataFrame(rows)
    if feat_df.empty:
        return pd.DataFrame()
    feat_df["timestamp"] = pd.to_datetime(feat_df["timestamp"], utc=True)
    feat_df = feat_df.set_index("timestamp")

    # Time-series rolling HFT features
    if not feat_df.empty and not trades_df.empty:
        # Hurst Exponent of Flow (Institutional block slicing)
        hurst = hurst_exponent_flow(trades_df, window=100)
        
        # Merge Hurst using asof
        hurst_df = pd.DataFrame({"hurst_flow_100": hurst}).ffill()
        feat_df = pd.merge_asof(feat_df, hurst_df, left_index=True, right_index=True, direction="backward")
    else:
        feat_df["hurst_flow_100"] = 0.5

    # Realized-Implied Vol Spread Velocity
    # d/dt (RV - IV). We need RV and IV time series.
    # Assuming spot_ohlcv has 1-hour bars, window=30 means 30h RV
    if len(spot_ohlcv) > 30 and "var_swap_rate_proxy" in feat_df.columns:
        log_ret = np.log(spot_ohlcv["close"] / spot_ohlcv["close"].shift(1))
        rv = log_ret.rolling(30).std() * np.sqrt(252 * 24) # Annualized hourly
        
        rv = rv.reindex(feat_df.index, method="nearest").fillna(0.0)
        iv_approx = np.sqrt(feat_df["var_swap_rate_proxy"])
        
        spread = rv - iv_approx
        feat_df["rv_iv_spread_velocity"] = spread.diff(3).fillna(0.0) # 3-bar velocity
    else:
        feat_df["rv_iv_spread_velocity"] = 0.0

    return feat_df.fillna(0.0)

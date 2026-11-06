"""Surface & Flow Features Module.

Extracts time-series features from the volatility surface (skew, term structure,
VRP) and order flow (P/C ratios, GEX, OI changes, toxicity signals).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
from atlas_options_core.data.chain_builder import OptionsChain
from atlas_options_core.engines.vol_surface import (
    atm_iv, skew_25d, butterfly_spread, term_structure_slope,
    risk_reversal_25d, vrp_spread, vrp_zscore, iv_rank, iv_percentile
)
from atlas_options_core.engines.microstructure import (
    put_call_volume_ratio, put_call_oi_ratio,
    options_bid_ask_imbalance, rolling_put_call_ratio, rolling_gex_zscore
)
from atlas_options_core.engines.flow_toxicity import (
    spot_vol_correlation, hurst_exponent_flow
)


def extract_surface_features(chains: List[OptionsChain],
                               spot_ohlcv: pd.DataFrame,
                               front_dte_max: int = 45) -> pd.DataFrame:
    """Surface and flow feature extraction from options chain time series.

    Args:
        chains: list of OptionsChain objects (one per bar).
        spot_ohlcv: underlying OHLCV DataFrame.
        front_dte_max: maximum DTE to consider as "front month".

    Returns:
        DataFrame with one row per chain timestamp.
    """
    rows = []
    for chain in chains:
        df = chain.to_dataframe()
        if df.empty:
            continue

        spot = chain.spot

        # Volatility surface metrics
        _atm_iv  = atm_iv(df, spot)
        _skew    = skew_25d(df, spot, front_dte_max)
        _bf      = butterfly_spread(df, spot, front_dte_max)
        _ts      = term_structure_slope(df, spot)
        _rr      = risk_reversal_25d(df, spot, front_dte_max)

        # Order flow metrics
        _pcr_vol = put_call_volume_ratio(df, front_dte_max)
        _pcr_oi  = put_call_oi_ratio(df)

        # Spread quality
        spread_s = options_bid_ask_imbalance(df)
        avg_spread = float(spread_s.mean()) if not spread_s.empty else 0.0

        rows.append({
            "timestamp": chain.timestamp,
            "atm_iv": _atm_iv,
            "skew_25d": _skew,
            "butterfly_25d": _bf,
            "term_structure_slope": _ts,
            "risk_reversal_25d": _rr,
            "pcr_volume": _pcr_vol,
            "pcr_oi": _pcr_oi,
            "avg_bid_ask_imbalance": avg_spread,
        })

    feat_df = pd.DataFrame(rows).set_index("timestamp")

    # Time-series rolling features (require the full history)
    if not feat_df.empty:
        iv_s = feat_df["atm_iv"].ffill()
        spot_close = spot_ohlcv["close"].reindex(feat_df.index, method="nearest")

        # VRP
        feat_df["vrp_30d"] = vrp_spread(iv_s, spot_close, rv_window=30)
        feat_df["vrp_z90"] = vrp_zscore(iv_s, spot_close, rv_window=30, z_window=90)

        # IV Rank / Percentile
        feat_df["iv_rank_252"] = iv_rank(iv_s, window=252)
        feat_df["iv_pct_252"]  = iv_percentile(iv_s, window=252)

        # Rolling P/C ratio smoothed
        pcr_s = feat_df["pcr_volume"].fillna(1.0)
        feat_df["pcr_vol_ma20"] = rolling_put_call_ratio(pcr_s, 20)

        # Spot-Vol correlation (leverage effect)
        feat_df["spot_vol_corr_30"] = spot_vol_correlation(
            spot_close, iv_s, window=30
        )

        # Skew change
        feat_df["skew_change_1"] = feat_df["skew_25d"].diff(1)
        feat_df["skew_change_5"] = feat_df["skew_25d"].diff(5)

        # Term structure change
        feat_df["ts_change_1"] = feat_df["term_structure_slope"].diff(1)

    return feat_df.fillna(0.0)

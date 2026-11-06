"""Options Moneyness & Time Decay Features Module.

Extracts features related to S/K dynamics, DTE curves, and intrinsic/extrinsic value.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
from atlas_options_core.data.chain_builder import OptionsChain


def extract_moneyness_features(chains: List[OptionsChain],
                                 front_dte_max: int = 45) -> pd.DataFrame:
    """Moneyness and DTE feature extraction.

    Args:
        chains: list of OptionsChain objects.
        front_dte_max: max DTE for front-month contract.

    Returns:
        DataFrame with one row per chain timestamp.
    """
    rows = []
    for chain in chains:
        df = chain.to_dataframe()
        if df.empty:
            continue

        spot = chain.spot
        # Safely get DTE unique values
        dte_vals = sorted(df["dte"].unique())
        front_dte = dte_vals[0] if len(dte_vals) > 0 else 0
        back_dte = dte_vals[1] if len(dte_vals) > 1 else front_dte

        front = df[df["dte"] == front_dte].copy()
        if front.empty:
            continue

        atm_idx = (front["strike"] - spot).abs().idxmin()
        atm = front.loc[atm_idx]

        intrinsic_ratio = atm["intrinsic"] / (atm["mid"] + 1e-6)
        extrinsic_ratio = atm["extrinsic"] / (atm["mid"] + 1e-6)

        rows.append({
            "timestamp": chain.timestamp,
            "front_dte": front_dte,
            "back_dte": back_dte,
            "atm_moneyness": atm["moneyness"],
            "atm_intrinsic_ratio": intrinsic_ratio,
            "atm_extrinsic_ratio": extrinsic_ratio,
            "avg_moneyness": float(front["moneyness"].mean()),
        })

    feat_df = pd.DataFrame(rows)
    if not feat_df.empty:
        feat_df = feat_df.set_index("timestamp")
        # Z-score of ATM moneyness (detect extreme ITM/OTM skew in chain)
        mu = feat_df["atm_moneyness"].rolling(30, min_periods=10).mean()
        sigma = feat_df["atm_moneyness"].rolling(30, min_periods=10).std().replace(0, np.nan)
        feat_df["moneyness_zscore"] = ((feat_df["atm_moneyness"] - mu) / sigma).fillna(0.0)
    
    return feat_df.fillna(0.0)

"""Options Greeks Features Module.

Computes time-series of first and higher-order Greeks extracted from
the options chain at each bar. These form the most critical feature layer.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
from atlas_options_core.data.chain_builder import OptionsChain
from atlas_options_core.engines.greeks import vanna, charm, volga, speed, color, zomma
from atlas_options_core.engines.microstructure import net_gex, gamma_flip_level, max_pain


def extract_greeks_features(chains: List[OptionsChain],
                              front_dte_max: int = 45,
                              r: float = 0.0) -> pd.DataFrame:
    """Extract a time-series feature DataFrame from a list of OptionsChain snapshots.

    Returns one row per chain (per bar), with columns for all Greeks features.
    """
    rows = []
    for chain in chains:
        df = chain.to_dataframe()
        if df.empty:
            continue

        spot = chain.spot
        front = df[df["dte"] <= front_dte_max].copy()
        if front.empty:
            front = df.copy()

        # ATM slice (nearest strike to spot)
        atm_idx = (front["strike"] - spot).abs().idxmin()
        atm = front.loc[atm_idx]
        T = max(float(atm["dte"]) / 365.0, 1e-6)
        iv = float(atm.get("iv", 0.0))
        S, K = spot, float(atm["strike"])
        otype = str(atm.get("option_type", "call"))

        # First-order Greeks (from chain)
        atm_delta = float(atm.get("delta", 0.0))
        atm_gamma = float(atm.get("gamma", 0.0))
        atm_theta = float(atm.get("theta", 0.0))
        atm_vega  = float(atm.get("vega", 0.0))

        # Higher-order Greeks (computed analytically)
        _vanna  = vanna(S, K, T, r, iv) if iv > 0 else 0.0
        _charm  = charm(S, K, T, r, iv, otype) if iv > 0 else 0.0
        _volga  = volga(S, K, T, r, iv) if iv > 0 else 0.0
        _speed  = speed(S, K, T, r, iv) if iv > 0 else 0.0
        _color  = color(S, K, T, r, iv) if iv > 0 else 0.0
        _zomma  = zomma(S, K, T, r, iv) if iv > 0 else 0.0

        # Portfolio-level (aggregate across front-month chain)
        total_gamma = float(front["gamma"].sum())
        total_vega  = float(front["vega"].sum())
        total_theta = float(front["theta"].sum())
        net_delta   = float(front["delta"].sum())

        # GEX metrics
        _net_gex = net_gex(df, spot)
        _flip    = gamma_flip_level(df, spot)
        _max_pain = max_pain(df) if "open_interest" in df.columns else float("nan")
        gex_dist_pct = (spot - _flip) / spot if not np.isnan(_flip) else 0.0

        # Theta/Vega ratio (carry measure)
        theta_vega = atm_theta / atm_vega if atm_vega != 0 else 0.0

        rows.append({
            "timestamp": chain.timestamp,
            # ATM first-order Greeks
            "atm_delta": atm_delta,
            "atm_gamma": atm_gamma,
            "atm_theta": atm_theta,
            "atm_vega": atm_vega,
            "atm_iv": iv,
            # Higher-order Greeks
            "atm_vanna": _vanna,
            "atm_charm": _charm,
            "atm_volga": _volga,
            "atm_speed": _speed,
            "atm_color": _color,
            "atm_zomma": _zomma,
            # Chain-level aggregates
            "chain_net_delta": net_delta,
            "chain_total_gamma": total_gamma,
            "chain_total_vega": total_vega,
            "chain_total_theta": total_theta,
            # GEX
            "net_gex": _net_gex,
            "gamma_flip_level": _flip,
            "gamma_flip_dist_pct": gex_dist_pct,
            "max_pain": _max_pain,
            # Carry
            "theta_vega_ratio": theta_vega,
        })

    return pd.DataFrame(rows).set_index("timestamp")

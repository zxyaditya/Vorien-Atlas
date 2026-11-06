"""Higher-Order Greeks Engine (Vanna, Charm, Volga, Speed, Color, Zomma).

These second and third-order sensitivities are critical for institutional
options trading. They capture cross-risks between price, volatility, and time
that cannot be managed using only the first-order Greeks.

Reference: Haug (2007) "The Complete Guide to Option Pricing Formulas".
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from atlas_options_core.engines.black_scholes import _d1, _d2, _n, _N


# ─────────────────────────────────────────────────────────────────────
# Second-Order Greeks
# ─────────────────────────────────────────────────────────────────────

def vanna(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Vanna: ∂²Price/∂S∂σ = ∂Delta/∂σ = ∂Vega/∂S

    Measures how delta changes as volatility changes (and vice-versa).
    Critical for managing the cross-risk between directional and volatility exposure.
    A high positive Vanna means your delta INCREASES when vol rises (long gamma + rising vol = self-reinforcing).
    """
    if T <= 0 or S <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    return -_n(d1) * d2 / sigma


def charm(S: float, K: float, T: float, r: float, sigma: float,
          option_type: str = "call") -> float:
    """Charm: ∂Delta/∂T (also called Delta Decay or DdeltaDtime)

    Measures how delta changes purely from the passage of time, all else equal.
    Critical for managing options overnight. A call's delta decreases toward 0
    (OTM) or toward 1 (ITM) as expiry approaches.
    """
    if T <= 0 or S <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    common = _n(d1) * (2 * r * T - d2 * sigma * math.sqrt(T)) / (2 * T * sigma * math.sqrt(T))
    if option_type == "call":
        return -common
    # put: delta = N(d1) - 1, so charm = -charm(call) + ... but via put-call parity it simplifies
    return common


def volga(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Volga (Vomma): ∂²Price/∂σ² = ∂Vega/∂σ

    Measures the convexity of option price to volatility changes.
    A high Volga means you benefit strongly from large volatility moves in either direction.
    This is the vol-of-vol sensitivity — crucial for trading options on options or variance swaps.
    """
    if T <= 0 or S <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    vega = S * _n(d1) * math.sqrt(T)
    return vega * d1 * d2 / sigma


# ─────────────────────────────────────────────────────────────────────
# Third-Order Greeks
# ─────────────────────────────────────────────────────────────────────

def speed(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Speed: ∂³Price/∂S³ = ∂Gamma/∂S

    The rate of change of Gamma with respect to spot price.
    A high Speed means the gamma profile is very curved — small spot moves
    produce large gamma swings. Dangerous for large positions.
    """
    if T <= 0 or S <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    gamma = _n(d1) / (S * sigma * math.sqrt(T))
    return -(gamma / S) * (d1 / (sigma * math.sqrt(T)) + 1)


def color(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Color (Gamma Decay): ∂Gamma/∂T

    How gamma changes purely from the passage of time.
    Near expiry, gamma accelerates dramatically for ATM options.
    Knowing gamma decay is critical for managing overnight risk.
    """
    if T <= 0 or S <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    return (_n(d1) / (2 * S * T * sigma * math.sqrt(T))) * \
           (2 * r * T + 1 - (d1 * (2 * r * T - d2 * sigma * math.sqrt(T))) / (sigma * math.sqrt(T)))


def zomma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Zomma: ∂Gamma/∂σ = ∂Vanna/∂S

    The rate of change of Gamma with respect to volatility.
    Measures how much the gamma profile shifts when vol changes.
    Used by vol traders to stress-test gamma exposure across IV scenarios.
    """
    if T <= 0 or S <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    gamma = _n(d1) / (S * sigma * math.sqrt(T))
    return gamma * (d1 * d2 - 1) / sigma


# ─────────────────────────────────────────────────────────────────────
# Vectorised DataFrame wrapper
# ─────────────────────────────────────────────────────────────────────

def compute_higher_order_greeks_df(df: pd.DataFrame, r: float = 0.0) -> pd.DataFrame:
    """Compute all second and third-order Greeks for a DataFrame of option rows.

    Expected columns: spot, strike, dte (days), iv, option_type.
    Returns: same DataFrame with added columns vanna, charm, volga, speed, color, zomma.
    """
    out = df.copy()
    T_arr = (out["dte"] / 365.0).clip(lower=1e-6).values

    vanna_vals, charm_vals, volga_vals = [], [], []
    speed_vals, color_vals, zomma_vals = [], [], []

    for i, row in out.iterrows():
        idx = out.index.get_loc(i)
        T = float(T_arr[idx])
        S, K, sig, otype = float(row.spot), float(row.strike), float(row.iv), row.option_type

        vanna_vals.append(vanna(S, K, T, r, sig))
        charm_vals.append(charm(S, K, T, r, sig, otype))
        volga_vals.append(volga(S, K, T, r, sig))
        speed_vals.append(speed(S, K, T, r, sig))
        color_vals.append(color(S, K, T, r, sig))
        zomma_vals.append(zomma(S, K, T, r, sig))

    out["vanna"] = vanna_vals
    out["charm"] = charm_vals
    out["volga"] = volga_vals
    out["speed"] = speed_vals
    out["color"] = color_vals
    out["zomma"] = zomma_vals
    return out

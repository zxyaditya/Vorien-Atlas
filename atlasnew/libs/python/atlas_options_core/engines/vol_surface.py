"""Volatility Surface Engine.

Constructs, interpolates, and analyses the 3D Implied Volatility surface:
    Axes: Strike (moneyness) × Expiration (DTE) × IV level

All functions operate on a DataFrame of options chain snapshots.
Relies on Black-Scholes IV inversion from black_scholes.py.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from typing import Optional, Tuple
from scipy.interpolate import RectBivariateSpline, griddata


# ─────────────────────────────────────────────────────────────────────
# Surface Construction
# ─────────────────────────────────────────────────────────────────────

def build_iv_surface(chain_df: pd.DataFrame) -> pd.DataFrame:
    """Build the IV surface from an options chain snapshot.

    Args:
        chain_df: DataFrame with columns [strike, dte, iv, option_type].
                  One row per contract. IV must already be computed (not NaN).

    Returns:
        Pivot table: rows = unique strikes, columns = unique DTEs, values = IV.
    """
    valid = chain_df.dropna(subset=["iv"])
    valid = valid[valid["iv"] > 0]
    surface = valid.pivot_table(
        values="iv", index="strike", columns="dte", aggfunc="mean"
    )
    return surface


def atm_iv(chain_df: pd.DataFrame, spot: float) -> float:
    """At-the-money implied volatility from the nearest-strike front-month contract."""
    valid = chain_df.dropna(subset=["iv"])
    valid = valid[valid["iv"] > 0]
    if valid.empty:
        return float("nan")
    # Nearest strike to spot, shortest expiry
    valid = valid.copy()
    valid["moneyness_dist"] = (valid["strike"] - spot).abs()
    valid = valid.sort_values(["dte", "moneyness_dist"])
    return float(valid.iloc[0]["iv"])


def skew_25d(chain_df: pd.DataFrame, spot: float,
             front_dte_max: int = 45) -> float:
    """25-delta Skew: put_iv(25d) - call_iv(25d).

    Positive skew = market paying up for downside protection (fear gauge).
    Negative skew = market complacent or bullish.
    """
    front = chain_df[chain_df["dte"] <= front_dte_max].copy()
    if front.empty:
        return float("nan")

    # Approximate 25-delta by moneyness
    front["moneyness"] = front["strike"] / spot

    # 25-delta put: strike ~5-10% OTM below spot
    puts = front[(front["option_type"] == "put") & (front["moneyness"] < 0.97)]
    calls = front[(front["option_type"] == "call") & (front["moneyness"] > 1.03)]

    if puts.empty or calls.empty:
        return float("nan")

    # Pick the nearest to 25-delta (typically ~5% OTM on each side)
    put_25d = puts.loc[(puts["moneyness"] - 0.95).abs().idxmin(), "iv"]
    call_25d = calls.loc[(calls["moneyness"] - 1.05).abs().idxmin(), "iv"]
    return float(put_25d - call_25d)


def butterfly_spread(chain_df: pd.DataFrame, spot: float,
                     front_dte_max: int = 45) -> float:
    """25-delta Butterfly Spread: (put_25d_iv + call_25d_iv) / 2 - atm_iv.

    Measures the curvature (convexity) of the volatility smile.
    High butterfly = fat tails priced in. Low butterfly = leptokurtic pricing.
    """
    front = chain_df[chain_df["dte"] <= front_dte_max].copy()
    if front.empty:
        return float("nan")
    front["moneyness"] = front["strike"] / spot

    atm = front.loc[(front["moneyness"] - 1.0).abs().idxmin(), "iv"]
    puts = front[(front["option_type"] == "put")]
    calls = front[(front["option_type"] == "call")]
    if puts.empty or calls.empty:
        return float("nan")

    put_25d_iv = puts.loc[(puts["moneyness"] - 0.95).abs().idxmin(), "iv"]
    call_25d_iv = calls.loc[(calls["moneyness"] - 1.05).abs().idxmin(), "iv"]
    return float((put_25d_iv + call_25d_iv) / 2.0 - atm)


def term_structure_slope(chain_df: pd.DataFrame, spot: float) -> float:
    """Volatility Term Structure Slope: back_iv - front_iv.

    Positive = contango (vol term structure in normal upward slope).
    Negative = backwardation (front-month vol is elevated — fear event).
    """
    valid = chain_df.dropna(subset=["iv"])
    valid = valid[valid["iv"] > 0].copy()
    valid["moneyness"] = (valid["strike"] / spot - 1.0).abs()
    atm_filter = valid[valid["moneyness"] < 0.03]  # within 3% of spot
    if atm_filter.empty:
        return float("nan")
    by_dte = atm_filter.groupby("dte")["iv"].mean().sort_index()
    if len(by_dte) < 2:
        return float("nan")
    return float(by_dte.iloc[-1] - by_dte.iloc[0])


def risk_reversal_25d(chain_df: pd.DataFrame, spot: float,
                      front_dte_max: int = 45) -> float:
    """25-delta Risk Reversal: call_25d_iv - put_25d_iv.

    Opposite sign of skew. Positive = calls bid up (bullish sentiment).
    Negative = puts bid up (bearish/fear sentiment).
    """
    s = skew_25d(chain_df, spot, front_dte_max)
    return -s if not math.isnan(s) else float("nan")


# ─────────────────────────────────────────────────────────────────────
# Realized vs Implied Volatility
# ─────────────────────────────────────────────────────────────────────

def realized_vol(spot_series: pd.Series, window: int = 30) -> pd.Series:
    """Annualised close-to-close realized volatility from spot prices."""
    log_ret = np.log(spot_series / spot_series.shift(1))
    return log_ret.rolling(window, min_periods=window).std(ddof=1) * math.sqrt(252)


def vrp_spread(iv_series: pd.Series, spot_series: pd.Series,
               rv_window: int = 30) -> pd.Series:
    """Volatility Risk Premium: IV - Realized_Vol.

    Positive VRP = implied vol is overpriced relative to actual realized vol.
    This is the premium that systematic volatility sellers harvest over time.
    """
    rv = realized_vol(spot_series, rv_window)
    return iv_series - rv


def vrp_zscore(iv_series: pd.Series, spot_series: pd.Series,
               rv_window: int = 30, z_window: int = 90) -> pd.Series:
    """Z-score of VRP over a rolling window.

    Extreme positive z-score = premium extremely overpriced → sell vol.
    Extreme negative z-score = premium extremely cheap → buy vol.
    """
    vrp = vrp_spread(iv_series, spot_series, rv_window)
    mu = vrp.rolling(z_window, min_periods=z_window).mean()
    sigma = vrp.rolling(z_window, min_periods=z_window).std(ddof=1).replace(0, np.nan)
    return ((vrp - mu) / sigma).fillna(0.0)


# ─────────────────────────────────────────────────────────────────────
# IV Percentile Rank
# ─────────────────────────────────────────────────────────────────────

def iv_rank(iv_series: pd.Series, window: int = 252) -> pd.Series:
    """IV Rank (IVR): percentile of current ATM IV vs past N periods.

    IVR = (IV_now - IV_min_N) / (IV_max_N - IV_min_N) * 100

    IVR > 80 = extremely high vol → potential sell signal.
    IVR < 20 = extremely low vol → potential buy signal.
    """
    iv_min = iv_series.rolling(window, min_periods=window).min()
    iv_max = iv_series.rolling(window, min_periods=window).max()
    rng = (iv_max - iv_min).replace(0, np.nan)
    return ((iv_series - iv_min) / rng * 100).fillna(0.0)


def iv_percentile(iv_series: pd.Series, window: int = 252) -> pd.Series:
    """IV Percentile: fraction of past N days where IV was below today's IV."""
    return iv_series.rolling(window, min_periods=window).rank(pct=True) * 100

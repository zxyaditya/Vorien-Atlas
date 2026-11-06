"""Options HFT Microstructure Engine.

Institutional-grade order-flow analysis specifically for the options market.
Identifies informed flow, adverse selection, and dealer positioning.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from atlas_options_core.engines.black_scholes import bs_gamma


# ─────────────────────────────────────────────────────────────────────
# Gamma Exposure (GEX)
# ─────────────────────────────────────────────────────────────────────

def gamma_exposure_profile(chain_df: pd.DataFrame, spot: float,
                           contract_multiplier: float = 1.0) -> pd.Series:
    """Net Dealer Gamma Exposure (GEX) by strike.

    Dealers are short gamma to traders (retail/institutional buyers).
    GEX = Σ over calls: (OI × Gamma × S² × multiplier / 100)
          Σ over puts:  -(OI × Gamma × S² × multiplier / 100)

    Positive GEX = dealers are long gamma → they SELL when market rises, BUY when it falls.
                   This suppresses volatility (market pinning effect).
    Negative GEX = dealers are short gamma → they BUY when market rises, SELL when it falls.
                   This AMPLIFIES volatility (gamma squeeze / blow-off).
    """
    out = chain_df.copy()
    T = (out["dte"] / 365.0).clip(lower=1e-6)
    gex_vals = []
    for (_, row), t in zip(out.iterrows(), T):
        g = bs_gamma(float(row.spot), float(row.strike), float(t), 0.0, float(row.iv))
        notional = g * (spot ** 2) * contract_multiplier / 100.0
        oi = float(row.get("open_interest", 1.0))
        sign = 1.0 if row.option_type == "call" else -1.0
        gex_vals.append(sign * oi * notional)

    out["gex"] = gex_vals
    return out.groupby("strike")["gex"].sum()


def net_gex(chain_df: pd.DataFrame, spot: float,
            contract_multiplier: float = 1.0) -> float:
    """Aggregate net GEX across all strikes.

    Returns a single scalar: total dealer gamma positioning.
    """
    profile = gamma_exposure_profile(chain_df, spot, contract_multiplier)
    return float(profile.sum())


def gamma_flip_level(chain_df: pd.DataFrame, spot: float,
                     contract_multiplier: float = 1.0) -> float:
    """The spot price where aggregate GEX crosses zero.

    Below the gamma flip → dealers are short gamma → volatility amplification.
    Above the gamma flip → dealers are long gamma → volatility suppression.

    This level acts as a strong magnetic attractor in options-heavy markets.
    """
    profile = gamma_exposure_profile(chain_df, spot, contract_multiplier)
    if profile.empty:
        return float("nan")

    # Cumulative sum from lowest to highest strike
    strikes = profile.index.values
    cum_gex = profile.values.cumsum()

    # Find the crossing point (sign change)
    for i in range(1, len(cum_gex)):
        if cum_gex[i - 1] <= 0 <= cum_gex[i] or cum_gex[i - 1] >= 0 >= cum_gex[i]:
            # Linear interpolation
            s0, s1 = strikes[i - 1], strikes[i]
            g0, g1 = cum_gex[i - 1], cum_gex[i]
            if g1 != g0:
                return float(s0 + (0 - g0) * (s1 - s0) / (g1 - g0))
            return float((s0 + s1) / 2)

    return float("nan")


def max_pain(chain_df: pd.DataFrame) -> float:
    """Max Pain: the strike where aggregate option holder value is MINIMIZED.

    At expiry, if spot = max_pain, all option holders (combined) suffer
    maximum loss. Dealers / writers benefit most. The market has a subtle
    gravitational pull toward max pain near expiry due to delta hedging.
    """
    strikes = chain_df["strike"].unique()
    min_pain = float("inf")
    max_pain_strike = float("nan")

    for target in strikes:
        calls = chain_df[chain_df["option_type"] == "call"]
        puts = chain_df[chain_df["option_type"] == "put"]
        call_pain = ((calls["strike"] - target).clip(lower=0) * calls.get("open_interest", 1)).sum()
        put_pain = ((target - puts["strike"]).clip(lower=0) * puts.get("open_interest", 1)).sum()
        total = call_pain + put_pain
        if total < min_pain:
            min_pain = total
            max_pain_strike = target

    return float(max_pain_strike)


# ─────────────────────────────────────────────────────────────────────
# Order Flow Analysis
# ─────────────────────────────────────────────────────────────────────

def put_call_volume_ratio(chain_df: pd.DataFrame,
                          front_dte_max: int = 45) -> float:
    """Put/Call Volume Ratio for front-month options.

    > 1.0 = more put volume (bearish hedging / fear).
    < 1.0 = more call volume (bullish speculation).
    """
    front = chain_df[chain_df["dte"] <= front_dte_max]
    if front.empty:
        return float("nan")
    call_vol = front[front["option_type"] == "call"]["volume"].sum()
    put_vol = front[front["option_type"] == "put"]["volume"].sum()
    if call_vol == 0:
        return float("nan")
    return float(put_vol / call_vol)


def put_call_oi_ratio(chain_df: pd.DataFrame) -> float:
    """Put/Call Open Interest Ratio across all expirations.

    Reflects longer-term institutional positioning vs pure day-trading.
    """
    call_oi = chain_df[chain_df["option_type"] == "call"]["open_interest"].sum()
    put_oi = chain_df[chain_df["option_type"] == "put"]["open_interest"].sum()
    if call_oi == 0:
        return float("nan")
    return float(put_oi / call_oi)


def options_bid_ask_imbalance(chain_df: pd.DataFrame) -> pd.Series:
    """Bid-Ask Depth Imbalance for each contract.

    (bid_size - ask_size) / (bid_size + ask_size) ∈ [-1, +1]
    Positive = more bids than asks → buying pressure on that contract.
    """
    b = chain_df.get("bid_size", pd.Series(1, index=chain_df.index))
    a = chain_df.get("ask_size", pd.Series(1, index=chain_df.index))
    total = (b + a).replace(0, np.nan)
    return ((b - a) / total).fillna(0.0)


def options_spread_pct(chain_df: pd.DataFrame) -> pd.Series:
    """Bid-Ask Spread as a percentage of mid-price.

    High spread = illiquid → adverse selection risk.
    """
    bid = chain_df.get("bid", pd.Series(np.nan, index=chain_df.index))
    ask = chain_df.get("ask", pd.Series(np.nan, index=chain_df.index))
    mid = (bid + ask) / 2.0
    spread = (ask - bid) / mid.replace(0, np.nan)
    return spread.fillna(0.0)


# ─────────────────────────────────────────────────────────────────────
# Rolling Chain-Level Features (time-series)
# ─────────────────────────────────────────────────────────────────────

def rolling_put_call_ratio(pcr_series: pd.Series, window: int = 20) -> pd.Series:
    """Rolling mean of the put/call ratio time series."""
    return pcr_series.rolling(window, min_periods=window).mean()


def rolling_gex_zscore(gex_series: pd.Series, window: int = 30) -> pd.Series:
    """Z-score of net GEX time series.

    Extreme negative z-score = dealers unusually short gamma → vol squeeze risk.
    """
    mu = gex_series.rolling(window, min_periods=window).mean()
    sigma = gex_series.rolling(window, min_periods=window).std(ddof=1).replace(0, np.nan)
    return ((gex_series - mu) / sigma).fillna(0.0)

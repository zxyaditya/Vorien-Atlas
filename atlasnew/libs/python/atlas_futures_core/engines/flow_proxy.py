"""Microstructure primitives engine (Book 1 Invariant 6.5-compliant).

Only pure mathematical functions over OHLCV bars. Nothing named after
an interpretation of what the number means. The Microstructure module
registers these under names that describe what is computed, not what
it is presumed to mean.

No 'absorption', 'aggression', 'auction efficiency', 'acceptance',
'rejection' functions here — those are Layer 2/3 interpretations.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series


def body(df) -> pd.Series:
    return (df["close"] - df["open"]).astype(float)


def abs_body(df) -> pd.Series:
    return body(df).abs()


def bar_range(df) -> pd.Series:
    return (df["high"] - df["low"]).astype(float)


def upper_wick(df) -> pd.Series:
    return (df["high"] - df[["open", "close"]].max(axis=1)).astype(float)


def lower_wick(df) -> pd.Series:
    return (df[["open", "close"]].min(axis=1) - df["low"]).astype(float)


def body_over_range(df) -> pd.Series:
    """|body| / range ∈ [0,1]. Pure measurement."""
    rng = bar_range(df).replace(0, np.nan)
    return (abs_body(df) / rng).clip(0, 1)


def signed_body_over_range(df) -> pd.Series:
    """body / range ∈ [-1, +1]. Pure signed measurement."""
    rng = bar_range(df).replace(0, np.nan)
    return (body(df) / rng).clip(-1, 1)


def body_position_in_range(df) -> pd.Series:
    """Midpoint(open,close) location inside [low, high] ∈ [0,1]."""
    rng = bar_range(df).replace(0, np.nan)
    mid = (df["open"] + df["close"]) / 2.0
    return ((mid - df["low"]) / rng).clip(0, 1)


def upper_wick_ratio(df) -> pd.Series:
    rng = bar_range(df).replace(0, np.nan)
    return (upper_wick(df) / rng).clip(0, 1)


def lower_wick_ratio(df) -> pd.Series:
    rng = bar_range(df).replace(0, np.nan)
    return (lower_wick(df) / rng).clip(0, 1)


def wick_difference_ratio(df) -> pd.Series:
    """(upper - lower) / (upper + lower) ∈ [-1, +1]. Pure measurement."""
    u = upper_wick(df); l = lower_wick(df)
    tot = (u + l).replace(0, np.nan)
    return ((u - l) / tot).clip(-1, 1)


def signed_volume_body(df) -> pd.Series:
    """sign(body) × volume × |body|/range — signed magnitude, no interpretation."""
    return np.sign(body(df)) * df["volume"].astype(float) * body_over_range(df)


def up_body_volume(df) -> pd.Series:
    """volume weighted by max(body,0)/range. Non-negative magnitude."""
    rng = bar_range(df).replace(0, np.nan)
    return (body(df).clip(lower=0) / rng).clip(0, 1) * df["volume"]


def down_body_volume(df) -> pd.Series:
    rng = bar_range(df).replace(0, np.nan)
    return ((-body(df)).clip(lower=0) / rng).clip(0, 1) * df["volume"]


def volume_rank_pct(df, w: int) -> pd.Series:
    v = df["volume"].astype(float)
    return v.rolling(w, min_periods=w).rank(pct=True)


def participation_ratio(df, w: int) -> pd.Series:
    """V / MA_w(V). Pure ratio."""
    v = df["volume"].astype(float)
    mv = v.rolling(w, min_periods=w).mean().replace(0, np.nan)
    return v / mv


def turnover(df) -> pd.Series:
    """Dollar turnover per bar = close × volume. Raw magnitude."""
    return (df["close"].astype(float) * df["volume"].astype(float))


def execution_imbalance_ratio(df, w: int) -> pd.Series:
    """Σ signed_body / Σ |body| over w bars ∈ [-1, +1]. Pure measurement of
    the fraction of intra-bar movement that resolved directionally."""
    num = body(df).rolling(w, min_periods=w).sum()
    den = abs_body(df).rolling(w, min_periods=w).sum().replace(0, np.nan)
    return (num / den).clip(-1, 1)


def range_covered_ratio(df, w: int) -> pd.Series:
    """|Σ signed body| / Σ range ∈ [0,1]. Pure measurement (efficient movement)."""
    num = body(df).rolling(w, min_periods=w).sum().abs()
    den = bar_range(df).rolling(w, min_periods=w).sum().replace(0, np.nan)
    return (num / den).clip(0, 1)


def vpin(df, w: int) -> pd.Series:
    """Volume-Synchronized Probability of Informed Trading (VPIN) proxy.
    
    Using Tick Rule on OHLCV:
    Buy Volume = Volume if Close > Prev Close else 0
    Sell Volume = Volume if Close < Prev Close else 0
    VPIN = Σ|Buy - Sell| / Σ(Buy + Sell) over w bars.
    """
    v = df["volume"].astype(float)
    c = df["close"].astype(float)
    
    # Tick rule
    dp = c.diff()
    buy_vol = np.where(dp > 0, v, 0)
    sell_vol = np.where(dp < 0, v, 0)
    
    buy_vol = pd.Series(buy_vol, index=df.index)
    sell_vol = pd.Series(sell_vol, index=df.index)
    
    sum_buy = buy_vol.rolling(w, min_periods=w).sum()
    sum_sell = sell_vol.rolling(w, min_periods=w).sum()
    
    total_active_vol = (sum_buy + sum_sell).replace(0, np.nan)
    return (sum_buy - sum_sell).abs() / total_active_vol


def vwap_zscore(df, w: int) -> pd.Series:
    """VWAP Deviation Z-Score: (P_t - VWAP_t) / sigma_t."""
    c = df["close"].astype(float)
    v = df["volume"].astype(float)
    
    cum_pv = (c * v).rolling(w, min_periods=w).sum()
    cum_v = v.rolling(w, min_periods=w).sum()
    vwap = cum_pv / cum_v.replace(0, np.nan)
    
    price_std = c.rolling(w, min_periods=w).std()
    z = (c - vwap) / price_std.replace(0, np.nan)
    return z.fillna(0.0)


# ══════════════════════════════════════════════════════════════════════
# HFT-GRADE MICROSTRUCTURE FEATURES
# These approximate institutional order-flow dynamics from OHLCV data.
# ══════════════════════════════════════════════════════════════════════

def trade_imbalance_velocity(df, w: int) -> pd.Series:
    """Rate of change of order-flow imbalance (OFI velocity).

    Measures how quickly the buy/sell imbalance is ACCELERATING.
    A rapidly increasing imbalance (dOFI/dt > 0) signals informed
    order flow arriving in the same direction — a key HFT entry signal.

    Formula: d/dt [ (BuyVol - SellVol) / TotalVol ] over w bars.
    """
    v = df["volume"].astype(float)
    c = df["close"].astype(float)
    dp = c.diff()

    buy_vol = np.where(dp > 0, v, np.where(dp == 0, v * 0.5, 0.0))
    sell_vol = np.where(dp < 0, v, np.where(dp == 0, v * 0.5, 0.0))
    buy_vol = pd.Series(buy_vol, index=df.index)
    sell_vol = pd.Series(sell_vol, index=df.index)

    rb = buy_vol.rolling(w, min_periods=w).sum()
    rs = sell_vol.rolling(w, min_periods=w).sum()
    total = (rb + rs).replace(0, np.nan)
    ofi = (rb - rs) / total
    return ofi.diff(1).fillna(0.0)


def adverse_selection_cost(df, w: int) -> pd.Series:
    """Adverse Selection Cost (ASC) proxy.

    Approximates the cost of trading against informed participants.
    Measured as the covariance between the signed order flow and the
    subsequent price change. A high ASC means buying is consistently
    followed by price increases (or selling is followed by declines) —
    indicating that order flow is informationally toxic.

    Formula: Cov(SignedVolume_t, Return_{t+1}) over w bars.
    """
    v = df["volume"].astype(float)
    c = df["close"].astype(float)
    r_curr = c.pct_change()
    sv_prev = (v * np.sign(c.diff())).shift(1).fillna(0)
    cov = sv_prev.rolling(w, min_periods=w).cov(r_curr)
    return cov.fillna(0.0)


def volume_clock_deviation(df, w: int) -> pd.Series:
    """Volume Clock Deviation — deviation from expected volume per bar.

    In HFT, time is measured in "volume time" not calendar time.
    When volume in a single bar is much higher than average, it signals
    that a compressed amount of "event time" has passed — usually
    driven by institutional execution or news. This is a proxy for
    event-time acceleration.

    Formula: (V_t - MA_w(V)) / std_w(V) = volume z-score.
    """
    v = df["volume"].astype(float)
    mu = v.rolling(w, min_periods=w).mean()
    sigma = v.rolling(w, min_periods=w).std(ddof=1).replace(0, np.nan)
    return ((v - mu) / sigma).fillna(0.0)


def bar_efficiency_ratio(df, w: int) -> pd.Series:
    """Bar Efficiency Ratio (BER).

    Net directional displacement over w bars divided by sum of absolute
    per-bar displacements. A ratio near 1.0 = strongly directional trend
    (high efficiency). A ratio near 0.0 = choppy/mean-reverting market.

    This is the core input for the Kaufman Adaptive Moving Average and
    is a direct proxy for trend vs. noise at the measured timescale.
    """
    c = df["close"].astype(float)
    net = c.diff(w).abs()
    path = c.diff(1).abs().rolling(w, min_periods=w).sum().replace(0, np.nan)
    return (net / path).clip(0, 1).fillna(0.0)


def micro_price_momentum(df, w_fast: int, w_slow: int) -> pd.Series:
    """Micro-Price Momentum: VWAP cross-timeframe signal.

    The difference between a fast VWAP and a slow VWAP, normalized
    by price volatility. When fast VWAP > slow VWAP and the gap is
    growing, it indicates strong, volume-weighted directional momentum —
    the institutional analogue of a simple MA crossover.

    Formula: (VWAP_fast - VWAP_slow) / sigma_slow
    """
    c = df["close"].astype(float)
    v = df["volume"].astype(float)

    def _vwap(w):
        return (c * v).rolling(w, min_periods=w).sum() / \
               v.rolling(w, min_periods=w).sum().replace(0, np.nan)

    vwap_f = _vwap(w_fast)
    vwap_s = _vwap(w_slow)
    sigma = c.rolling(w_slow, min_periods=w_slow).std(ddof=1).replace(0, np.nan)
    return ((vwap_f - vwap_s) / sigma).fillna(0.0)


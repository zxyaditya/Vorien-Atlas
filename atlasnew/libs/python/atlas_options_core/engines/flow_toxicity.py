"""Flow Toxicity Engine.

Detects informed institutional order flow in the options market.
Adverse selection, block trade identification, smart money signals.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_options_core.engines.statistics import rolling_corr


# ─────────────────────────────────────────────────────────────────────
# Adverse Selection
# ─────────────────────────────────────────────────────────────────────

def adverse_selection_score(trades_df: pd.DataFrame, window: int = 50) -> pd.Series:
    """Adverse Selection Cost: Cov(SignedFlow_t, FutureReturn_{t+1}).

    If trades that arrive as BUYs consistently precede price increases,
    buyers are informed → adverse selection is high.
    """
    sv = trades_df.get("signed_volume",
                       trades_df["volume"] * np.sign(trades_df["price"].diff()).fillna(0))
    r_fwd = trades_df["price"].pct_change().shift(-1)
    return sv.rolling(window, min_periods=window).cov(r_fwd).fillna(0.0)


def options_vpin(trades_df: pd.DataFrame, bucket_size: int = 50) -> pd.Series:
    """Options VPIN (Volume-Synchronized Probability of Informed Trading).

    Divides trades into equal-volume buckets and measures the imbalance
    between buyer-initiated and seller-initiated volume in each bucket.
    High VPIN → high probability of informed trading → exit or avoid.
    """
    v = trades_df["volume"].astype(float)
    price = trades_df["price"].astype(float)
    dp = price.diff().fillna(0)
    buy_vol = np.where(dp >= 0, v, 0.0)
    sell_vol = np.where(dp < 0, v, 0.0)

    buy_s = pd.Series(buy_vol, index=trades_df.index)
    sell_s = pd.Series(sell_vol, index=trades_df.index)

    rb = buy_s.rolling(bucket_size, min_periods=bucket_size).sum()
    rs = sell_s.rolling(bucket_size, min_periods=bucket_size).sum()
    total = (rb + rs).replace(0, np.nan)
    return ((rb - rs).abs() / total).fillna(0.0)


# ─────────────────────────────────────────────────────────────────────
# Block Trade Detection
# ─────────────────────────────────────────────────────────────────────

def block_trade_detector(trades_df: pd.DataFrame,
                          threshold_percentile: float = 95.0) -> pd.Series:
    """Flag trades above the Nth percentile in size as institutional block prints.

    Returns a binary Series: 1 = block trade, 0 = retail trade.
    """
    v = trades_df["volume"].astype(float)
    cutoff = v.expanding(min_periods=10).quantile(threshold_percentile / 100.0)
    return (v >= cutoff).astype(float)


def block_trade_frequency(trades_df: pd.DataFrame, window: int = 50,
                           threshold_percentile: float = 95.0) -> pd.Series:
    """Rolling frequency of block trades over past N trades."""
    flags = block_trade_detector(trades_df, threshold_percentile)
    return flags.rolling(window, min_periods=window).mean()


# ─────────────────────────────────────────────────────────────────────
# Smart Money Indicator
# ─────────────────────────────────────────────────────────────────────

def smart_money_indicator(trades_df: pd.DataFrame,
                           spot_series: pd.Series,
                           window: int = 30) -> pd.Series:
    """Smart Money Indicator: correlation between net options flow and future spot return.

    If net call-buying (bullish flow) consistently precedes spot rallies,
    options traders have informational edge.
    """
    if "option_type" not in trades_df.columns:
        return pd.Series(0.0, index=trades_df.index)

    # Net call flow: call buys - put buys (signed by direction)
    is_call = (trades_df["option_type"] == "call").astype(float)
    is_put = (trades_df["option_type"] == "put").astype(float)
    v = trades_df["volume"].astype(float)
    dp = trades_df["price"].diff().fillna(0)
    buy_flag = (dp >= 0).astype(float)

    net_call_flow = (buy_flag * v * is_call - (1 - buy_flag) * v * is_call
                     - buy_flag * v * is_put + (1 - buy_flag) * v * is_put)

    future_spot_ret = spot_series.pct_change().shift(-1).reindex(trades_df.index)
    return net_call_flow.rolling(window, min_periods=window).corr(future_spot_ret).fillna(0.0)


# ─────────────────────────────────────────────────────────────────────
# Spot-Volatility Correlation (Leverage Effect)
# ─────────────────────────────────────────────────────────────────────

def spot_vol_correlation(spot_series: pd.Series, iv_series: pd.Series,
                          window: int = 30) -> pd.Series:
    """Spot-Vol Correlation (Leverage Effect): ρ(dS, dIV).

    For equities and crypto: typically negative (spot falls → vol rises).
    A positive correlation is unusual and signals a vol-driven rally (demand shock).

    This is a critical real-time input for selecting option direction.
    """
    dS = spot_series.pct_change()
    dIV = iv_series.diff()
    return rolling_corr(dS, dIV, window)


def hurst_exponent_flow(trades_df: pd.DataFrame, window: int = 100) -> pd.Series:
    """Hurst Exponent of Options Flow Direction.

    Applies DFA-style Hurst estimation to the binary buy/sell sequence of trades.
    H > 0.5 → persistent (institutional block-splitting algorithm detected)
    H ≈ 0.5 → random (retail noise)
    H < 0.5 → mean-reverting (market maker inventory management)
    """
    price = trades_df["price"].astype(float)
    dp = price.diff().fillna(0)
    direction = np.sign(dp).fillna(0)

    def _hurst(a: np.ndarray) -> float:
        if len(a) < 20:
            return 0.5
        n = len(a)
        lags = range(2, min(20, n // 2))
        rs_vals = []
        for lag in lags:
            chunks = [a[i:i + lag] for i in range(0, n - lag, lag)]
            if not chunks:
                continue
            rs = []
            for chunk in chunks:
                if len(chunk) < 2:
                    continue
                mean = chunk.mean()
                dev = chunk - mean
                r = dev.cumsum()
                rng = r.max() - r.min()
                std = chunk.std(ddof=1)
                if std > 0:
                    rs.append(rng / std)
            if rs:
                rs_vals.append((lag, np.mean(rs)))
        if len(rs_vals) < 2:
            return 0.5
        lags_arr = np.log([x[0] for x in rs_vals])
        rs_arr = np.log([x[1] for x in rs_vals])
        try:
            h = float(np.polyfit(lags_arr, rs_arr, 1)[0])
            return max(0.0, min(1.0, h))
        except Exception:
            return 0.5

    return direction.rolling(window, min_periods=window).apply(
        lambda a: _hurst(np.asarray(a)), raw=True).fillna(0.5)

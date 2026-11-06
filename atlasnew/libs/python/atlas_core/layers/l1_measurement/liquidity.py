"""Liquidity Module — Layer 1.

Liquidity = "how easily can this asset be traded without moving the price."

Without order-book data we derive liquidity proxies from OHLCV:
  • Roll spread estimator          → serial-covariance-based spread
  • High-Low spread estimator      → range-based spread
  • Amihud illiquidity ratio       → |r| / dollar-volume
  • Kyle's lambda proxy            → |r| / signed-volume
  • Turnover proxy                 → volume / rolling mean volume
  • Effective range ratio          → intra-bar range / inter-bar path

All 11 Perspectives applied to the resulting illiquidity time-series.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.engines import statistics as st, motion as mo, geometry as ge
from atlas_core.engines import distribution as di, normalization as no
from atlas_core.engines import information as info, technical as tc

MODULE = "liquidity"


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["open", "high", "low", "close", "volume"], params=params or {},
        complexity=complexity, fn=fn,
    ))


# ═══════════════════════════════════════════════════════════════════════
# Base building blocks
# ═══════════════════════════════════════════════════════════════════════
def _log_ret(df):
    return np.log(df["close"] / df["close"].shift(1))


def _dollar_vol(df):
    return df["close"] * df["volume"]


def _signed_vol(df):
    return df["volume"] * np.sign(df["close"].diff()).fillna(0)


def _roll_spread(df, w):
    """Roll (1984): 2·√(-cov(Δp, Δp_{-1})) when negative; else NaN."""
    dp = df["close"].diff()
    def _rs(a):
        n = len(a)
        if n < 3:
            return np.nan
        c = np.cov(a[:-1], a[1:], ddof=1)[0, 1]
        return 2 * np.sqrt(-c) if c < 0 else np.nan
    return dp.rolling(w, min_periods=w).apply(_rs, raw=True)


def _hl_spread(df):
    """Simple range-based spread proxy per bar."""
    return 2 * (np.log(df["high"]) - np.log(df["low"]))


def _amihud(df, w):
    """Amihud (2002): mean(|r| / dollar_volume) over w bars."""
    dv = _dollar_vol(df).replace(0, np.nan)
    return (_log_ret(df).abs() / dv).rolling(w, min_periods=w).mean()


def _kyle_lambda(df, w):
    """|r| / |signed_volume| — price impact per unit of order flow.
    Aggregated as rolling mean to smooth zero-signed-volume bars."""
    sv = _signed_vol(df).abs().replace(0, np.nan)
    return (_log_ret(df).abs() / sv).rolling(w, min_periods=w).mean()


def _turnover(df, w):
    """Volume relative to rolling baseline — activity intensity."""
    return df["volume"] / df["volume"].rolling(w, min_periods=w).mean() \
        .replace(0, np.nan)


def _effective_range_ratio(df, w):
    """(H-L) / (|Δclose| rolling sum) — intra-bar vs inter-bar movement."""
    ib = (df["high"] - df["low"]).rolling(w, min_periods=w).sum()
    xb = df["close"].diff().abs().rolling(w, min_periods=w).sum().replace(0, np.nan)
    return ib / xb


# Canonical illiquidity reference (Amihud @ 20) for cross-Perspective use
def _illiq_ref(df, w=20):
    return _amihud(df, w)


# ═══════════════════════════════════════════════════════════════════════
# MAGNITUDE — canonical estimators
# ═══════════════════════════════════════════════════════════════════════
_reg("liquidity.magnitude.hl_spread",
     "High-Low Spread", "Magnitude", "spread",
     "Per-bar range-based spread proxy.", "2·(ln H − ln L)",
     "Wider = wider effective bid-ask.",
     _hl_spread)

for w in [20, 50]:
    _reg(f"liquidity.magnitude.roll_spread_{w}",
         f"Roll Spread ({w})", "Magnitude", "spread",
         f"Roll (1984) spread from serial covariance over {w} bars.",
         "2·√(-cov(Δp,Δp_{-1}))",
         "Serial-covariance implied bid-ask spread.",
         (lambda w_: (lambda df: _roll_spread(df, w_)))(w),
         params={"window": w})

    _reg(f"liquidity.magnitude.amihud_{w}",
         f"Amihud Illiquidity ({w})", "Magnitude", "impact",
         f"Amihud illiquidity: mean(|r|/dollar_vol) over {w}.",
         "mean(|r| / (P·V))",
         "Higher = more price impact per dollar traded.",
         (lambda w_: (lambda df: _amihud(df, w_)))(w),
         params={"window": w})

    _reg(f"liquidity.magnitude.kyle_lambda_{w}",
         f"Kyle Lambda Proxy ({w})", "Magnitude", "impact",
         f"|r| / |signed_volume| rolling mean over {w}.",
         "mean(|r| / |V·sign(r)|)",
         "Approximates the price impact per unit of order flow.",
         (lambda w_: (lambda df: _kyle_lambda(df, w_)))(w),
         params={"window": w})

    _reg(f"liquidity.magnitude.turnover_{w}",
         f"Turnover Ratio ({w})", "Magnitude", "activity",
         f"Volume / mean(V)_{w}.", "V / mean(V)_w",
         "> 1 = active bar; < 1 = quiet bar.",
         (lambda w_: (lambda df: _turnover(df, w_)))(w),
         params={"window": w})

    _reg(f"liquidity.magnitude.effective_range_{w}",
         f"Effective Range Ratio ({w})", "Magnitude", "microstructure",
         f"Σ(H-L)/Σ|Δclose| over {w}.",
         "Σ(H-L) / Σ|Δclose|",
         "How much price 'wiggled' vs how much it net-moved. High = choppy execution zone.",
         (lambda w_: (lambda df: _effective_range_ratio(df, w_)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# MOTION
# ═══════════════════════════════════════════════════════════════════════
for dt in [1, 5]:
    _reg(f"liquidity.motion.amihud_log_ret_{dt}",
         f"Amihud Log-Return ({dt})", "Motion", "illiq_change",
         f"Log-return of Amihud illiquidity over {dt} bars.",
         "ln(A_t/A_{t-dt})",
         "Multiplicative change in illiquidity.",
         (lambda dt_: (lambda df: mo.log_return(_illiq_ref(df), dt_)))(dt),
         params={"dt": dt})

_reg("liquidity.motion.amihud_ema_20",
     "EMA(Amihud, 20)", "Motion", "smoothed",
     "Recency-weighted illiquidity level.",
     "EMA_20(A)",
     "Smoothed illiquidity — reduces spikes from single bars.",
     lambda df: tc.ema(_illiq_ref(df), 20))


# ═══════════════════════════════════════════════════════════════════════
# GEOMETRY
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50]:
    _reg(f"liquidity.geometry.amihud_path_length_{w}",
         f"Amihud Path Length ({w})", "Geometry", "trajectory",
         f"Σ|ΔA| over {w}.", "Σ|ΔAmihud|",
         "Total variation of illiquidity across the window.",
         (lambda w_: (lambda df: ge.path_length(_illiq_ref(df), w_)))(w),
         params={"window": w})

    _reg(f"liquidity.geometry.amihud_straightness_{w}",
         f"Amihud Straightness ({w})", "Geometry", "trajectory",
         f"|net ΔA| / path length over {w}.",
         "|A_t - A_{t-w}|/Σ|ΔA|",
         "1 = monotonic illiquidity trend, 0 = zig-zag.",
         (lambda w_: (lambda df: ge.straightness(_illiq_ref(df), w_)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# RELATIVE
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50]:
    _reg(f"liquidity.relative.amihud_dist_ma_{w}",
         f"Amihud vs MA{w}", "Relative", "illiq_baseline",
         f"(A − SMA_w(A)) / SMA_w(A).",
         "(A - SMA_w) / SMA_w",
         "% deviation of illiquidity from its baseline.",
         (lambda w_: (lambda df: (_illiq_ref(df) - st.rolling_mean(_illiq_ref(df), w_)) /
                                 st.rolling_mean(_illiq_ref(df), w_).replace(0, np.nan)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# POSITION
# ═══════════════════════════════════════════════════════════════════════
for w in [50, 100]:
    _reg(f"liquidity.position.amihud_pct_rank_{w}",
         f"Amihud Pct Rank ({w})", "Position", "distribution_position",
         f"Percentile rank of current Amihud within {w} bars.",
         "F̂_w(A_t)",
         "0 = most liquid in window, 1 = least liquid.",
         (lambda w_: (lambda df: di.rolling_percentile_rank(_illiq_ref(df), w_)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50]:
    _reg(f"liquidity.statistics.amihud_mean_{w}",
         f"Mean Amihud ({w})", "Statistics", "moments",
         f"Mean of Amihud over {w} bars.", "mean(A)_w",
         "Average illiquidity in the window.",
         (lambda w_: (lambda df: st.rolling_mean(_illiq_ref(df), w_)))(w),
         params={"window": w})

    _reg(f"liquidity.statistics.amihud_std_{w}",
         f"Std Amihud ({w})", "Statistics", "moments",
         f"Std of Amihud over {w}.", "σ(A)_w",
         "Illiquidity dispersion — bigger = more unstable liquidity.",
         (lambda w_: (lambda df: st.rolling_std(_illiq_ref(df), w_)))(w),
         params={"window": w})

    _reg(f"liquidity.statistics.amihud_zscore_{w}",
         f"Amihud Z-Score ({w})", "Statistics", "standardized",
         f"Standardized Amihud over {w}.",
         "(A - μ)/σ",
         "σ-units from local mean illiquidity.",
         (lambda w_: (lambda df: no.zscore(_illiq_ref(df), w_)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# DISTRIBUTION
# ═══════════════════════════════════════════════════════════════════════
for q in [0.1, 0.5, 0.9]:
    _reg(f"liquidity.distribution.amihud_q{int(q*100)}_100",
         f"Amihud Q{int(q*100)}% (100)", "Distribution", "quantiles",
         f"{int(q*100)}th percentile of Amihud over 100 bars.",
         f"Q_{q}(A)_100", f"{int(q*100)}th percentile illiquidity level.",
         (lambda q_: (lambda df: di.rolling_quantile(_illiq_ref(df), 100, q_)))(q),
         params={"window": 100, "q": q})


# ═══════════════════════════════════════════════════════════════════════
# ENTROPY
# ═══════════════════════════════════════════════════════════════════════
_reg("liquidity.entropy.amihud_shannon_60",
     "Amihud Shannon Entropy (60)", "Entropy", "information",
     "Shannon entropy of Amihud histogram over 60 bars.",
     "-Σ p log p",
     "Uncertainty in the illiquidity distribution.",
     lambda df: st.rolling_entropy(_illiq_ref(df), 60))

_reg("liquidity.entropy.amihud_perm_o3_30",
     "Amihud Permutation Entropy (30)", "Entropy", "ordinal",
     "Permutation entropy (order 3) of Amihud over 30 bars.",
     "H(π)/log(3!)",
     "Ordinal complexity of illiquidity changes.",
     lambda df: info.permutation_entropy(_illiq_ref(df), 30, 3),
     complexity="O(nlogn)")


# ═══════════════════════════════════════════════════════════════════════
# EXPANSION
# ═══════════════════════════════════════════════════════════════════════
_reg("liquidity.expansion.short_long_ratio",
     "Amihud Short/Long Ratio", "Expansion", "multi_scale",
     "10-bar mean Amihud / 50-bar mean Amihud.",
     "mean(A)_10 / mean(A)_50",
     ">1 = short-term illiquidity elevated vs baseline.",
     lambda df: st.rolling_mean(_illiq_ref(df), 10) /
                st.rolling_mean(_illiq_ref(df), 50).replace(0, np.nan))


# ═══════════════════════════════════════════════════════════════════════
# CLUSTERING
# ═══════════════════════════════════════════════════════════════════════
for lag in [1, 5]:
    _reg(f"liquidity.clustering.amihud_acf_lag{lag}",
         f"Amihud ACF lag {lag}", "Clustering", "persistence",
         f"Lag-{lag} autocorrelation of Amihud over 60 bars.",
         f"ρ(A_t, A_{{t-{lag}}})",
         "Illiquidity persistence — high = illiquidity clusters.",
         (lambda lag_: (lambda df: st.rolling_autocorr(_illiq_ref(df), 60, lag_)))(lag),
         params={"lag": lag, "window": 60})


# ═══════════════════════════════════════════════════════════════════════
# REGIME
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50]:
    _reg(f"liquidity.regime.above_ma_{w}",
         f"Amihud Above MA{w}", "Regime", "illiq_regime",
         f"Sign of (A - SMA_{w}(A)).", "sign(A - SMA_w(A))",
         "+1 illiquid regime, -1 liquid regime.",
         (lambda w_: (lambda df: np.sign(_illiq_ref(df) -
                                          st.rolling_mean(_illiq_ref(df), w_))))(w),
         params={"window": w})

# Tercile illiquidity regime
def _illiq_tercile(df):
    a = _illiq_ref(df)
    q33 = a.rolling(200, min_periods=100).quantile(0.33)
    q66 = a.rolling(200, min_periods=100).quantile(0.66)
    out = pd.Series(0.0, index=df.index)
    out[a < q33] = -1.0
    out[a > q66] = 1.0
    return out

_reg("liquidity.regime.tercile_200",
     "Amihud Tercile Regime (200)", "Regime", "illiq_regime",
     "-1 liquid / 0 normal / +1 illiquid via rolling 33/66 quantiles.",
     "sign relative to Q_33, Q_66 over 200",
     "Categorical liquidity state.",
     _illiq_tercile, params={"window": 200})

# Kyle lambda regime (impact regime)
_reg("liquidity.regime.kyle_above_ma_50",
     "Kyle λ Above MA50", "Regime", "impact_regime",
     "Sign of (Kyle_λ − SMA_50(Kyle_λ)).",
     "sign(λ - SMA_50(λ))",
     "+1 elevated impact, -1 normal impact.",
     lambda df: np.sign(_kyle_lambda(df, 20) -
                        st.rolling_mean(_kyle_lambda(df, 20), 50)))

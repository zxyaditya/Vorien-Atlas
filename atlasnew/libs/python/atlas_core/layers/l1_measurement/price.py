"""Price Module — Layer 1. Comprehensive mathematical representation of PRICE.

Depth over breadth. Each Perspective is expanded until its mathematical
search space is well-covered. Parameter sweeps are done only when different
values probe genuinely different timescales of the same mathematical object.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.engines import (
    statistics as st, motion as mo, geometry as ge,
    distribution as di, normalization as no, distance as ds,
)
from atlas_core.engines import fractal as fr, information as info, spectral as sp
from atlas_core.engines import technical as tc
from atlas_core.engines import dsp as dsp
from atlas_core.engines import lmoments as lm
from atlas_core.engines import liquidity as liq
from atlas_core.engines import fractional as fdiff
from atlas_core.engines import distribution as dist
from atlas_core.engines import wavelet as wav

MODULE = "price"


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["close"], params=params or {},
        complexity=complexity, fn=fn,
    ))


def _bulk(cfg):
    """cfg: iterable of tuples (id_, name, persp, family, defn, formula, interp, fn, params)."""
    for row in cfg:
        _reg(*row[:8], params=row[8] if len(row) > 8 else None)


def _p(df):
    return df["close"].astype(float)


# Common window ladders (each window probes a genuinely different horizon)
W_SHORT = [5, 10]
W_MED = [20, 50]
W_LONG = [100, 200]
W_ALL = W_SHORT + W_MED + W_LONG
W_MED_LONG = W_MED + W_LONG

# ═══════════════════════════════════════════════════════════════════════
# MAGNITUDE — "How much?"  (levels, ranges, candle anatomy)
# ═══════════════════════════════════════════════════════════════════════
_reg("price.magnitude.close", "Close", "Magnitude", "level",
     "Observed closing price.", "P_t", "The close price at time t.",
     lambda df: _p(df))
_reg("price.magnitude.open", "Open", "Magnitude", "level",
     "Opening price of the bar.", "O_t", "Bar's opening level.",
     lambda df: df["open"].astype(float))
_reg("price.magnitude.high", "High", "Magnitude", "level",
     "Highest traded price of the bar.", "H_t", "Bar's peak.",
     lambda df: df["high"].astype(float))
_reg("price.magnitude.low", "Low", "Magnitude", "level",
     "Lowest traded price of the bar.", "L_t", "Bar's trough.",
     lambda df: df["low"].astype(float))
_reg("price.magnitude.typical", "Typical Price", "Magnitude", "level",
     "Mean of H, L, C.", "(H+L+C)/3", "Smoothed intraperiod price.",
     lambda df: (df["high"] + df["low"] + df["close"]) / 3.0)
_reg("price.magnitude.ohlc4", "OHLC4", "Magnitude", "level",
     "Mean of O, H, L, C.", "(O+H+L+C)/4", "Whole-bar representative.",
     lambda df: (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0)
_reg("price.magnitude.hlcc4", "HLCC4", "Magnitude", "level",
     "H, L, and Close (weighted twice).", "(H+L+2C)/4",
     "Close-weighted representative.",
     lambda df: (df["high"] + df["low"] + 2 * df["close"]) / 4.0)
_reg("price.magnitude.log_close", "Log Close", "Magnitude", "level",
     "Natural log of close.", "ln(P_t)",
     "Multiplicative-scale representation.",
     lambda df: np.log(_p(df)))
_reg("price.magnitude.midrange", "Midrange", "Magnitude", "level",
     "Midpoint of H and L.", "(H+L)/2", "Center of the bar's range.",
     lambda df: (df["high"] + df["low"]) / 2.0)

# Ranges & candle anatomy
_reg("price.magnitude.range_hl", "Bar Range", "Magnitude", "range",
     "Absolute intra-bar range.", "H - L", "Full bar extent.",
     lambda df: df["high"] - df["low"])
_reg("price.magnitude.body", "Body Size", "Magnitude", "candle",
     "Absolute open-to-close body.", "|C - O|", "Directional body span.",
     lambda df: (df["close"] - df["open"]).abs())
_reg("price.magnitude.signed_body", "Signed Body", "Magnitude", "candle",
     "Signed open-to-close move.", "C - O",
     ">0 bullish body, <0 bearish body.",
     lambda df: df["close"] - df["open"])
_reg("price.magnitude.upper_shadow", "Upper Shadow", "Magnitude", "candle",
     "Length of the upper wick.", "H - max(O,C)",
     "Rejected upward movement.",
     lambda df: df["high"] - df[["open", "close"]].max(axis=1))
_reg("price.magnitude.lower_shadow", "Lower Shadow", "Magnitude", "candle",
     "Length of the lower wick.", "min(O,C) - L",
     "Rejected downward movement.",
     lambda df: df[["open", "close"]].min(axis=1) - df["low"])
_reg("price.magnitude.body_ratio", "Body-to-Range", "Magnitude", "candle_ratio",
     "Body magnitude relative to full range.", "|C-O| / (H-L)",
     "1 = marubozu, 0 = doji.",
     lambda df: (df["close"] - df["open"]).abs() /
                (df["high"] - df["low"]).replace(0, np.nan))
_reg("price.magnitude.upper_wick_ratio", "Upper-Wick Ratio", "Magnitude",
     "candle_ratio", "Upper shadow / range.",
     "(H - max(O,C)) / (H - L)", "Fraction of range spent above the body.",
     lambda df: (df["high"] - df[["open", "close"]].max(axis=1)) /
                (df["high"] - df["low"]).replace(0, np.nan))
_reg("price.magnitude.lower_wick_ratio", "Lower-Wick Ratio", "Magnitude",
     "candle_ratio", "Lower shadow / range.",
     "(min(O,C) - L) / (H - L)", "Fraction of range spent below the body.",
     lambda df: (df[["open", "close"]].min(axis=1) - df["low"]) /
                (df["high"] - df["low"]).replace(0, np.nan))
_reg("price.magnitude.true_range", "True Range", "Magnitude", "range",
     "Range including gaps to prior close.",
     "max(H-L, |H-C_prev|, |L-C_prev|)",
     "Gap-aware bar extent.",
     lambda df: tc.true_range(df))
_reg("price.magnitude.gap_open", "Gap-at-Open", "Magnitude", "gap",
     "Difference between open and prior close.", "O_t - C_{t-1}",
     "Overnight/interbar gap.",
     lambda df: df["open"] - df["close"].shift(1))

# ATR at multiple horizons (different timescale = different feature)
for w in [7, 14, 30]:
    _reg(f"price.magnitude.atr_{w}", f"ATR ({w})", "Magnitude", "range",
         f"Average True Range over {w} bars.",
         f"mean(TR)_{w}", "Typical bar-to-bar movement.",
         (lambda w_: (lambda df: tc.atr(df, w_)))(w), params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# MOTION — "How is it changing?"  (derivatives, returns, EMA slopes)
# ═══════════════════════════════════════════════════════════════════════
# Log returns at multiple horizons
for dt in [1, 2, 3, 5, 10, 20, 50, 100]:
    _reg(f"price.motion.log_return_{dt}", f"Log Return ({dt})", "Motion",
         "returns", f"Logarithmic return over {dt} bars.",
         f"ln(P_t / P_{{t-{dt}}})", "Additive, symmetric return.",
         (lambda dt_: (lambda df: mo.log_return(_p(df), dt_)))(dt),
         params={"dt": dt})

# Simple % return
for dt in [1, 5, 20]:
    _reg(f"price.motion.simple_return_{dt}", f"Simple Return ({dt})", "Motion",
         "returns", f"Percentage return over {dt} bars.",
         f"P_t / P_{{t-{dt}}} - 1", "Multiplicative return.",
         (lambda dt_: (lambda df: mo.simple_return(_p(df), dt_)))(dt),
         params={"dt": dt})

# Higher-order derivatives
_reg("price.motion.velocity_1", "Velocity (1)", "Motion", "derivative_1",
     "First finite difference.", "P_t - P_{t-1}", "One-step change.",
     lambda df: mo.velocity(_p(df), 1))
_reg("price.motion.acceleration", "Acceleration", "Motion", "derivative_2",
     "Second finite difference.", "Δ²P", "Rate-of-change of velocity.",
     lambda df: mo.acceleration(_p(df), 1))
_reg("price.motion.jerk", "Jerk", "Motion", "derivative_3",
     "Third finite difference.", "Δ³P", "Change of acceleration.",
     lambda df: mo.jerk(_p(df), 1))
_reg("price.motion.snap", "Snap", "Motion", "derivative_4",
     "Fourth finite difference.", "Δ⁴P", "Change of jerk.",
     lambda df: mo.snap(_p(df), 1))

# Absolute and squared returns (magnitudes of motion)
for dt in [1, 5, 20]:
    _reg(f"price.motion.abs_return_{dt}", f"|Log Return| ({dt})", "Motion",
         "return_magnitude", f"Absolute log-return magnitude.",
         "|ln(P_t/P_{t-dt})|", "Motion size regardless of sign.",
         (lambda dt_: (lambda df: mo.log_return(_p(df), dt_).abs()))(dt),
         params={"dt": dt})
    _reg(f"price.motion.sq_return_{dt}", f"Log Return² ({dt})", "Motion",
         "realized_var", f"Squared log-return — instantaneous variance proxy.",
         "(ln(P_t/P_{t-dt}))²", "Realized-variance building block.",
         (lambda dt_: (lambda df: mo.log_return(_p(df), dt_) ** 2))(dt),
         params={"dt": dt})

# Sign of return
_reg("price.motion.return_sign", "Return Sign", "Motion", "direction",
     "Sign of 1-bar log return.", "sign(r_t)", "+1 up, -1 down, 0 flat.",
     lambda df: np.sign(mo.log_return(_p(df), 1)))

# Same-sign streak length (positive = up-streak, negative = down-streak)
def _streak(df):
    s = np.sign(mo.log_return(_p(df), 1)).fillna(0).values
    out = np.zeros_like(s)
    for i in range(1, len(s)):
        if s[i] == 0:
            out[i] = 0
        elif s[i] == np.sign(out[i - 1]) or out[i - 1] == 0:
            out[i] = out[i - 1] + s[i]
        else:
            out[i] = s[i]
    return pd.Series(out, index=df.index)

_reg("price.motion.streak_length", "Signed Streak Length", "Motion", "streak",
     "Length of the current same-sign return streak.",
     "count of consecutive same-sign r_t (signed)",
     "+n after n up-bars, -n after n down-bars.",
     _streak)

# EMA levels (smoothed price)  and EMA slopes (smoothed velocity)
for span in [5, 10, 20, 50, 100, 200]:
    _reg(f"price.motion.ema_{span}", f"EMA ({span})", "Motion", "smoothed_level",
         f"Exponential moving average, span={span}.",
         f"EMA_{span}(P)",
         "Recency-weighted level; short spans = faster.",
         (lambda s_: (lambda df: tc.ema(_p(df), s_)))(span),
         params={"span": span})

for span in [10, 20, 50]:
    _reg(f"price.motion.ema_slope_{span}", f"EMA Slope ({span})", "Motion",
         "smoothed_slope",
         f"1-step change of EMA_{span}.", f"ΔEMA_{span}",
         "Smoothed velocity — direction & pace of trend.",
         (lambda s_: (lambda df: tc.ema(_p(df), s_).diff()))(span),
         params={"span": span})

# MACD-flavored differentials (difference of two EMAs)
for fast, slow in [(12, 26), (5, 20), (20, 50)]:
    _reg(f"price.motion.ema_diff_{fast}_{slow}",
         f"EMA Difference ({fast}-{slow})", "Motion", "ema_spread",
         f"EMA({fast}) − EMA({slow}).",
         f"EMA_{fast}(P) − EMA_{slow}(P)",
         "Positive when short-term > long-term (momentum up).",
         (lambda f_, s_: (lambda df: tc.ema(_p(df), f_) - tc.ema(_p(df), s_)))(fast, slow),
         params={"fast": fast, "slow": slow})

# Realized variance (log-return²) rolling sum — RV estimator
for w in [10, 20, 50]:
    _reg(f"price.motion.realized_var_{w}", f"Realized Variance ({w})",
         "Motion", "realized_var",
         f"Sum of squared 1-bar log-returns over {w} bars.",
         "Σ r_t²", "Non-parametric variance estimator.",
         (lambda w_: (lambda df: (mo.log_return(_p(df), 1) ** 2)
                     .rolling(w_, min_periods=w_).sum()))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# GEOMETRY — "What is its shape?"
# ═══════════════════════════════════════════════════════════════════════
for w in W_ALL:
    _reg(f"price.geometry.path_length_{w}", f"Path Length ({w})", "Geometry",
         "trajectory", f"Total absolute path length over {w} bars.",
         f"Σ|ΔP| over w={w}",
         "Larger = more travel = rougher path.",
         (lambda w_: (lambda df: ge.path_length(_p(df), w_)))(w),
         params={"window": w})

for w in W_ALL:
    _reg(f"price.geometry.straightness_{w}", f"Straightness ({w})",
         "Geometry", "trajectory",
         f"|displacement| / path length over {w} bars.",
         "|P_t - P_{t-w}| / Σ|ΔP|",
         "1 = straight line, 0 = zig-zag.",
         (lambda w_: (lambda df: ge.straightness(_p(df), w_)))(w),
         params={"window": w})

for w in W_MED_LONG:
    _reg(f"price.geometry.complexity_{w}", f"Turning Points ({w})", "Geometry",
         "trajectory",
         f"Number of local turning points in {w} bars.",
         "#{i: sign(ΔP_i) ≠ sign(ΔP_{i-1})}",
         "Higher = choppier trajectory.",
         (lambda w_: (lambda df: ge.trajectory_complexity(_p(df), w_)))(w),
         params={"window": w})

_reg("price.geometry.curvature", "Curvature", "Geometry", "local_shape",
     "Discrete second-difference curvature.", "P_{t-1} - 2P_t + P_{t+1}",
     "Sharp bend detector.",
     lambda df: ge.curvature(_p(df)))
_reg("price.geometry.angular_change", "Angular Change", "Geometry",
     "local_shape",
     "Difference of consecutive slope angles.", "atan(ΔP_t) - atan(ΔP_{t-1})",
     "Instantaneous angle of the trajectory.",
     lambda df: ge.angular_change(_p(df)))

# Fractal geometry
for w in [25, 50, 100]:
    _reg(f"price.geometry.higuchi_fd_{w}", f"Higuchi FD ({w})", "Geometry",
         "fractal",
         f"Higuchi fractal dimension over {w} bars.",
         "slope of log(L(k)) vs log(1/k)",
         "1 = smooth line, 2 = space-filling roughness.",
         (lambda w_: (lambda df: fr.higuchi_fd(_p(df), w_)))(w),
         params={"window": w, "kmax": 8}, complexity="O(nlogn)")

for w in [16, 32, 64, 128]:
    _reg(f"price.geometry.hurst_{w}", f"Hurst Exponent ({w})", "Geometry",
         "fractal",
         f"R/S Hurst exponent estimate over {w} bars.",
         "log(R/S) / log(w)",
         ">0.5 persistent, <0.5 mean-reverting, ≈0.5 random walk.",
         (lambda w_: (lambda df: fr.hurst_rs(_p(df), w_)))(w),
         params={"window": w}, complexity="O(n)")

_reg(f"price.geometry.hurst_divergence_16_64", f"Hurst Divergence (16/64)", "Geometry",
     "fractal",
     f"Absolute difference between 16-bar and 64-bar Hurst exponent.",
     "|H(16) - H(64)|",
     "Large divergence indicates rapid regime shift.",
     lambda df: np.abs(fr.hurst_rs(_p(df), 16) - fr.hurst_rs(_p(df), 64)),
     params={"window_short": 16, "window_long": 64}, complexity="O(n)")

for w in [128]:
    _reg(f"price.geometry.dfa_alpha_{w}", f"DFA α ({w})", "Geometry",
         "fractal",
         f"Detrended Fluctuation Analysis exponent over {w} bars.",
         "slope of log F(s) vs log s",
         "Scaling exponent of long-range correlations.",
         (lambda w_: (lambda df: fr.dfa_alpha(_p(df), w_)))(w),
         params={"window": w}, complexity="O(nlogn)")

for w in [32, 64, 128]:
    _reg(f"price.geometry.boxcount_fd_{w}", f"Box-Counting FD ({w})", "Geometry",
         "fractal",
         f"Capacity dimension via Box-Counting over {w} bars.",
         "slope of log N vs log(1/eps)",
         "High values indicate efficient random walk, low indicates persistent trend.",
         (lambda w_: (lambda df: fr.boxcount_fd(_p(df), w_)))(w),
         params={"window": w}, complexity="O(w)")

# Kaufman Efficiency Ratio is mathematically identical to Geometry.straightness_w
# by definition (|P_t - P_{t-w}| / Σ|ΔP|). Not re-registered per Rule 1.


# ═══════════════════════════════════════════════════════════════════════
# RELATIVE — "Compared to what?"
# ═══════════════════════════════════════════════════════════════════════
for w in W_ALL:
    _reg(f"price.relative.dist_sma_{w}", f"% from SMA{w}", "Relative",
         "moving_average", f"Relative distance from SMA({w}).",
         "(P - SMA_w) / SMA_w", "% deviation from the moving average.",
         (lambda w_: (lambda df: ds.distance_from_ma(_p(df), w_)))(w),
         params={"window": w})

for span in [10, 20, 50, 100, 200]:
    _reg(f"price.relative.dist_ema_{span}", f"% from EMA{span}", "Relative",
         "ema_distance",
         f"Relative distance from EMA(span={span}).",
         "(P - EMA_span) / EMA_span", "% deviation from EMA.",
         (lambda s_: (lambda df: (_p(df) - tc.ema(_p(df), s_)) /
                                 tc.ema(_p(df), s_).replace(0, np.nan)))(span),
         params={"span": span})

for w in [20, 50, 200]:
    _reg(f"price.relative.dist_high_{w}", f"% from High {w}", "Relative",
         "extremes",
         f"Relative distance from rolling {w}-bar high.",
         "(P - max_w) / max_w", "0 at fresh high; negative below.",
         (lambda w_: (lambda df: ds.distance_from_high(_p(df), w_)))(w),
         params={"window": w})
    _reg(f"price.relative.dist_low_{w}", f"% from Low {w}", "Relative",
         "extremes",
         f"Relative distance from rolling {w}-bar low.",
         "(P - min_w) / min_w", "0 at fresh low; positive above.",
         (lambda w_: (lambda df: ds.distance_from_low(_p(df), w_)))(w),
         params={"window": w})

for w in [20, 50]:
    _reg(f"price.relative.dist_median_{w}", f"% from Median {w}", "Relative",
         "robust_center",
         f"Relative distance from rolling {w}-bar median.",
         "(P - med_w) / med_w", "Outlier-robust deviation from center.",
         (lambda w_: (lambda df: (_p(df) - st.rolling_median(_p(df), w_)) /
                                 st.rolling_median(_p(df), w_).replace(0, np.nan)))(w),
         params={"window": w})

# Distance from N-bar-ago values
for n in [1, 5, 20]:
    _reg(f"price.relative.dist_prev_{n}", f"% Change from {n} bars ago",
         "Relative", "lagged",
         f"Relative change vs price {n} bars ago.",
         "(P_t - P_{t-n}) / P_{t-n}",
         "Backward-looking change.",
         (lambda n_: (lambda df: (_p(df) - _p(df).shift(n_)) /
                                 _p(df).shift(n_).replace(0, np.nan)))(n),
         params={"n": n})

# Distance from midrange
_reg("price.relative.dist_midrange", "% from Bar Midrange", "Relative",
     "intra_bar",
     "Close relative to bar's own midrange.",
     "(C - (H+L)/2) / ((H+L)/2)",
     "+ above bar center, - below.",
     lambda df: (df["close"] - (df["high"] + df["low"]) / 2) /
                ((df["high"] + df["low"]) / 2).replace(0, np.nan))


# ═══════════════════════════════════════════════════════════════════════
# POSITION — "Where does the current value lie?"
# ═══════════════════════════════════════════════════════════════════════
for w in W_ALL:
    _reg(f"price.position.minmax_{w}", f"Min-Max Position ({w})", "Position",
         "range_position",
         f"Where price sits in the {w}-bar min-max range.",
         "(P - min)/(max - min)", "0 = at low, 1 = at high.",
         (lambda w_: (lambda df: no.min_max(_p(df), w_)))(w),
         params={"window": w})

for w in [20, 50, 100, 200]:
    _reg(f"price.position.pct_rank_{w}", f"Percentile Rank ({w})", "Position",
         "distribution_position",
         f"Empirical CDF value of current price in {w}-bar window.",
         "F̂_w(P_t)", "Percentile rank ∈ [0,1].",
         (lambda w_: (lambda df: di.rolling_percentile_rank(_p(df), w_)))(w),
         params={"window": w})

# Bollinger %B
for w in [20, 50]:
    for k in [2.0, 3.0]:
        _reg(f"price.position.bb_percent_b_{w}_k{int(k)}",
             f"Bollinger %B ({w}, k={k})", "Position", "bollinger",
             f"Bollinger %B on window {w} with k={k}.",
             "(P - lower) / (upper - lower)",
             "0 = at lower band, 1 = at upper.",
             (lambda w_, k_: (lambda df: tc.bollinger_percent_b(_p(df), w_, k_)))(w, k),
             params={"window": w, "k": k})

# Donchian position
for w in [20, 50, 100]:
    _reg(f"price.position.donchian_{w}", f"Donchian Position ({w})",
         "Position", "donchian",
         f"Position of price within {w}-bar Donchian channel.",
         "(P - min_w) / (max_w - min_w)",
         "0 = at Donchian low, 1 = at Donchian high.",
         (lambda w_: (lambda df: tc.donchian_percent(_p(df), w_)))(w),
         params={"window": w})

# Keltner position
for w in [20, 50]:
    _reg(f"price.position.keltner_{w}", f"Keltner Position ({w})",
         "Position", "keltner",
         f"Position within Keltner channel (EMA±1.5·ATR).",
         "(P - lower) / (upper - lower)",
         "0 = at Keltner lower band, 1 = at upper.",
         (lambda w_: (lambda df: tc.keltner_percent(df, w_, 1.5)))(w),
         params={"window": w, "k": 1.5})


# ═══════════════════════════════════════════════════════════════════════
# STATISTICS — "What statistical properties exist?"
# ═══════════════════════════════════════════════════════════════════════
for w in W_ALL:
    _reg(f"price.statistics.mean_{w}", f"Rolling Mean ({w})", "Statistics",
         "moments", f"Arithmetic mean over {w}.",
         f"(1/{w}) Σ P", "Central tendency.",
         (lambda w_: (lambda df: st.rolling_mean(_p(df), w_)))(w),
         params={"window": w})
    _reg(f"price.statistics.std_{w}", f"Rolling Std ({w})", "Statistics",
         "moments", f"Sample std over {w}.", "√Var_w", "Dispersion.",
         (lambda w_: (lambda df: st.rolling_std(_p(df), w_)))(w),
         params={"window": w})
    _reg(f"price.statistics.var_{w}", f"Rolling Variance ({w})", "Statistics",
         "moments", f"Sample variance over {w}.",
         "(1/(w-1)) Σ (P-μ)²", "Squared dispersion.",
         (lambda w_: (lambda df: st.rolling_var(_p(df), w_)))(w),
         params={"window": w})

for w in W_MED_LONG:
    _reg(f"price.statistics.skew_{w}", f"Rolling Skew ({w})", "Statistics",
         "moments", f"Third standardized moment over {w}.",
         "E[((P-μ)/σ)³]", "Distributional asymmetry.",
         (lambda w_: (lambda df: st.rolling_skew(_p(df), w_)))(w),
         params={"window": w})
    _reg(f"price.statistics.kurt_{w}", f"Rolling Excess Kurtosis ({w})",
         "Statistics", "moments",
         f"Excess kurtosis over {w}.", "E[((P-μ)/σ)⁴] - 3", "Tail heaviness.",
         (lambda w_: (lambda df: st.rolling_kurt(_p(df), w_)))(w),
         params={"window": w})

# Robust statistics
for w in W_MED:
    _reg(f"price.statistics.mad_{w}", f"MAD ({w})", "Statistics",
         "robust_dispersion", f"Median absolute deviation over {w}.",
         "median(|P - median(P)|)", "Robust dispersion (outlier-safe).",
         (lambda w_: (lambda df: st.rolling_mad(_p(df), w_)))(w),
         params={"window": w})
    _reg(f"price.statistics.iqr_{w}", f"IQR ({w})", "Statistics",
         "robust_dispersion", f"Interquartile range over {w}.",
         "Q3 - Q1", "Middle-50% spread.",
         (lambda w_: (lambda df: st.rolling_iqr(_p(df), w_)))(w),
         params={"window": w})

# Coefficient of variation
for w in W_MED:
    _reg(f"price.statistics.cv_{w}", f"Coeff of Variation ({w})",
         "Statistics", "relative_dispersion",
         f"σ / |μ| over {w}.", "σ_w / |μ_w|",
         "Scale-free dispersion.",
         (lambda w_: (lambda df: st.rolling_std(_p(df), w_) /
                                 st.rolling_mean(_p(df), w_).abs()
                                 .replace(0, np.nan)))(w),
         params={"window": w})

# Autocorrelation at multiple lags
for w in [30, 60]:
    for lag in [1, 2, 5, 10]:
        _reg(f"price.statistics.autocorr_w{w}_lag{lag}",
             f"AR({lag}) Autocorr ({w})", "Statistics", "temporal",
             f"Lag-{lag} autocorrelation over {w} bars.",
             f"ρ(P_t, P_{{t-{lag}}})",
             "Serial dependence — persistence structure.",
             (lambda w_, l_: (lambda df: st.rolling_autocorr(_p(df), w_, l_)))(w, lag),
             params={"window": w, "lag": lag})

# Z-scores
for w in W_ALL:
    _reg(f"price.statistics.zscore_{w}", f"Z-Score ({w})", "Statistics",
         "standardized", f"Standardized price over {w}.",
         "(P - μ_w) / σ_w", "σ-units from local mean.",
         (lambda w_: (lambda df: no.zscore(_p(df), w_)))(w),
         params={"window": w})

for w in W_MED:
    _reg(f"price.statistics.robust_z_{w}", f"Robust Z ({w})", "Statistics",
         "standardized", f"MAD-based robust z-score over {w}.",
         "0.6745·(P - med)/MAD",
         "Outlier-safe standardized deviation.",
         (lambda w_: (lambda df: no.robust_zscore(_p(df), w_)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# DISTRIBUTION — "How are values distributed?"
# ═══════════════════════════════════════════════════════════════════════
QUANTILES = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
for w in [50, 100]:
    for q in QUANTILES:
        _reg(f"price.distribution.q{int(q*100)}_w{w}",
             f"Quantile {int(q*100)}% ({w})",
             "Distribution", "quantiles",
             f"{int(q*100)}th percentile over {w}.",
             f"Q_{{{q}}}(P)_{w}", f"The {int(q*100)}th percentile level.",
             (lambda w_, q_: (lambda df: di.rolling_quantile(_p(df), w_, q_)))(w, q),
             params={"window": w, "q": q})

# IQR ratio (Q3-Q1) / (Q95-Q5)
for w in [50, 100]:
    _reg(f"price.distribution.iqr_ratio_{w}", f"IQR/D9-D1 Ratio ({w})",
         "Distribution", "concentration",
         "IQR divided by 90-10% decile range.",
         "(Q75-Q25) / (Q95-Q5)",
         "Higher = tighter core relative to tails.",
         (lambda w_: (lambda df: (di.rolling_quantile(_p(df), w_, .75) -
                                   di.rolling_quantile(_p(df), w_, .25)) /
                                  (di.rolling_quantile(_p(df), w_, .95) -
                                   di.rolling_quantile(_p(df), w_, .05))
                                  .replace(0, np.nan)))(w),
         params={"window": w})

# Value-at-Risk on returns
for alpha in [0.01, 0.05]:
    _reg(f"price.distribution.var_returns_a{int(alpha*100)}",
         f"VaR (returns, α={alpha})", "Distribution", "risk",
         f"{int(alpha*100)}% Value-at-Risk of 1-bar log returns over 100 bars.",
         f"Q_{{{alpha}}}(r)_{100}",
         "Left-tail loss threshold at α confidence.",
         (lambda a_: (lambda df: di.rolling_quantile(mo.log_return(_p(df), 1), 100, a_)))(alpha),
         params={"window": 100, "alpha": alpha})

# Expected Shortfall
for alpha in [0.05]:
    def _es(alpha_):
        def f(df):
            r = mo.log_return(_p(df), 1)
            q = di.rolling_quantile(r, 100, alpha_)
            return r.rolling(100, min_periods=100).apply(
                lambda a: np.mean(a[a <= np.quantile(a, alpha_)])
                if np.sum(a <= np.quantile(a, alpha_)) > 0 else np.nan, raw=True)
        return f
    _reg(f"price.distribution.es_returns_a{int(alpha*100)}",
         f"ES (returns, α={alpha})", "Distribution", "risk",
         f"Expected Shortfall of returns at α={alpha}.",
         "E[r | r ≤ Q_α(r)]",
         "Average loss beyond VaR.",
         _es(alpha), params={"window": 100, "alpha": alpha},
         complexity="O(nlogn)")


# ═══════════════════════════════════════════════════════════════════════
# ENTROPY — "How uncertain?"
# ═══════════════════════════════════════════════════════════════════════
for w in [30, 60, 120]:
    _reg(f"price.entropy.shannon_{w}", f"Shannon Entropy ({w})", "Entropy",
         "information", f"Shannon entropy of price histogram over {w}.",
         "-Σ p log p", "Distributional uncertainty.",
         (lambda w_: (lambda df: st.rolling_entropy(_p(df), w_)))(w),
         params={"window": w, "bins": 10})

for order in [3, 4]:
    for w in [30, 60]:
        _reg(f"price.entropy.perm_o{order}_w{w}",
             f"Permutation Entropy (order={order}, w={w})", "Entropy",
             "ordinal", f"Permutation entropy of order {order} over {w}.",
             "H(π) / log(m!)",
             "Ordinal-pattern complexity ∈ [0,1].",
             (lambda o_, w_: (lambda df: info.permutation_entropy(_p(df), w_, o_)))(order, w),
             params={"order": order, "window": w},
             complexity="O(nlogn)")

for w in [60, 100]:
    _reg(f"price.entropy.sample_{w}", f"Sample Entropy ({w})", "Entropy",
         "regularity", f"Sample entropy (m=2, r=0.2σ) over {w}.",
         "-log(A/B)",
         "Regularity/predictability — lower = more predictable.",
         (lambda w_: (lambda df: info.sample_entropy(_p(df), w_)))(w),
         params={"m": 2, "r": 0.2, "window": w},
         complexity="O(n^2)")
    _reg(f"price.entropy.approx_{w}", f"Approx Entropy ({w})", "Entropy",
         "regularity", f"Approximate entropy (m=2, r=0.2σ) over {w}.",
         "φ(m) - φ(m+1)",
         "Regularity measure; robust to short windows.",
         (lambda w_: (lambda df: info.approximate_entropy(_p(df), w_)))(w),
         params={"m": 2, "r": 0.2, "window": w},
         complexity="O(n^2)")

for alpha in [0.5, 2.0]:
    _reg(f"price.entropy.renyi_a{alpha}", f"Rényi Entropy (α={alpha})",
         "Entropy", "generalized",
         f"Rényi entropy of order {alpha} on price histogram (w=60).",
         "log(Σp^α) / (1-α)",
         "α<1 emphasizes rare events; α>1 emphasizes modes.",
         (lambda a_: (lambda df: info.renyi_entropy(_p(df), 60, a_)))(alpha),
         params={"alpha": alpha, "window": 60, "bins": 10})

_reg("price.entropy.tsallis_q2", "Tsallis Entropy (q=2)", "Entropy",
     "generalized", "Non-additive Tsallis entropy over 60 bars, q=2.",
     "(1 - Σp²)/(q-1)",
     "Complexity measure sensitive to distribution concentration.",
     lambda df: info.tsallis_entropy(_p(df), 60, 2.0))

for w in [60, 120]:
    _reg(f"price.entropy.spectral_{w}", f"Spectral Entropy ({w})", "Entropy",
         "spectral", f"Shannon entropy of normalized PSD over {w} bars.",
         "H(PSD) / log|PSD|",
         "0 = single-frequency oscillator; 1 = white noise.",
         (lambda w_: (lambda df: sp.spectral_entropy(_p(df), w_)))(w),
         params={"window": w},
         complexity="O(nlogn)")

_reg("price.entropy.lz_60", "LZ Complexity (60)", "Entropy",
     "algorithmic",
     "Lempel-Ziv complexity of median-binarized series over 60 bars.",
     "C · log₂(n)/n",
     "Compressibility of the binarized path.",
     lambda df: info.lz_complexity(_p(df), 60), complexity="O(n)")

_reg("price.entropy.zero_crossings_60", "Zero-Crossings (Δ, 60)", "Entropy",
     "combinatorial",
     "Zero-crossings of the first difference within 60 bars.",
     "#{i: sign(ΔP_i)≠sign(ΔP_{i-1})}",
     "Oscillation frequency in count form.",
     lambda df: info.zero_crossings(_p(df), 60))


# ═══════════════════════════════════════════════════════════════════════
# EXPANSION — "Is it expanding?"
# ═══════════════════════════════════════════════════════════════════════
for w in [10, 20, 50]:
    def _rer(w_):
        def f(df):
            r = st.rolling_range(_p(df), w_)
            return r / r.rolling(w_, min_periods=w_).mean().replace(0, np.nan)
        return f
    _reg(f"price.expansion.range_ratio_{w}", f"Range Expansion ({w})",
         "Expansion", "range_dynamics",
         f"{w}-bar range / trailing mean of range.",
         "R_w / mean(R_w)",
         ">1 expanding, <1 contracting.",
         _rer(w), params={"window": w})

# Bollinger bandwidth (relative width)
for w in [20, 50]:
    for k in [2.0]:
        _reg(f"price.expansion.bb_width_{w}_k{int(k)}",
             f"Bollinger Bandwidth ({w}, k={k})", "Expansion", "bollinger",
             f"Bollinger band width relative to mid over {w} (k={k}).",
             "(upper - lower) / mid",
             "Volatility-scaled band width; low = squeeze.",
             (lambda w_, k_: (lambda df: tc.bollinger_bandwidth(_p(df), w_, k_)))(w, k),
             params={"window": w, "k": k})

# Keltner width
for w in [20, 50]:
    _reg(f"price.expansion.keltner_width_{w}",
         f"Keltner Width ({w})", "Expansion", "keltner",
         f"Keltner channel width / mid at {w} (k=1.5).",
         "(upper - lower)/mid", "ATR-scaled band width.",
         (lambda w_: (lambda df: tc.keltner_width(df, w_, 1.5)))(w),
         params={"window": w, "k": 1.5})

# Squeeze indicator (Bollinger width < Keltner width → squeeze)
for w in [20]:
    def _sq(w_):
        def f(df):
            bb = tc.bollinger_bandwidth(_p(df), w_, 2.0)
            kw = tc.keltner_width(df, w_, 1.5)
            return (bb < kw).astype(float)
        return f
    _reg(f"price.expansion.squeeze_{w}", f"Squeeze Flag ({w})",
         "Expansion", "compression",
         f"Bollinger bandwidth < Keltner width at {w}.",
         "1[BB_width < Keltner_width]",
         "1 during volatility squeeze, 0 otherwise.",
         _sq(w), params={"window": w})

# ATR expansion (short/long)
_reg("price.expansion.atr_ratio_14_50", "ATR Ratio 14/50",
     "Expansion", "atr_dynamics",
     "Short ATR divided by longer ATR.",
     "ATR_14 / ATR_50",
     ">1 short-term volatility above baseline.",
     lambda df: tc.atr(df, 14) / tc.atr(df, 50).replace(0, np.nan))

# Std-of-std (vol of vol)
for w in [20]:
    def _vovol(w_):
        def f(df):
            v = st.rolling_std(_p(df), w_)
            return st.rolling_std(v, w_)
        return f
    _reg(f"price.expansion.vol_of_vol_{w}", f"Vol-of-Vol ({w})",
         "Expansion", "vol_dynamics",
         f"Std of the rolling std at window {w}.",
         "σ(σ_w)_w",
         "Instability of the volatility itself.",
         _vovol(w), params={"window": w})

# Ulcer index (drawdown-based expansion of downside)
for w in [14, 30]:
    _reg(f"price.expansion.ulcer_{w}", f"Ulcer Index ({w})",
         "Expansion", "drawdown",
         f"Root-mean-square drawdown over {w} bars.",
         "√mean((P/max_running - 1)²)",
         "Downside dispersion emphasizing depth × duration.",
         (lambda w_: (lambda df: tc.ulcer_index(_p(df), w_)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# CLUSTERING — "Does it cluster?"
# ═══════════════════════════════════════════════════════════════════════
for w in [10, 20]:
    def _vc(w_):
        def f(df):
            r = mo.log_return(_p(df), 1)
            s = (r ** 2).rolling(w_, min_periods=w_).mean()
            l = (r ** 2).rolling(w_ * 3, min_periods=w_ * 3).mean()
            return s / l.replace(0, np.nan)
        return f
    _reg(f"price.clustering.vol_ratio_{w}", f"Vol Cluster ({w})", "Clustering",
         "volatility_clustering",
         f"Short (w={w}) vs long (3w) mean-squared-return ratio.",
         "mean(r²)_w / mean(r²)_{3w}",
         ">1 active volatility cluster.",
         _vc(w), params={"window": w})

# Squared-return autocorrelation (ARCH signature) at multiple lags
for lag in [1, 2, 5]:
    def _sqacf(lag_):
        def f(df):
            r2 = mo.log_return(_p(df), 1) ** 2
            return st.rolling_autocorr(r2, 60, lag_)
        return f
    _reg(f"price.clustering.sq_acf_lag{lag}",
         f"Squared-Return ACF (lag {lag})", "Clustering", "arch",
         f"Lag-{lag} autocorrelation of squared returns over 60 bars.",
         f"ρ(r_t², r_{{t-{lag}}}²)",
         "Positive = ARCH effect present.",
         _sqacf(lag), params={"lag": lag, "window": 60})

# Absolute-return autocorrelation (also captures long memory)
for lag in [1, 5]:
    def _absacf(lag_):
        def f(df):
            a = mo.log_return(_p(df), 1).abs()
            return st.rolling_autocorr(a, 60, lag_)
        return f
    _reg(f"price.clustering.abs_acf_lag{lag}",
         f"|Return| ACF (lag {lag})", "Clustering", "long_memory",
         f"Lag-{lag} autocorrelation of |returns| over 60 bars.",
         f"ρ(|r_t|, |r_{{t-{lag}}}|)",
         "Volatility long-memory signature.",
         _absacf(lag), params={"lag": lag, "window": 60})


# ═══════════════════════════════════════════════════════════════════════
# REGIME — regime structure of the price itself
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50, 100, 200]:
    _reg(f"price.regime.above_sma_{w}", f"Above SMA{w}", "Regime",
         "level_regime",
         f"Sign of (P − SMA_{w}).", "sign(P - SMA_w)",
         "+1 above, -1 below, trend-position regime.",
         (lambda w_: (lambda df: np.sign(_p(df) - st.rolling_mean(_p(df), w_))))(w),
         params={"window": w})

for span in [20, 50, 200]:
    _reg(f"price.regime.above_ema_{span}", f"Above EMA{span}", "Regime",
         "ema_regime",
         f"Sign of (P − EMA_{span}).", "sign(P - EMA_span)",
         "Persistent above/below EMA state.",
         (lambda s_: (lambda df: np.sign(_p(df) - tc.ema(_p(df), s_))))(span),
         params={"span": span})

# MA-slope regime — trend regime independent of level
for w in [20, 50]:
    _reg(f"price.regime.sma_slope_sign_{w}", f"SMA{w} Slope Sign", "Regime",
         "slope_regime",
         f"Sign of the change in SMA_{w}.",
         "sign(ΔSMA_w)",
         "+1 rising MA, -1 falling MA — trend direction.",
         (lambda w_: (lambda df: np.sign(st.rolling_mean(_p(df), w_).diff())))(w),
         params={"window": w})

# Golden-cross / death-cross flag (two-MA agreement)
_reg("price.regime.ma50_above_ma200", "MA50 above MA200", "Regime",
     "cross_regime",
     "1 if SMA50 above SMA200 else 0.",
     "1[SMA_50 > SMA_200]",
     "Long-term uptrend regime indicator.",
     lambda df: (st.rolling_mean(_p(df), 50) >
                 st.rolling_mean(_p(df), 200)).astype(float))

# Chande momentum oscillator regime
for w in [14, 30]:
    _reg(f"price.regime.chande_momentum_{w}",
         f"Chande Momentum ({w})", "Regime", "signed_momentum",
         f"(Σ up - Σ down) / (Σ up + Σ down) over {w}.",
         "(U-D)/(U+D)",
         "Signed momentum ∈ [-1,1].",
         (lambda w_: (lambda df: tc.chande_momentum(_p(df), w_)))(w),
         params={"window": w})

# Choppiness index (regime discriminator: trending vs choppy)
for w in [14, 30]:
    _reg(f"price.regime.choppiness_{w}", f"Choppiness Index ({w})",
         "Regime", "trend_vs_range",
         f"log10(Σ TR / range) / log10({w}).",
         "log₁₀(ΣTR/range)/log₁₀(w)",
         "High = choppy/range-bound; Low = trending.",
         (lambda w_: (lambda df: tc.choppiness_index(df, w_)))(w),
         params={"window": w})

# Spectral regime — dominant frequency
for w in [64]:
    _reg(f"price.regime.dominant_freq_{w}", f"Dominant Frequency ({w})",
         "Regime", "spectral_regime",
         f"Normalized dominant frequency of PSD over {w} bars.",
         "argmax(PSD)/N",
         "Which cycle length currently dominates.",
         (lambda w_: (lambda df: sp.dominant_frequency(_p(df), w_)))(w),
         params={"window": w},
         complexity="O(nlogn)")

    _reg(f"price.regime.spectral_centroid_{w}", f"Spectral Centroid ({w})",
         "Regime", "spectral_regime",
         f"Center of mass of PSD over {w} bars.",
         "Σ f·PSD / Σ PSD",
         "Higher = more high-frequency energy.",
         (lambda w_: (lambda df: sp.spectral_centroid(_p(df), w_)))(w),
         params={"window": w},
         complexity="O(nlogn)")

    _reg(f"price.regime.spectral_flatness_{w}",
         f"Spectral Flatness ({w})", "Regime", "spectral_regime",
         f"Geometric/arithmetic PSD ratio over {w}.",
         "geomean(PSD)/mean(PSD)",
         "1 = white noise; 0 = pure tone.",
         (lambda w_: (lambda df: sp.spectral_flatness(_p(df), w_)))(w),
         params={"window": w},
         complexity="O(nlogn)")

    _reg(f"price.regime.spectral_rolloff_{w}",
         f"Spectral Rolloff 85% ({w})", "Regime", "spectral_regime",
         f"Frequency below which 85% of spectral energy sits.",
         "min f: Σ_{≤f} PSD ≥ 0.85·total",
         "Bandwidth of the dominant activity.",
         (lambda w_: (lambda df: sp.spectral_rolloff(_p(df), w_, 0.85)))(w),
         params={"window": w, "pct": 0.85},
         complexity="O(nlogn)")

    _reg(f"price.regime.low_band_power_{w}",
         f"Low-Band Power Fraction ({w})", "Regime", "spectral_regime",
         f"Fraction of energy in low frequencies of PSD ({w}).",
         "Σ_{f≤0.25} PSD / Σ PSD",
         "High = slow-moving regime; Low = high-frequency chop.",
         (lambda w_: (lambda df: sp.band_power_ratio(_p(df), w_, 0.25)))(w),
         params={"window": w, "low_end": 0.25},
         complexity="O(nlogn)")


# ═══════════════════════════════════════════════════════════════════════
# HILBERT / DSP additions
# ═══════════════════════════════════════════════════════════════════════
# Magnitude — instantaneous amplitude from analytic signal
for w in [32, 64]:
    _reg(f"price.magnitude.hilbert_envelope_{w}",
         f"Hilbert Envelope ({w})", "Magnitude", "hilbert",
         f"Instantaneous amplitude of Hilbert analytic signal over {w} bars.",
         "|x_a(t)| where x_a = x + iH(x)",
         "Envelope of the price oscillation.",
         (lambda w_: (lambda df: dsp.envelope(_p(df), w_)))(w),
         params={"window": w}, complexity="O(nlogn)")

    _reg(f"price.expansion.envelope_ratio_{w}",
         f"Envelope Ratio ({w})", "Expansion", "hilbert",
         f"Current amplitude / mean amplitude over {w} bars.",
         "|x_a(t)| / mean(|x_a|)_w",
         ">1 amplitude expanding; <1 damping.",
         (lambda w_: (lambda df: dsp.envelope_ratio(_p(df), w_)))(w),
         params={"window": w}, complexity="O(nlogn)")

# Geometry — instantaneous phase & frequency (shape properties in time-freq)
for w in [32, 64]:
    _reg(f"price.geometry.inst_phase_{w}",
         f"Instantaneous Phase ({w})", "Geometry", "hilbert",
         f"Phase (radians) of the analytic signal at time t, window {w}.",
         "arg(x_a(t))",
         "Where in the local oscillation cycle the price sits.",
         (lambda w_: (lambda df: dsp.instantaneous_phase(_p(df), w_)))(w),
         params={"window": w}, complexity="O(nlogn)")

for w in [32, 64]:
    _reg(f"price.geometry.inst_freq_{w}",
         f"Instantaneous Frequency ({w})", "Geometry", "hilbert",
         f"Local dφ/dt averaged over last 3 bars, window {w}.",
         "d·arg(x_a)/dt",
         "Local oscillation rate; high = fast local cycles.",
         (lambda w_: (lambda df: dsp.instantaneous_frequency(_p(df), w_)))(w),
         params={"window": w}, complexity="O(nlogn)")

# Position — Fisher transform (Gaussianized min-max position)
for w in [10, 20]:
    _reg(f"price.position.fisher_{w}",
         f"Fisher Transform ({w})", "Position", "fisher",
         f"Fisher transform of the {w}-bar min-max position.",
         "½ln((1+r)/(1-r)), r=2·MMP-1",
         "Extreme values indicate turning-point pressure.",
         (lambda w_: (lambda df: dsp.fisher_transform(_p(df), w_)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# L-MOMENTS (robust distributional moments)
# ═══════════════════════════════════════════════════════════════════════
for w in [30, 60]:
    _reg(f"price.statistics.lmean_{w}",
         f"L-Mean ({w})", "Statistics", "lmoments",
         f"First L-moment (location) over {w}.", "λ_1",
         "Robust central location.",
         (lambda w_: (lambda df: lm.lmoment(_p(df), w_, 1)))(w),
         params={"window": w, "order": 1}, complexity="O(n^2)")
    _reg(f"price.statistics.lscale_{w}",
         f"L-Scale ({w})", "Statistics", "lmoments",
         f"Second L-moment (scale) over {w}.", "λ_2",
         "Robust dispersion; robust ~ Gini/2.",
         (lambda w_: (lambda df: lm.lmoment(_p(df), w_, 2)))(w),
         params={"window": w, "order": 2}, complexity="O(n^2)")
    _reg(f"price.statistics.lskew_{w}",
         f"L-Skewness ({w})", "Statistics", "lmoments",
         f"L-skewness (τ3) over {w}.", "λ_3/λ_2",
         "Robust asymmetry ∈ [-1,1].",
         (lambda w_: (lambda df: lm.lmoment(_p(df), w_, 3)))(w),
         params={"window": w, "order": 3}, complexity="O(n^2)")
    _reg(f"price.statistics.lkurt_{w}",
         f"L-Kurtosis ({w})", "Statistics", "lmoments",
         f"L-kurtosis (τ4) over {w}.", "λ_4/λ_2",
         "Robust tail-weight measure.",
         (lambda w_: (lambda df: lm.lmoment(_p(df), w_, 4)))(w),
         params={"window": w, "order": 4}, complexity="O(n^2)")


# ═══════════════════════════════════════════════════════════════════════
# TREND / DIRECTIONAL FEATURES for the Decision Engine
# ═══════════════════════════════════════════════════════════════════════
# Aroon Up/Down and Oscillator
def _aroon_up(w_):
    def f(df):
        return _p(df).rolling(w_ + 1, min_periods=w_ + 1).apply(
            lambda a: 100.0 * (w_ - (w_ - int(np.argmax(a)))) / w_, raw=True)
    return f

def _aroon_dn(w_):
    def f(df):
        return _p(df).rolling(w_ + 1, min_periods=w_ + 1).apply(
            lambda a: 100.0 * (w_ - (w_ - int(np.argmin(a)))) / w_, raw=True)
    return f

for w in [14, 25]:
    _reg(f"price.regime.aroon_up_{w}", f"Aroon Up ({w})", "Regime", "aroon",
         f"100·(w - bars_since_high)/w over {w}.",
         "100·(w - argmax_offset)/w",
         "Closer to 100 = fresh high recently.",
         _aroon_up(w), params={"window": w})
    _reg(f"price.regime.aroon_dn_{w}", f"Aroon Down ({w})", "Regime", "aroon",
         f"100·(w - bars_since_low)/w over {w}.",
         "100·(w - argmin_offset)/w",
         "Closer to 100 = fresh low recently.",
         _aroon_dn(w), params={"window": w})
    def _aroonosc(w_):
        def f(df):
            return _aroon_up(w_)(df) - _aroon_dn(w_)(df)
        return f
    _reg(f"price.regime.aroon_osc_{w}", f"Aroon Oscillator ({w})",
         "Regime", "aroon",
         f"Aroon Up − Aroon Down.", "AU - AD",
         "+ = uptrend structure, - = downtrend structure.",
         _aroonosc(w), params={"window": w})

# Vortex Indicator (VI+ and VI-)
def _vortex(w_, sign="up"):
    def f(df):
        h, l, c = df["high"], df["low"], df["close"]
        pc = c.shift(1)
        tr = tc.true_range(df)
        vm_p = (h - l.shift(1)).abs()
        vm_n = (l - h.shift(1)).abs()
        trn = tr.rolling(w_, min_periods=w_).sum().replace(0, np.nan)
        if sign == "up":
            return vm_p.rolling(w_, min_periods=w_).sum() / trn
        else:
            return vm_n.rolling(w_, min_periods=w_).sum() / trn
    return f

for w in [14, 30]:
    _reg(f"price.regime.vortex_up_{w}", f"Vortex Up ({w})", "Regime", "vortex",
         f"Σ|H_t − L_{{t-1}}| / Σ TR over {w}.",
         "Σ|H_t-L_{t-1}| / Σ TR",
         "Upward-swing intensity indicator.",
         _vortex(w, "up"), params={"window": w})
    _reg(f"price.regime.vortex_dn_{w}", f"Vortex Down ({w})", "Regime", "vortex",
         f"Σ|L_t − H_{{t-1}}| / Σ TR over {w}.",
         "Σ|L_t-H_{t-1}| / Σ TR",
         "Downward-swing intensity indicator.",
         _vortex(w, "dn"), params={"window": w})

# ADX-flavored directional strength (RMS of momentum)
def _adx_proxy(w_):
    def f(df):
        up = (df["high"].diff()).clip(lower=0)
        dn = (-df["low"].diff()).clip(lower=0)
        pdm = up.where(up > dn, 0).rolling(w_, min_periods=w_).sum()
        ndm = dn.where(dn > up, 0).rolling(w_, min_periods=w_).sum()
        tr = tc.true_range(df).rolling(w_, min_periods=w_).sum().replace(0, np.nan)
        pdi = 100 * pdm / tr
        ndi = 100 * ndm / tr
        dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
        return dx.rolling(w_, min_periods=w_).mean()
    return f

for w in [14, 30]:
    _reg(f"price.regime.adx_{w}", f"ADX-like Directional Strength ({w})",
         "Regime", "adx",
         f"Smoothed |+DI − -DI|/(+DI + -DI) over {w}.",
         "SMA_w(|+DI - -DI|·100 / (+DI + -DI))",
         "High values = strongly directional regime (regardless of side).",
         _adx_proxy(w), params={"window": w})

# DeMarker
def _demarker(w_):
    def f(df):
        h, l = df["high"], df["low"]
        dmax = (h - h.shift(1)).clip(lower=0)
        dmin = (l.shift(1) - l).clip(lower=0)
        num = dmax.rolling(w_, min_periods=w_).sum()
        den = num + dmin.rolling(w_, min_periods=w_).sum()
        return num / den.replace(0, np.nan)
    return f

for w in [14]:
    _reg(f"price.regime.demarker_{w}", f"DeMarker ({w})", "Regime", "demarker",
         f"Σ ΔH+ / (Σ ΔH+ + Σ ΔL−) over {w}.",
         "DMax_w / (DMax_w + DMin_w)",
         "0.5 = balanced; >0.7 stretched up; <0.3 stretched down.",
         _demarker(w), params={"window": w})

# Trend Intensity Index (share of returns above a rolling MA)
def _trend_intensity(w_):
    def f(df):
        p = _p(df)
        ma = p.rolling(w_, min_periods=w_).mean()
        above = (p > ma).astype(float)
        return above.rolling(w_, min_periods=w_).mean()
    return f

for w in [20, 50]:
    _reg(f"price.regime.trend_intensity_{w}",
         f"Trend Intensity Index ({w})", "Regime", "trend_intensity",
         f"Fraction of last {w} bars closing above SMA{w}.",
         "(1/w) Σ 1[P > SMA_w]",
         "Persistent bull/bear pressure measure.",
         _trend_intensity(w), params={"window": w})

# Rate-of-Change (equivalent to simple_return but named for tradition)
# NB: skipped — mathematically identical to price.motion.simple_return_n

# Squeeze-momentum-flavored trend strength: slope of linear regression
def _lr_slope(w_):
    def f(df):
        p = _p(df).values
        x = np.arange(w_)
        out = np.full(len(p), np.nan)
        for i in range(w_ - 1, len(p)):
            y = p[i - w_ + 1:i + 1]
            slope, _ = np.polyfit(x, y, 1)
            out[i] = slope
        return pd.Series(out, index=df.index)
    return f

for w in [20, 50]:
    _reg(f"price.motion.lr_slope_{w}",
         f"Linear-Regression Slope ({w})", "Motion", "trend_slope",
         f"OLS slope of price on time index over {w} bars.",
         "β_1 in P_t = β_0 + β_1·t",
         "Best-fit trend slope; sign = direction, magnitude = pace.",
         _lr_slope(w), params={"window": w})

# R² of that regression — trend quality
def _lr_r2(w_):
    def f(df):
        p = _p(df).values
        x = np.arange(w_)
        out = np.full(len(p), np.nan)
        for i in range(w_ - 1, len(p)):
            y = p[i - w_ + 1:i + 1]
            slope, intercept = np.polyfit(x, y, 1)
            yhat = slope * x + intercept
            ss_res = np.sum((y - yhat) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            out[i] = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
        return pd.Series(out, index=df.index)
    return f

for w in [20, 50]:
    _reg(f"price.geometry.lr_r2_{w}",
         f"Linear Regression R² ({w})", "Geometry", "trend_quality",
         f"R² of OLS trend fit over {w} bars.",
         "1 - SS_res/SS_tot",
         "1 = perfect trend; 0 = noise dominates.",
         _lr_r2(w), params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# INFORMATION THEORY — Structural complexity and noise
# ═══════════════════════════════════════════════════════════════════════

for w in [20, 50]:
    _reg(f"price.information.permutation_entropy_{w}",
         f"Permutation Entropy ({w})", "Information", "complexity",
         f"Permutation entropy of price over {w} bars (order=3).",
         "H(π) / log(3!)",
         "Low value indicates strong deterministic structure. High indicates noise.",
         (lambda w_: (lambda df: info.permutation_entropy(_p(df), w_, order=3)))(w),
         params={"window": w}, complexity="O(n)")

    _reg(f"price.information.sample_entropy_{w}",
         f"Sample Entropy ({w})", "Information", "regularity",
         f"Sample entropy of price over {w} bars.",
         "-ln(A/B)",
         "Low value indicates predictability and self-similarity.",
         (lambda w_: (lambda df: info.sample_entropy(_p(df), w_)))(w),
         params={"window": w}, complexity="O(n^2)")


# ═══════════════════════════════════════════════════════════════════════
# SPECTRAL ANALYSIS — Frequency domain and phase
# ═══════════════════════════════════════════════════════════════════════

for w in [20, 50]:
    _reg(f"price.spectral.hilbert_phase_{w}",
         f"Hilbert Phase ({w})", "Spectral", "phase",
         f"Instantaneous analytic phase over {w} bars.",
         "arctan(H(P) / P)",
         "Zero-lag phase ∈ [-π, +π] for cyclical turning points.",
         (lambda w_: (lambda df: sp.hilbert_phase(_p(df), w_)))(w),
         params={"window": w}, complexity="O(n)")


# ═══════════════════════════════════════════════════════════════════════
# ESOTERIC EDGE — Institutional HFT Proxies
# ═══════════════════════════════════════════════════════════════════════

# Corwin-Schultz Spread Estimator (Liquidity Proxy)
for w in W_MED:
    registry.register(FeatureDefinition(
        id=f"price.liquidity.corwin_schultz_spread_{w}",
        name=f"Corwin-Schultz Spread ({w})",
        layer=1, module="price", perspective="Liquidity", family="spread",
        definition=f"OHLCV implied bid-ask spread over {w} bars.",
        formula="S = f(H, L)",
        interpretation="Rising spread implies liquidity depletion.",
        inputs=["high", "low"],
        params={"w": w},
        complexity="O(w)",
        fn=lambda df, pw=w: liq.corwin_schultz_spread(df["high"], df["low"], pw)
    ))

# Fractional Differencing (Stationary Memory)
for d in [0.4, 0.6]:
    registry.register(FeatureDefinition(
        id=f"price.memory.fractional_diff_d{int(d*10)}",
        name=f"Fractional Difference (d={d})",
        layer=1, module="price", perspective="Memory", family="stationarity",
        definition=f"Price fractionally differenced with d={d}.",
        formula="(1-B)^d X_t",
        interpretation="Stationary price with preserved long-term memory.",
        inputs=["close"],
        params={"d": d},
        complexity="O(n)",
        fn=lambda df, pd=d: fdiff.frac_diff(df["close"], pd)
    ))

# Hill Estimator (Tail Risk)
for w in W_MED_LONG:
    registry.register(FeatureDefinition(
        id=f"price.risk.hill_estimator_{w}",
        name=f"Hill Estimator ({w})",
        layer=1, module="price", perspective="Risk", family="tail",
        definition=f"Extreme tail index over {w} bars.",
        formula="Mean(log(Top K / Threshold))",
        interpretation="Decreasing index implies fat tails and extreme crash risk.",
        inputs=["close"],
        params={"w": w},
        complexity="O(w log w)",
        fn=lambda df, pw=w: dist.hill_estimator(df["close"], pw)
    ))

# L-Kurtosis (Robust distribution shape)
for w in W_MED_LONG:
    registry.register(FeatureDefinition(
        id=f"price.risk.l_kurtosis_{w}",
        name=f"L-Kurtosis ({w})",
        layer=1, module="price", perspective="Risk", family="moments",
        definition=f"Robust L-Kurtosis over {w} bars.",
        formula="L4 / L2",
        interpretation="Rising L-Kurtosis implies frequent extreme events.",
        inputs=["close"],
        params={"w": w},
        complexity="O(w^2)",
        fn=lambda df, pw=w: lm.lmoment(df["close"], pw, 4)
    ))

# Roll Measure (Latency / Bid-Ask Bounce)
for w in W_MED:
    registry.register(FeatureDefinition(
        id=f"price.liquidity.roll_measure_{w}",
        name=f"Roll Measure ({w})",
        layer=1, module="price", perspective="Liquidity", family="spread",
        definition=f"Roll Measure (serial covariance) over {w} bars.",
        formula="2 * -Cov(dP_t, dP_{t-1})",
        interpretation="Higher values indicate stronger bid-ask bounce and illiquidity.",
        inputs=["close"],
        params={"w": w},
        complexity="O(w)",
        fn=lambda df, pw=w: liq.roll_measure(df["close"], pw)
    ))

# Haar Discrete Wavelet Transform (Time-Frequency Decomposition)
for level in [1, 2]:
    registry.register(FeatureDefinition(
        id=f"price.dsp.haar_approx_l{level}",
        name=f"Haar Approximation (Level {level})",
        layer=1, module="price", perspective="DSP", family="wavelet",
        definition=f"Haar DWT Approximation at level {level}.",
        formula="Low-pass filter of price.",
        interpretation="Fundamental low-frequency trend of the market.",
        inputs=["close"],
        params={"level": level},
        complexity="O(n)",
        fn=lambda df, pl=level: wav.haar_approximation(df["close"], pl)
    ))
    registry.register(FeatureDefinition(
        id=f"price.dsp.haar_detail_l{level}",
        name=f"Haar Detail (Level {level})",
        layer=1, module="price", perspective="DSP", family="wavelet",
        definition=f"Haar DWT Detail at level {level}.",
        formula="High-pass filter of price.",
        interpretation="High-frequency microstructure noise and volatility.",
        inputs=["close"],
        params={"level": level},
        complexity="O(n)",
        fn=lambda df, pl=level: wav.haar_detail(df["close"], pl)
    ))

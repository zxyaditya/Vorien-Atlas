"""Volatility Module — Layer 1.

Volatility is a PROPERTY of returns. This module represents that property
across every mathematically-justified estimator and every Perspective.

Base estimators (each a distinct mathematical construction over OHLCV):
  • CC   — Close-to-close realized vol (std of log-returns)
  • PK   — Parkinson (H, L)
  • GK   — Garman-Klass (O, H, L, C)
  • RS   — Rogers-Satchell (drift-independent)
  • YZ   — Yang-Zhang (overnight + intraday)
  • Semivariance (upside, downside)

Then we apply Atlas Perspectives to the volatility time-series itself:
its motion, geometry, distribution, entropy, expansion, clustering, regime.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.engines import statistics as st, motion as mo, geometry as ge
from atlas_core.engines import distribution as di, normalization as no
from atlas_core.engines import fractal as fr, information as info
from atlas_core.engines import technical as tc

MODULE = "volatility"


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["open", "high", "low", "close"], params=params or {},
        complexity=complexity, fn=fn,
    ))


# ═══════════════════════════════════════════════════════════════════════
# BASE ESTIMATORS (each is a Magnitude-Perspective feature at multi-w)
# ═══════════════════════════════════════════════════════════════════════
def _log_ret(df):
    return np.log(df["close"] / df["close"].shift(1))


def rv_cc(df, w):
    return _log_ret(df).rolling(w, min_periods=w).std(ddof=1)


def rv_parkinson(df, w):
    hl = np.log(df["high"] / df["low"])
    return np.sqrt((hl ** 2 / (4 * np.log(2))).rolling(w, min_periods=w).mean())


def rv_garman_klass(df, w):
    hl = np.log(df["high"] / df["low"])
    co = np.log(df["close"] / df["open"])
    gk = 0.5 * hl ** 2 - (2 * np.log(2) - 1) * co ** 2
    return np.sqrt(gk.rolling(w, min_periods=w).mean().clip(lower=0))


def rv_rogers_satchell(df, w):
    ho = np.log(df["high"] / df["open"])
    lo = np.log(df["low"] / df["open"])
    co = np.log(df["close"] / df["open"])
    rs = ho * (ho - co) + lo * (lo - co)
    return np.sqrt(rs.rolling(w, min_periods=w).mean().clip(lower=0))


def rv_yang_zhang(df, w):
    log_ho = np.log(df["high"] / df["open"])
    log_lo = np.log(df["low"] / df["open"])
    log_co = np.log(df["close"] / df["open"])
    log_oc = np.log(df["open"] / df["close"].shift(1))
    so2 = log_oc.rolling(w, min_periods=w).var(ddof=1)
    sc2 = log_co.rolling(w, min_periods=w).var(ddof=1)
    rs = (log_ho * (log_ho - log_co) + log_lo * (log_lo - log_co)) \
        .rolling(w, min_periods=w).mean()
    k = 0.34 / (1.34 + (w + 1) / max(w - 1, 1))
    return np.sqrt((so2 + k * sc2 + (1 - k) * rs).clip(lower=0))


def rv_downside(df, w):
    r = _log_ret(df)
    return np.sqrt((r.clip(upper=0) ** 2).rolling(w, min_periods=w).mean())


def rv_upside(df, w):
    r = _log_ret(df)
    return np.sqrt((r.clip(lower=0) ** 2).rolling(w, min_periods=w).mean())


# Register the five canonical estimators + upside/downside semi-vol
_ESTIMATORS = {
    "cc":   (rv_cc,               "Close-to-Close σ",   "std(ln(P_t/P_{t-1}))"),
    "pk":   (rv_parkinson,        "Parkinson σ",        "√(mean((ln H/L)²)/(4 ln 2))"),
    "gk":   (rv_garman_klass,     "Garman-Klass σ",     "√(mean(0.5(ln H/L)² - (2ln2-1)(ln C/O)²))"),
    "rs":   (rv_rogers_satchell,  "Rogers-Satchell σ",  "√(mean(u(u-c) + d(d-c)))"),
    "yz":   (rv_yang_zhang,       "Yang-Zhang σ",       "√(σ_o² + kσ_c² + (1-k)σ_rs²)"),
    "down": (rv_downside,         "Downside σ",         "√(mean(min(r,0)²))"),
    "up":   (rv_upside,           "Upside σ",           "√(mean(max(r,0)²))"),
}

# ═══════════════════════════════════════════════════════════════════════
# MAGNITUDE — volatility level, each estimator × canonical windows
# ═══════════════════════════════════════════════════════════════════════
for est, (fn, name, formula) in _ESTIMATORS.items():
    for w in [10, 20, 50]:
        _reg(f"volatility.magnitude.{est}_{w}",
             f"{name} ({w})", "Magnitude", f"estimator_{est}",
             f"{name} over {w} bars.", formula,
             f"{name}: a distinct mathematical construction of volatility.",
             (lambda f_, w_: (lambda df: f_(df, w_)))(fn, w),
             params={"window": w, "estimator": est})

# Semi-vol ratios (upside vs downside)
for w in [20, 50]:
    _reg(f"volatility.magnitude.semi_ratio_{w}",
         f"Upside/Downside σ Ratio ({w})", "Magnitude", "asymmetry",
         "Upside semi-vol divided by downside semi-vol.",
         "σ_up / σ_down",
         ">1 = upward volatility dominates.",
         (lambda w_: (lambda df: rv_upside(df, w_) /
                                 rv_downside(df, w_).replace(0, np.nan)))(w),
         params={"window": w})


# Helper: canonical vol series (Yang-Zhang @ 20) for cross-Perspective work
def _sigma_ref(df, w=20):
    return rv_yang_zhang(df, w)


def _sigma_short(df):
    return rv_yang_zhang(df, 10)


def _sigma_long(df):
    return rv_yang_zhang(df, 50)


# ═══════════════════════════════════════════════════════════════════════
# MOTION — derivatives of volatility
# ═══════════════════════════════════════════════════════════════════════
for dt in [1, 5, 20]:
    _reg(f"volatility.motion.log_return_{dt}",
         f"Log-Vol Return ({dt})", "Motion", "log_vol_returns",
         f"Log-return of the Yang-Zhang σ series over {dt} bars.",
         "ln(σ_t / σ_{t-dt})",
         "Multiplicative change in volatility.",
         (lambda dt_: (lambda df: mo.log_return(_sigma_ref(df), dt_)))(dt),
         params={"dt": dt, "base": "yz_20"})

for dt in [1, 5]:
    _reg(f"volatility.motion.velocity_{dt}",
         f"σ Velocity ({dt})", "Motion", "derivative",
         f"First difference of σ over {dt} bars.",
         "σ_t - σ_{t-dt}",
         "How fast volatility is changing.",
         (lambda dt_: (lambda df: mo.velocity(_sigma_ref(df), dt_)))(dt),
         params={"dt": dt, "base": "yz_20"})

_reg("volatility.motion.acceleration",
     "σ Acceleration", "Motion", "derivative_2",
     "Second difference of σ.", "Δ²σ",
     "Rate-of-change of vol velocity.",
     lambda df: mo.acceleration(_sigma_ref(df), 1))

for span in [10, 20, 50]:
    _reg(f"volatility.motion.ema_sigma_{span}",
         f"EMA(σ) span={span}", "Motion", "smoothed_level",
         f"Exponential moving average of the σ series.",
         f"EMA_{span}(σ)",
         "Recency-weighted volatility level.",
         (lambda s_: (lambda df: tc.ema(_sigma_ref(df), s_)))(span),
         params={"span": span, "base": "yz_20"})


# ═══════════════════════════════════════════════════════════════════════
# GEOMETRY — trajectory of the σ series
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50, 100]:
    _reg(f"volatility.geometry.path_length_{w}",
         f"σ Path Length ({w})", "Geometry", "trajectory",
         f"Total absolute path length of σ over {w} bars.",
         "Σ|Δσ|",
         "How much volatility itself has traveled.",
         (lambda w_: (lambda df: ge.path_length(_sigma_ref(df), w_)))(w),
         params={"window": w})

    _reg(f"volatility.geometry.straightness_{w}",
         f"σ Straightness ({w})", "Geometry", "trajectory",
         f"|net σ change| / σ path length over {w} bars.",
         "|σ_t - σ_{t-w}| / Σ|Δσ|",
         "1 = smooth vol trend; 0 = zig-zag vol.",
         (lambda w_: (lambda df: ge.straightness(_sigma_ref(df), w_)))(w),
         params={"window": w})

for w in [50, 100]:
    _reg(f"volatility.geometry.higuchi_fd_{w}",
         f"σ Higuchi FD ({w})", "Geometry", "fractal",
         f"Higuchi fractal dimension of σ over {w} bars.",
         "slope log(L(k)) vs log(1/k)",
         "Fractal roughness of the volatility path.",
         (lambda w_: (lambda df: fr.higuchi_fd(_sigma_ref(df), w_)))(w),
         params={"window": w}, complexity="O(nlogn)")


# ═══════════════════════════════════════════════════════════════════════
# RELATIVE — volatility vs its own history & vs price
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50, 100]:
    _reg(f"volatility.relative.dist_ma_{w}",
         f"σ Distance from MA{w}", "Relative", "vol_ma_distance",
         f"Relative distance of σ from its SMA{w}.",
         "(σ - SMA_w(σ)) / SMA_w(σ)",
         "% deviation of vol from its own mean.",
         (lambda w_: (lambda df: (_sigma_ref(df) - st.rolling_mean(_sigma_ref(df), w_)) /
                                 st.rolling_mean(_sigma_ref(df), w_).replace(0, np.nan)))(w),
         params={"window": w})

# Cross-estimator ratios (Parkinson vs CC, GK vs RS) — signal of drift vs range
for pair in [("pk", "cc"), ("gk", "cc"), ("rs", "cc"), ("yz", "cc")]:
    a, b = pair
    fa, _, _ = _ESTIMATORS[a]
    fb, _, _ = _ESTIMATORS[b]
    _reg(f"volatility.relative.ratio_{a}_over_{b}_20",
         f"{a.upper()}/{b.upper()} σ Ratio (20)", "Relative", "estimator_ratio",
         f"Ratio of {a.upper()} vol to {b.upper()} vol at w=20.",
         f"σ_{a} / σ_{b}",
         "Divergence between estimators — informs microstructure noise.",
         (lambda fa_, fb_: (lambda df: fa_(df, 20) / fb_(df, 20).replace(0, np.nan)))(fa, fb),
         params={"window": 20, "num": a, "den": b})


# ═══════════════════════════════════════════════════════════════════════
# POSITION — where does σ sit in its own historical distribution
# ═══════════════════════════════════════════════════════════════════════
for w in [50, 100, 200]:
    _reg(f"volatility.position.pct_rank_{w}",
         f"σ Percentile Rank ({w})", "Position", "distribution_position",
         f"Empirical CDF value of current σ in {w}-bar window.",
         "F̂_w(σ_t)",
         "0 = calmest in window, 1 = most volatile.",
         (lambda w_: (lambda df: di.rolling_percentile_rank(_sigma_ref(df), w_)))(w),
         params={"window": w})

for w in [50, 100]:
    _reg(f"volatility.position.minmax_{w}",
         f"σ Min-Max Position ({w})", "Position", "range_position",
         f"σ position within {w}-bar min-max range.",
         "(σ - min_w)/(max_w - min_w)",
         "Normalized position within recent vol range.",
         (lambda w_: (lambda df: no.min_max(_sigma_ref(df), w_)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# STATISTICS — moments of the σ series
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50, 100]:
    _reg(f"volatility.statistics.mean_{w}",
         f"σ Mean ({w})", "Statistics", "moments",
         f"Mean σ over {w} bars.", "mean(σ)_w",
         "Central level of recent volatility.",
         (lambda w_: (lambda df: st.rolling_mean(_sigma_ref(df), w_)))(w),
         params={"window": w})
    _reg(f"volatility.statistics.std_{w}",
         f"Vol-of-Vol σ({w})", "Statistics", "vol_of_vol",
         f"Std of σ over {w} — vol-of-vol.", "σ(σ)_w",
         "Instability of volatility itself.",
         (lambda w_: (lambda df: st.rolling_std(_sigma_ref(df), w_)))(w),
         params={"window": w})

for w in [50, 100]:
    _reg(f"volatility.statistics.skew_{w}",
         f"σ Skewness ({w})", "Statistics", "moments",
         f"Skewness of σ over {w}.", "E[((σ-μ)/σ_σ)³]",
         "Asymmetry of the vol distribution.",
         (lambda w_: (lambda df: st.rolling_skew(_sigma_ref(df), w_)))(w),
         params={"window": w})
    _reg(f"volatility.statistics.kurt_{w}",
         f"σ Kurtosis ({w})", "Statistics", "moments",
         f"Excess kurtosis of σ over {w}.", "E[((σ-μ)/σ_σ)⁴]-3",
         "Tail heaviness of the vol distribution.",
         (lambda w_: (lambda df: st.rolling_kurt(_sigma_ref(df), w_)))(w),
         params={"window": w})

# Autocorrelation of log-vol at multi-lag (Volatility persistence)
for lag in [1, 5, 10]:
    _reg(f"volatility.statistics.log_vol_acf_lag{lag}",
         f"log-σ Autocorr lag {lag}", "Statistics", "persistence",
         f"Lag-{lag} autocorrelation of log(σ) over 60 bars.",
         f"ρ(ln σ_t, ln σ_{{t-{lag}}})",
         "Persistence memory of volatility — GARCH-like signature.",
         (lambda lag_: (lambda df: st.rolling_autocorr(np.log(_sigma_ref(df)
                                                             .replace(0, np.nan)),
                                                       60, lag_)))(lag),
         params={"lag": lag, "window": 60})


# ═══════════════════════════════════════════════════════════════════════
# DISTRIBUTION — quantiles of σ, VaR-of-vol
# ═══════════════════════════════════════════════════════════════════════
for q in [0.1, 0.5, 0.9]:
    for w in [100]:
        _reg(f"volatility.distribution.q{int(q*100)}_{w}",
             f"σ Quantile {int(q*100)}% ({w})",
             "Distribution", "quantiles",
             f"{int(q*100)}th percentile of σ over {w}.",
             f"Q_{{{q}}}(σ)_{w}",
             "Volatility percentile level.",
             (lambda w_, q_: (lambda df: di.rolling_quantile(_sigma_ref(df), w_, q_)))(w, q),
             params={"window": w, "q": q})


# ═══════════════════════════════════════════════════════════════════════
# ENTROPY — information content of the σ series
# ═══════════════════════════════════════════════════════════════════════
for w in [60]:
    _reg(f"volatility.entropy.shannon_{w}",
         f"σ Shannon Entropy ({w})", "Entropy", "information",
         f"Shannon entropy of the σ histogram over {w}.",
         "-Σ p log p",
         "Uncertainty in the volatility distribution.",
         (lambda w_: (lambda df: st.rolling_entropy(_sigma_ref(df), w_)))(w),
         params={"window": w})

    _reg(f"volatility.entropy.perm_o3_{w}",
         f"σ Permutation Entropy ({w})", "Entropy", "ordinal",
         f"Permutation entropy (order 3) of σ over {w}.",
         "H(π) / log(3!)",
         "Ordinal complexity of vol changes.",
         (lambda w_: (lambda df: info.permutation_entropy(_sigma_ref(df), w_, 3)))(w),
         params={"window": w, "order": 3}, complexity="O(nlogn)")


# ═══════════════════════════════════════════════════════════════════════
# EXPANSION — multi-scale vol ratios (short/long)
# ═══════════════════════════════════════════════════════════════════════
_reg("volatility.expansion.short_long_ratio",
     "σ_short / σ_long", "Expansion", "multi_scale",
     "10-bar σ divided by 50-bar σ (both Yang-Zhang).",
     "σ_10 / σ_50",
     ">1 short-term vol elevated vs baseline.",
     lambda df: _sigma_short(df) / _sigma_long(df).replace(0, np.nan))

_reg("volatility.expansion.log_short_long_ratio",
     "log(σ_short/σ_long)", "Expansion", "multi_scale",
     "Natural log of the short/long σ ratio.",
     "ln(σ_10/σ_50)",
     "Symmetric expansion/contraction signal.",
     lambda df: np.log(_sigma_short(df) / _sigma_long(df).replace(0, np.nan)))


# ═══════════════════════════════════════════════════════════════════════
# CLUSTERING — squared-return persistence over σ-normalized returns
# ═══════════════════════════════════════════════════════════════════════
def _std_returns(df, w=20):
    r = _log_ret(df)
    s = _sigma_ref(df, w)
    return r / s.replace(0, np.nan)

for lag in [1, 2, 5]:
    _reg(f"volatility.clustering.std_ret_acf_lag{lag}",
         f"Vol-Std'd Return² ACF (lag {lag})", "Clustering", "conditional",
         f"Lag-{lag} autocorrelation of (r/σ)² over 60 bars.",
         f"ρ((r/σ)_t², (r/σ)_{{t-{lag}}}²)",
         "Residual clustering after volatility standardization.",
         (lambda lag_: (lambda df: st.rolling_autocorr(_std_returns(df) ** 2,
                                                       60, lag_)))(lag),
         params={"lag": lag, "window": 60})


# ═══════════════════════════════════════════════════════════════════════
# REGIME — vol-state regimes
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50]:
    _reg(f"volatility.regime.above_ma_{w}",
         f"σ Above MA{w}", "Regime", "vol_regime",
         f"Sign of (σ - SMA_{w}(σ)).", "sign(σ - SMA_w(σ))",
         "+1 elevated-vol regime, -1 calm-vol regime.",
         (lambda w_: (lambda df: np.sign(_sigma_ref(df) -
                                          st.rolling_mean(_sigma_ref(df), w_))))(w),
         params={"window": w})

# High-vol / normal / low-vol tercile flag
def _vol_tercile(df):
    s = _sigma_ref(df)
    q33 = s.rolling(200, min_periods=100).quantile(0.33)
    q66 = s.rolling(200, min_periods=100).quantile(0.66)
    out = pd.Series(0.0, index=df.index)
    out[s < q33] = -1.0
    out[s > q66] = 1.0
    return out

_reg("volatility.regime.tercile_200",
     "σ Tercile Regime (200)", "Regime", "vol_regime",
     "-1 low / 0 normal / +1 high based on rolling 33/66 quantiles.",
     "sign relative to Q_33, Q_66 over 200 bars",
     "Categorical volatility regime.",
     _vol_tercile, params={"window": 200})

# GARCH-adjacent: rolling correlation between |r| and prior |r|
_reg("volatility.regime.abs_ret_persistence_60",
     "|r| Persistence (60)", "Regime", "vol_persistence",
     "Rolling correlation between |r_t| and |r_{t-1}| over 60 bars.",
     "ρ(|r_t|, |r_{t-1}|)",
     "Strong positive value → volatility clusters (GARCH regime).",
     lambda df: st.rolling_autocorr(_log_ret(df).abs(), 60, 1))

# ═══════════════════════════════════════════════════════════════════════
# ESOTERIC EDGE — High-Efficiency Volatility
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50, 100]:
    registry.register(FeatureDefinition(
        id=f"volatility.efficiency.garman_klass_{w}",
        name=f"Garman-Klass Volatility ({w})",
        layer=1, module="volatility", perspective="Efficiency", family="estimator",
        definition=f"Garman-Klass high-efficiency volatility over {w} bars.",
        formula="sqrt( 0.5(ln(H/L))^2 - ... )",
        interpretation="Superior estimate of variance for non-trending markets.",
        inputs=["open", "high", "low", "close"],
        params={"w": w},
        complexity="O(n)",
        fn=(lambda w_: (lambda df: st.garman_klass_volatility(df["open"], df["high"], df["low"], df["close"], w_)))(w)
    ))

    registry.register(FeatureDefinition(
        id=f"volatility.efficiency.rogers_satchell_{w}",
        name=f"Rogers-Satchell Volatility ({w})",
        layer=1, module="volatility", perspective="Efficiency", family="estimator",
        definition=f"Rogers-Satchell drift-independent volatility over {w} bars.",
        formula="sqrt( ln(H/C)ln(H/O) + ln(L/C)ln(L/O) )",
        interpretation="Superior estimate of variance for trending markets with drift.",
        inputs=["open", "high", "low", "close"],
        params={"w": w},
        complexity="O(n)",
        fn=(lambda w_: (lambda df: st.rogers_satchell_volatility(df["open"], df["high"], df["low"], df["close"], w_)))(w)
    ))

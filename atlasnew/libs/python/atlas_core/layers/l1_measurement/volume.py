"""Volume Module — Layer 1.

Volume is a property of trade activity. Represented across the same
Perspective grammar as Price and Volatility.

Base quantities:
  • V_t         — raw traded volume
  • log V_t     — log volume
  • Dollar-vol  — P·V, monetary intensity of trading
  • Signed vol  — V·sign(r), buy/sell pressure proxy
  • VWAP        — volume-weighted average price (used as reference)
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.engines import statistics as st, motion as mo, geometry as ge
from atlas_core.engines import distribution as di, normalization as no
from atlas_core.engines import information as info, technical as tc
from atlas_core.engines import point_process as pp
from atlas_core.engines import liquidity as liq
from atlas_core.engines import flow_proxy as fp

MODULE = "volume"


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["close", "volume"], params=params or {},
        complexity=complexity, fn=fn,
    ))


def _v(df):
    return df["volume"].astype(float)


def _logv(df):
    return np.log(_v(df).replace(0, np.nan))


def _dollar(df):
    return df["close"].astype(float) * _v(df)


def _signed(df):
    return _v(df) * np.sign(df["close"].astype(float).diff()).fillna(0)


def _vwap(df, w):
    v = _v(df)
    return (df["close"] * v).rolling(w, min_periods=w).sum() / \
           v.rolling(w, min_periods=w).sum().replace(0, np.nan)


# ═══════════════════════════════════════════════════════════════════════
# MAGNITUDE
# ═══════════════════════════════════════════════════════════════════════
_reg("volume.magnitude.raw", "Raw Volume", "Magnitude", "level",
     "Observed traded volume.", "V_t", "Bar's total traded units.",
     lambda df: _v(df))
_reg("volume.magnitude.log", "Log Volume", "Magnitude", "level",
     "Natural log of volume.", "ln V_t",
     "Log-scale volume (Gaussianizes the fat right tail).",
     lambda df: _logv(df))
_reg("volume.magnitude.dollar", "Dollar Volume", "Magnitude", "level",
     "Price × Volume.", "P_t · V_t",
     "Monetary intensity of trading.",
     lambda df: _dollar(df))
_reg("volume.magnitude.signed", "Signed Volume", "Magnitude", "flow",
     "Volume × sign(1-bar return).", "V_t · sign(r_t)",
     "Buy/sell-pressure proxy.",
     lambda df: _signed(df))

for w in [10, 20, 50]:
    _reg(f"volume.magnitude.vwap_{w}",
         f"VWAP ({w})", "Magnitude", "vwap",
         f"Volume-weighted average price over {w} bars.",
         "Σ(P·V) / Σ V",
         "Reference price weighted by traded activity.",
         (lambda w_: (lambda df: _vwap(df, w_)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# MOTION — how volume changes
# ═══════════════════════════════════════════════════════════════════════
for dt in [1, 5, 20]:
    _reg(f"volume.motion.log_return_{dt}",
         f"Log-Volume Return ({dt})", "Motion", "log_returns",
         f"Log-return of volume over {dt} bars.",
         "ln(V_t/V_{t-dt})",
         "Multiplicative change in trading activity.",
         (lambda dt_: (lambda df: mo.log_return(_v(df), dt_)))(dt),
         params={"dt": dt})

_reg("volume.motion.acceleration",
     "Volume Acceleration", "Motion", "derivative_2",
     "Second difference of volume.", "Δ²V",
     "Rate-of-change of volume changes.",
     lambda df: mo.acceleration(_v(df), 1))

# OBV — cumulative signed volume (accumulation)
def _obv(df):
    return _signed(df).cumsum()

_reg("volume.motion.obv",
     "OBV (On-Balance Volume)", "Motion", "accumulation",
     "Cumulative sum of signed volume.",
     "Σ V·sign(r)",
     "Running accumulation/distribution proxy.",
     _obv)

for span in [10, 20, 50]:
    _reg(f"volume.motion.ema_vol_{span}",
         f"EMA(V) span={span}", "Motion", "smoothed_level",
         f"Exponential moving average of volume, span={span}.",
         f"EMA_{span}(V)",
         "Recency-weighted volume baseline.",
         (lambda s_: (lambda df: tc.ema(_v(df), s_)))(span),
         params={"span": span})


# ═══════════════════════════════════════════════════════════════════════
# GEOMETRY — volume path
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50]:
    _reg(f"volume.geometry.path_length_{w}",
         f"Volume Path Length ({w})", "Geometry", "trajectory",
         f"Σ|ΔV| over {w}.",
         "Σ|ΔV|",
         "Total volume fluctuation across the window.",
         (lambda w_: (lambda df: ge.path_length(_v(df), w_)))(w),
         params={"window": w})

    _reg(f"volume.geometry.straightness_{w}",
         f"Volume Straightness ({w})", "Geometry", "trajectory",
         f"|net ΔV| / path length.",
         "|V_t - V_{t-w}| / Σ|ΔV|",
         "1 = monotonic volume trend; 0 = choppy.",
         (lambda w_: (lambda df: ge.straightness(_v(df), w_)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# RELATIVE — volume vs its own history & vs VWAP
# ═══════════════════════════════════════════════════════════════════════
for w in [10, 20, 50]:
    _reg(f"volume.relative.dist_ma_{w}",
         f"Volume vs MA{w}", "Relative", "vol_ma_distance",
         f"Volume relative to its own SMA{w}.",
         "(V - SMA_w(V)) / SMA_w(V)",
         "% deviation from average volume.",
         (lambda w_: (lambda df: (_v(df) - st.rolling_mean(_v(df), w_)) /
                                 st.rolling_mean(_v(df), w_).replace(0, np.nan)))(w),
         params={"window": w})

# Price vs VWAP distance — signals unusual price relative to volume-weighted mean
for w in [10, 20, 50]:
    _reg(f"volume.relative.price_vs_vwap_{w}",
         f"Price vs VWAP {w}", "Relative", "price_vwap",
         f"(P − VWAP_w) / VWAP_w.",
         "(P - VWAP_w) / VWAP_w",
         "Signed distance of price from volume-weighted mean.",
         (lambda w_: (lambda df: (df["close"] - _vwap(df, w_)) /
                                 _vwap(df, w_).replace(0, np.nan)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# POSITION — where is current volume within its own distribution
# ═══════════════════════════════════════════════════════════════════════
for w in [50, 100]:
    _reg(f"volume.position.pct_rank_{w}",
         f"Volume Percentile Rank ({w})", "Position", "distribution_position",
         f"Percentile rank of current volume in {w}-bar window.",
         "F̂_w(V_t)",
         "0 = quietest, 1 = heaviest in the window.",
         (lambda w_: (lambda df: di.rolling_percentile_rank(_v(df), w_)))(w),
         params={"window": w})


# ═══════════════════════════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50]:
    _reg(f"volume.statistics.mean_{w}",
         f"Volume Mean ({w})", "Statistics", "moments",
         f"Mean volume over {w}.", "mean(V)_w",
         "Baseline volume level.",
         (lambda w_: (lambda df: st.rolling_mean(_v(df), w_)))(w),
         params={"window": w})

    _reg(f"volume.statistics.std_{w}",
         f"Volume Std ({w})", "Statistics", "moments",
         f"Std of volume over {w}.", "σ(V)_w",
         "Dispersion of traded activity.",
         (lambda w_: (lambda df: st.rolling_std(_v(df), w_)))(w),
         params={"window": w})

    _reg(f"volume.statistics.zscore_log_{w}",
         f"log-V Z-Score ({w})", "Statistics", "standardized",
         f"Z-score of log volume over {w}.",
         "(ln V - μ_ln)/σ_ln",
         "Standard deviations of log-volume from local mean.",
         (lambda w_: (lambda df: no.zscore(_logv(df), w_)))(w),
         params={"window": w})

# Coefficient of variation
_reg("volume.statistics.cv_20", "Volume CV (20)", "Statistics",
     "relative_dispersion", "std(V)/mean(V) over 20.",
     "σ(V)/mean(V)", "Scale-free volume dispersion.",
     lambda df: st.rolling_std(_v(df), 20) /
                st.rolling_mean(_v(df), 20).replace(0, np.nan))


# ═══════════════════════════════════════════════════════════════════════
# DISTRIBUTION — quantiles of volume
# ═══════════════════════════════════════════════════════════════════════
for q in [0.1, 0.5, 0.9]:
    _reg(f"volume.distribution.q{int(q*100)}_100",
         f"Volume Q{int(q*100)}% (100)", "Distribution", "quantiles",
         f"{int(q*100)}th percentile of volume over 100 bars.",
         f"Q_{q}(V)_100", f"{int(q*100)}th percentile volume level.",
         (lambda q_: (lambda df: di.rolling_quantile(_v(df), 100, q_)))(q),
         params={"window": 100, "q": q})


# ═══════════════════════════════════════════════════════════════════════
# ENTROPY — information content of volume series
# ═══════════════════════════════════════════════════════════════════════
_reg("volume.entropy.shannon_60",
     "log-V Shannon Entropy (60)", "Entropy", "information",
     "Shannon entropy of log-volume histogram over 60 bars.",
     "-Σ p log p",
     "Uncertainty in the recent volume distribution.",
     lambda df: st.rolling_entropy(_logv(df), 60))

_reg("volume.entropy.perm_o3_30",
     "log-V Permutation Entropy (30)", "Entropy", "ordinal",
     "Permutation entropy of log-volume, order 3, w=30.",
     "H(π) / log(3!)",
     "Ordinal complexity of the volume sequence.",
     lambda df: info.permutation_entropy(_logv(df), 30, 3),
     complexity="O(nlogn)")


# ═══════════════════════════════════════════════════════════════════════
# EXPANSION — volume expansion/contraction
# ═══════════════════════════════════════════════════════════════════════
_reg("volume.expansion.short_long_ratio",
     "V_short / V_long", "Expansion", "multi_scale",
     "10-bar mean volume divided by 50-bar mean volume.",
     "mean(V)_10 / mean(V)_50",
     ">1 short-term volume above baseline.",
     lambda df: st.rolling_mean(_v(df), 10) /
                st.rolling_mean(_v(df), 50).replace(0, np.nan))


# ═══════════════════════════════════════════════════════════════════════
# CLUSTERING — volume persistence
# ═══════════════════════════════════════════════════════════════════════
for lag in [1, 5]:
    _reg(f"volume.clustering.log_v_acf_lag{lag}",
         f"log-V ACF lag {lag}", "Clustering", "persistence",
         f"Lag-{lag} autocorrelation of log-V over 60 bars.",
         f"ρ(ln V_t, ln V_{{t-{lag}}})",
         "Persistence memory of trading activity.",
         (lambda lag_: (lambda df: st.rolling_autocorr(_logv(df), 60, lag_)))(lag),
         params={"lag": lag, "window": 60})


# ═══════════════════════════════════════════════════════════════════════
# REGIME — volume regimes and flow
# ═══════════════════════════════════════════════════════════════════════
for w in [20, 50]:
    _reg(f"volume.regime.above_ma_{w}",
         f"Volume Above MA{w}", "Regime", "flow_regime",
         f"Sign of (V - SMA_{w}(V)).", "sign(V - SMA_w(V))",
         "+1 elevated activity, -1 quiet regime.",
         (lambda w_: (lambda df: np.sign(_v(df) - st.rolling_mean(_v(df), w_))))(w),
         params={"window": w})

# Money flow-like: signed volume EMA (accumulation regime)
_reg("volume.regime.signed_ema_20",
     "Signed Vol EMA(20)", "Regime", "flow_regime",
     "EMA of signed volume — smoothed net buying pressure.",
     "EMA_20(V·sign(r))",
     ">0 = net buying regime, <0 = net selling regime.",
     lambda df: tc.ema(_signed(df), 20))

# Volume-price divergence: rising price but falling volume EMA (weakness)
def _vp_divergence(df):
    pxs = df["close"]
    px_up = np.sign(pxs.diff(20))
    vol_slope = tc.ema(_v(df), 20).diff(20)
    vol_up = np.sign(vol_slope)
    # +1 both up (confirmation), -1 divergence (price up vol down or vice versa)
    return (px_up * vol_up)

_reg("volume.regime.pv_confirmation_20",
     "Price-Volume Confirmation (20)", "Regime", "confirmation",
     "Sign(Δprice_20) · Sign(ΔEMA_20(V)).",
     "sign(ΔP_20) · sign(ΔEMA_20(V))",
     "+1 = price trend confirmed by volume, -1 = divergence.",
     _vp_divergence, params={"window": 20})


# ═══════════════════════════════════════════════════════════════════════
# MICROSTRUCTURE — institutional flow proxies
# ═══════════════════════════════════════════════════════════════════════
from atlas_core.engines.flow_proxy import vpin

for w in [20, 50, 100]:
    _reg(f"volume.microstructure.vpin_{w}",
         f"VPIN ({w})", "Microstructure", "institutional_flow",
         f"Volume-Synchronized Probability of Informed Trading over {w} bars.",
         "Σ|BuyV - SellV| / ΣV",
         "High values indicate institutional accumulation/distribution.",
         (lambda w_: (lambda df: vpin(df, w_)))(w),
         params={"window": w}, complexity="O(n)")

# ═══════════════════════════════════════════════════════════════════════
# ESOTERIC EDGE — Institutional HFT Proxies
# ═══════════════════════════════════════════════════════════════════════
for w in [50, 100]:
    for kappa in [0.1, 0.2]:
        registry.register(FeatureDefinition(
            id=f"volume.microstructure.hawkes_intensity_{w}_k{int(kappa*100)}",
            name=f"Hawkes Intensity ({w}, {kappa})",
            layer=1, module="volume", perspective="Microstructure", family="point_process",
            definition=f"Hawkes process intensity of volume shocks (w={w}, kappa={kappa}).",
            formula="lambda_t = ewm(shock)",
            interpretation="Rising intensity indicates infectious volume clustering.",
            inputs=["volume"],
            params={"w": w, "kappa": kappa},
            complexity="O(w)",
            fn=(lambda w_, k_: (lambda df: pp.hawkes_intensity(_v(df), w_, k_)))(w, kappa)
        ))


for w in [20, 50, 100]:
    registry.register(FeatureDefinition(
        id=f"volume.microstructure.amihud_illiq_{w}",
        name=f"Amihud Illiquidity ({w})",
        layer=1, module="volume", perspective="Microstructure", family="liquidity",
        definition=f"Amihud illiquidity ratio over {w} bars.",
        formula="|R| / (V * P)",
        interpretation="Higher values indicate lower market depth and higher slippage.",
        inputs=["close", "open", "volume"],
        params={"w": w},
        complexity="O(n)",
        fn=(lambda w_: (lambda df: liq.amihud_illiquidity(df["close"], df["open"], df["volume"], w_)))(w)
    ))

    registry.register(FeatureDefinition(
        id=f"volume.microstructure.kyles_lambda_{w}",
        name=f"Kyle's Lambda ({w})",
        layer=1, module="volume", perspective="Microstructure", family="liquidity",
        definition=f"Kyle's Lambda (price impact) over {w} bars.",
        formula="Cov(|R|, SV) / Var(SV)",
        interpretation="Rising Lambda indicates decreasing market depth.",
        inputs=["close", "open", "volume"],
        params={"w": w},
        complexity="O(w)",
        fn=(lambda w_: (lambda df: liq.kyles_lambda(df["close"], df["open"], df["volume"], w_)))(w)
    ))

    registry.register(FeatureDefinition(
        id=f"volume.microstructure.invariance_w_{w}",
        name=f"Microstructure Invariance W ({w})",
        layer=1, module="volume", perspective="Microstructure", family="invariance",
        definition=f"Trading activity invariant W over {w} bars.",
        formula="V * P * sigma",
        interpretation="Deviations signal large institutional meta-orders.",
        inputs=["close", "volume"],
        params={"w": w},
        complexity="O(w)",
        fn=(lambda w_: (lambda df: liq.microstructure_invariant(df["close"], df["volume"], w_)))(w)
    ))

    registry.register(FeatureDefinition(
        id=f"volume.microstructure.vwap_zscore_{w}",
        name=f"VWAP Z-Score ({w})",
        layer=1, module="volume", perspective="Microstructure", family="flow",
        definition=f"VWAP deviation Z-score over {w} bars.",
        formula="(P - VWAP) / std(P)",
        interpretation="Extreme deviations indicate institutional footprinting or liquidity exhaustion.",
        inputs=["close", "volume"],
        params={"w": w},
        complexity="O(n)",
        fn=(lambda w_: (lambda df: fp.vwap_zscore(df, w_)))(w)
    ))

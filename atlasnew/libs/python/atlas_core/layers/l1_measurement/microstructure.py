"""Microstructure Module — Layer 1.

Book 1 places 'Candle Anatomy' and 'Market Microstructure' among the
legitimate L1 examples. This module represents the microstructure of
individual bars and their immediate participation — nothing more.

Rule: measurements only. Nothing named after an interpretation. Anything
resembling 'absorption', 'aggression', 'auction efficiency', 'acceptance'
or 'rejection' does not live here — those are L2/L3 questions and must
not appear in L1 (Invariant 6.5).

All 11 Subsystems ("Perspectives" per PRD) applied where mathematically
justified. Zero interpretation. Zero opinions.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.engines import (
    statistics as st, motion as mo, geometry as ge,
    distribution as di, normalization as no, information as info,
    technical as tc,
)
from atlas_core.engines import flow_proxy as fp

MODULE = "microstructure"


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["open", "high", "low", "close", "volume"],
        params=params or {}, complexity=complexity, fn=fn,
    ))


# ══════════════════════════════════════════════════════════════════════
# MAGNITUDE — raw bar anatomy quantities
# ══════════════════════════════════════════════════════════════════════
_reg("microstructure.magnitude.body", "Body Magnitude", "Magnitude",
     "anatomy", "|close - open|.", "|C - O|",
     "Absolute directional-body span per bar.", fp.abs_body)

_reg("microstructure.magnitude.signed_body", "Signed Body", "Magnitude",
     "anatomy", "close - open.", "C - O",
     "Signed body — magnitude with direction preserved.", fp.body)

_reg("microstructure.magnitude.bar_range", "Bar Range", "Magnitude",
     "anatomy", "high - low.", "H - L", "Full intra-bar extent.", fp.bar_range)

_reg("microstructure.magnitude.upper_wick", "Upper Wick", "Magnitude",
     "anatomy", "high - max(open, close).", "H - max(O,C)",
     "Upper wick length — pure measurement, no interpretation.", fp.upper_wick)

_reg("microstructure.magnitude.lower_wick", "Lower Wick", "Magnitude",
     "anatomy", "min(open, close) - low.", "min(O,C) - L",
     "Lower wick length — pure measurement.", fp.lower_wick)

_reg("microstructure.magnitude.turnover", "Dollar Turnover", "Magnitude",
     "turnover", "close × volume per bar.", "C_t · V_t",
     "Notional value transacted this bar.", fp.turnover)

_reg("microstructure.magnitude.up_body_volume", "Up-Body Volume",
     "Magnitude", "pressure",
     "V × max(body,0) / range — volume weighted by upside body.",
     "V · max(C-O,0) / (H-L)",
     "Positive-side pressure primitive. Measurement, not interpretation.",
     fp.up_body_volume)

_reg("microstructure.magnitude.down_body_volume", "Down-Body Volume",
     "Magnitude", "pressure",
     "V × max(-body,0) / range.", "V · max(O-C,0) / (H-L)",
     "Negative-side pressure primitive.", fp.down_body_volume)

_reg("microstructure.magnitude.signed_volume_body", "Signed Volume·Body Ratio",
     "Magnitude", "delta_proxy",
     "sign(body) × V × |body|/range — signed volume weighted by body dominance.",
     "sgn(C-O)·V·|C-O|/(H-L)",
     "OHLCV-derived signed-magnitude series. Not an interpretation.",
     fp.signed_volume_body)


# ══════════════════════════════════════════════════════════════════════
# GEOMETRY — dimensionless bar-shape ratios
# ══════════════════════════════════════════════════════════════════════
_reg("microstructure.geometry.body_over_range",
     "|Body|/Range", "Geometry", "ratio",
     "|body| / range ∈ [0,1].", "|C-O|/(H-L)",
     "Body-to-range ratio — a dimensionless bar-shape measurement.",
     fp.body_over_range)

_reg("microstructure.geometry.signed_body_over_range",
     "Signed Body/Range", "Geometry", "ratio",
     "(close - open) / range ∈ [-1,+1].", "(C-O)/(H-L)",
     "Signed body-fraction — dimensionless.",
     fp.signed_body_over_range)

_reg("microstructure.geometry.body_position_in_range",
     "Body Midpoint Position", "Geometry", "ratio",
     "mid(O,C) location inside [L,H] ∈ [0,1].", "(mid(O,C)-L)/(H-L)",
     "Where the body sits inside the bar — pure geometric ratio.",
     fp.body_position_in_range)

_reg("microstructure.geometry.upper_wick_ratio",
     "Upper Wick / Range", "Geometry", "ratio",
     "upper_wick / range.", "(H-max(O,C))/(H-L)",
     "Upper-wick share of bar range.",
     fp.upper_wick_ratio)

_reg("microstructure.geometry.lower_wick_ratio",
     "Lower Wick / Range", "Geometry", "ratio",
     "lower_wick / range.", "(min(O,C)-L)/(H-L)",
     "Lower-wick share of bar range.",
     fp.lower_wick_ratio)

_reg("microstructure.geometry.wick_difference_ratio",
     "Wick Difference Ratio", "Geometry", "ratio",
     "(upper - lower) / (upper + lower) ∈ [-1,+1].",
     "(U-L_w)/(U+L_w)",
     "Signed wick-imbalance measurement — dimensionless.",
     fp.wick_difference_ratio)


# ══════════════════════════════════════════════════════════════════════
# EXPANSION — aggregated ratios over windows (still direct measurement)
# ══════════════════════════════════════════════════════════════════════
for w in [10, 20, 50]:
    _reg(f"microstructure.expansion.execution_imbalance_{w}",
         f"Execution Imbalance ({w})", "Expansion", "ratio",
         f"Σ signed_body / Σ |body| over {w} bars.",
         "Σ(C-O) / Σ|C-O|",
         "Direct measurement of directional resolution over the window.",
         (lambda w_: (lambda df: fp.execution_imbalance_ratio(df, w_)))(w),
         params={"window": w})
    _reg(f"microstructure.expansion.range_covered_{w}",
         f"Range-Covered Ratio ({w})", "Expansion", "ratio",
         f"|Σ signed_body| / Σ range over {w} bars.",
         "|Σ(C-O)| / Σ(H-L)",
         "Fraction of aggregate bar range that was directionally traversed.",
         (lambda w_: (lambda df: fp.range_covered_ratio(df, w_)))(w),
         params={"window": w})


# ══════════════════════════════════════════════════════════════════════
# RELATIVE — participation ratios
# ══════════════════════════════════════════════════════════════════════
for w in [20, 50]:
    _reg(f"microstructure.relative.participation_{w}",
         f"Participation Ratio ({w})", "Relative", "volume_ratio",
         f"V / MA_{w}(V).", "V / MA(V)",
         "Volume relative to its own moving average.",
         (lambda w_: (lambda df: fp.participation_ratio(df, w_)))(w),
         params={"window": w})


# ══════════════════════════════════════════════════════════════════════
# POSITION — rolling percentile of volume
# ══════════════════════════════════════════════════════════════════════
for w in [50, 100]:
    _reg(f"microstructure.position.volume_pct_rank_{w}",
         f"Volume Percentile Rank ({w})", "Position", "percentile_rank",
         f"Rank(V) among the last {w} bars, expressed as percentile.",
         "rank_pct(V, w)",
         "Where the current volume sits in its recent distribution.",
         (lambda w_: (lambda df: fp.volume_rank_pct(df, w_)))(w),
         params={"window": w})


# ══════════════════════════════════════════════════════════════════════
# STATISTICS — rolling stats of the signed-body-over-range series
# ══════════════════════════════════════════════════════════════════════
for w in [20, 50]:
    _reg(f"microstructure.statistics.body_ratio_mean_{w}",
         f"Mean signed body/range ({w})", "Statistics", "moment",
         f"Rolling mean of signed body/range over {w} bars.",
         "mean_w((C-O)/(H-L))",
         "Central tendency of the signed body-share series.",
         (lambda w_: (lambda df: st.rolling_mean(fp.signed_body_over_range(df), w_)))(w),
         params={"window": w})
    _reg(f"microstructure.statistics.body_ratio_std_{w}",
         f"Std of signed body/range ({w})", "Statistics", "moment",
         f"Rolling std of signed body/range over {w} bars.",
         "std_w((C-O)/(H-L))",
         "Dispersion of the signed body-share series.",
         (lambda w_: (lambda df: st.rolling_std(fp.signed_body_over_range(df), w_)))(w),
         params={"window": w})


# ══════════════════════════════════════════════════════════════════════
# MOTION — changes in the microstructure series
# ══════════════════════════════════════════════════════════════════════
for dt in [1, 5]:
    _reg(f"microstructure.motion.body_ratio_change_{dt}",
         f"Δ(signed body/range) [{dt}]", "Motion", "derivative",
         f"First difference of signed body/range over {dt} bars.",
         "Δ((C-O)/(H-L))",
         "How the signed-body ratio changes across bars.",
         (lambda dt_: (lambda df: mo.velocity(fp.signed_body_over_range(df), dt_)))(dt),
         params={"dt": dt})


# ══════════════════════════════════════════════════════════════════════
# DISTRIBUTION — quantiles of the signed body/range series
# ══════════════════════════════════════════════════════════════════════
for w in [50]:
    for q in [0.25, 0.75]:
        qkey = f"q{int(q*100):02d}"
        _reg(f"microstructure.distribution.body_ratio_{qkey}_{w}",
             f"Body-ratio {qkey} ({w})", "Distribution", "quantile",
             f"Rolling {q:.2f}-quantile of signed body/range over {w} bars.",
             f"Q_{{{q}}}((C-O)/(H-L))",
             "Distributional shape of the signed-body-share series.",
             (lambda w_, q_: (lambda df: fp.signed_body_over_range(df)
                              .rolling(w_, min_periods=w_).quantile(q_)))(w, q),
             params={"window": w, "q": q})


# ══════════════════════════════════════════════════════════════════════
# ENTROPY — Shannon entropy of the wick-difference-ratio distribution
# ══════════════════════════════════════════════════════════════════════
_reg("microstructure.entropy.wick_diff_shannon_50",
     "Shannon Entropy of Wick-Diff Ratio (50)", "Entropy", "shannon",
     "Shannon entropy of the wick-difference-ratio histogram over 50 bars.",
     "H(wick_diff_ratio, 10 bins)",
     "Unpredictability of wick asymmetry over the window.",
     lambda df: st.rolling_entropy(fp.wick_difference_ratio(df), 50, bins=10),
     params={"window": 50, "bins": 10})


# ══════════════════════════════════════════════════════════════════════
# CLUSTERING — autocorrelation of body/range
# ══════════════════════════════════════════════════════════════════════
for lag in [1, 5]:
    _reg(f"microstructure.clustering.body_ratio_acf_lag{lag}_50",
         f"ACF(signed body/range, lag={lag}, w=50)",
         "Clustering", "autocorrelation",
         f"Rolling autocorrelation of signed body/range at lag {lag}.",
         f"corr(x_t, x_{{t-{lag}}}, w=50)",
         "Persistence of directional-body regime.",
         (lambda l_: (lambda df: st.rolling_autocorr(
             fp.signed_body_over_range(df), 50, lag=l_)))(lag),
         params={"lag": lag, "window": 50})


# ══════════════════════════════════════════════════════════════════════
# REGIME — flag features derived purely from direct measurements
# ══════════════════════════════════════════════════════════════════════
_reg("microstructure.regime.marubozu_flag", "Marubozu Flag", "Regime",
     "bar_shape_flag", "1 if |body|/range >= 0.9.", "1[|C-O|/(H-L) ≥ 0.9]",
     "Direct threshold on body/range — measurement, not interpretation.",
     lambda df: (fp.body_over_range(df) >= 0.9).astype(float))

_reg("microstructure.regime.doji_flag", "Doji Flag", "Regime",
     "bar_shape_flag", "1 if |body|/range <= 0.1.", "1[|C-O|/(H-L) ≤ 0.1]",
     "Direct threshold on body/range.",
     lambda df: (fp.body_over_range(df) <= 0.1).astype(float))

for w in [20, 50]:
    _reg(f"microstructure.regime.high_participation_flag_{w}",
         f"High-Participation Flag ({w})", "Regime", "participation_flag",
         f"1 if participation_{w} > 1.5.", "1[V/MA(V) > 1.5]",
         "Threshold on the participation ratio — measurement.",
         (lambda w_: (lambda df: (fp.participation_ratio(df, w_) > 1.5)
                      .astype(float)))(w),
         params={"window": w, "threshold": 1.5})


# ══════════════════════════════════════════════════════════════════════
# HFT-GRADE MICROSTRUCTURE FEATURES (L1)
# Grounded in market microstructure theory. Captures order-flow
# dynamics, execution efficiency, and institutional timing signals
# that are invisible to traditional price/volume indicators.
# ══════════════════════════════════════════════════════════════════════

# Trade Imbalance Velocity — acceleration of buy/sell pressure
for w in [10, 20, 50]:
    _reg(f"microstructure.hft.trade_imbalance_velocity_{w}",
         f"Trade Imbalance Velocity ({w})", "Flow", "ofi_velocity",
         f"Rate-of-change of OFI over {w} bars. Acceleration of informed order flow.",
         "d/dt[(BuyVol-SellVol)/TotalVol]",
         "Positive = buy pressure accelerating. Negative = sell pressure accelerating.",
         (lambda w_: (lambda df: fp.trade_imbalance_velocity(df, w_)))(w),
         params={"window": w})

# Adverse Selection Cost — covariance of signed flow with future return
for w in [20, 50]:
    _reg(f"microstructure.hft.adverse_selection_cost_{w}",
         f"Adverse Selection Cost ({w})", "Flow", "asc_proxy",
         f"Cov(SignedVol_t, Return_{{t+1}}) over {w} bars. Informational toxicity of order flow.",
         "Cov(SV_t, r_{t+1})",
         "High ASC = informed flow consistently predicts next-bar direction.",
         (lambda w_: (lambda df: fp.adverse_selection_cost(df, w_)))(w),
         params={"window": w})

# Volume Clock Deviation — event-time acceleration proxy
for w in [20, 50, 100]:
    _reg(f"microstructure.hft.volume_clock_deviation_{w}",
         f"Volume Clock Deviation ({w})", "Activity", "event_time",
         f"Volume z-score over {w} bars. Deviation from expected activity level.",
         "(V_t - MA_w) / std_w",
         "High = compressed event time (institutional execution). Low = thin market.",
         (lambda w_: (lambda df: fp.volume_clock_deviation(df, w_)))(w),
         params={"window": w})

# Bar Efficiency Ratio — trend vs noise discriminator
for w in [10, 20, 50]:
    _reg(f"microstructure.hft.bar_efficiency_ratio_{w}",
         f"Bar Efficiency Ratio ({w})", "Geometry", "efficiency",
         f"Net displacement / sum(|moves|) over {w} bars. 1=pure trend, 0=pure chop.",
         "|ΔP_w| / Σ|ΔP_1|",
         "Near 1.0 = strong directional trend. Near 0.0 = noise-dominated market.",
         (lambda w_: (lambda df: fp.bar_efficiency_ratio(df, w_)))(w),
         params={"window": w})

# Micro-Price Momentum — volume-weighted cross-timeframe momentum
for w_fast, w_slow in [(5, 20), (10, 50), (20, 100)]:
    _reg(f"microstructure.hft.micro_price_momentum_{w_fast}_{w_slow}",
         f"Micro-Price Momentum ({w_fast}/{w_slow})", "Flow", "vwap_momentum",
         f"(VWAP_{w_fast} - VWAP_{w_slow}) / sigma_{w_slow}. Volume-weighted price momentum.",
         "(VWAP_f - VWAP_s) / σ",
         "Positive = fast volume-weighted price above slow. Institutional momentum signal.",
         (lambda f_, s_: (lambda df: fp.micro_price_momentum(df, f_, s_)))(w_fast, w_slow),
         params={"w_fast": w_fast, "w_slow": w_slow})


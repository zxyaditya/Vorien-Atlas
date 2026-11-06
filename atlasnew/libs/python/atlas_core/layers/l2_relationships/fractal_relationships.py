"""Fractal Relationships — Layer 2 (Book 1 Ch. 5, named exemplar).

Full mathematical specification:  /app/docs/L2_SPECS/FRACTAL_RELATIONSHIPS.md
Decision-Engine review           :  /app/docs/L2_SPECS/FRACTAL_RELATIONSHIPS_DE_REVIEW.md

Purpose
-------
Measure whether the same market phenomenon exhibits **self-similar
behaviour across multiple observation scales** — whether the
statistical laws describing the market at short scales continue to
describe it at long scales.

Distinguished from the two other Session-7 L2 modules by the
**Three-Scale Rule**: every feature is a statistical or geometric
property of a scaling relationship computed from ≥ 3 distinct scales.
Any two-scale ratio belongs in `trend_relationships`; any temporal
derivative belongs in `momentum_of_trend`.

Inputs are consumed EXCLUSIVELY via `_l1_bridge.l1_series` (Book 1
Invariant 6.4). Zero direct OHLCV column access. Enforced by pytest.

Registered features (21 total, 5 Perspectives)
---------------------------------------------
Geometry   (5): variance-scaling exponent + R², range-scaling exponent
                + R² + deviation-from-Brownian.
Statistics (5): generalised Hurst H(1), H(2), H(3);
                multifractal spread H(1) − H(3);
                wavelet-variance scaling exponent (Haar).
Distribution (3): variance-ratio max-deviation, scale-std, signed extreme.
Regime     (5): Hurst cross-window std/range (32/64/128);
                Higuchi FD cross-window std (25/50/100);
                self-similarity score; self-similarity flag.
Position   (3): rolling percentile ranks (60 bars).

L1 prerequisites shipped in the same commit (see spec §4.2):
  price.geometry.hurst_32, price.geometry.higuchi_fd_25
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l2_relationships._l1_bridge import l1_series

MODULE = "fractal_relationships"
EPS = 1e-12

# ── Canonical scale sets (Three-Scale Rule: every set has |S| ≥ 3) ────────
S_VAR    = (2, 4, 8, 16, 32, 64)          # variance-scaling
S_STRUCT = (2, 4, 8, 16, 32)              # structure-function moments
S_VR     = (2, 4, 8, 16)                  # variance-ratio envelope
S_HURST  = (32, 64, 128)                  # multi-window Hurst
S_FD     = (25, 50, 100)                  # multi-window Higuchi FD
S_RANGE  = (5, 10, 20, 40, 80)            # range-scaling
S_WAVE   = (1, 2, 3, 4)                   # Haar wavelet detail levels

# Rolling-window sizes for scaling-law fits.
W_FIT     = 128   # variance-scaling, structure-function, VR, range-scaling
W_FIT_WAV = 256   # wavelet needs enough samples for level 4

# Rank window (Position features).
W_RANK = 60


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         inputs, scales, params=None, complexity="O(n·W·|S|)"):
    """Book-1-compliant registration helper.

    ``scales`` is the explicit list of observation scales this feature
    uses; asserted ≥ 3 by pytest (Three-Scale Rule, spec §2).
    """
    assert len(scales) >= 3, (
        f"Three-Scale Rule violation: feature {id_} lists {len(scales)} scales; "
        f"minimum is 3. See docs/L2_SPECS/FRACTAL_RELATIONSHIPS.md §2."
    )
    p = dict(params or {})
    p["scales"] = list(scales)
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=2, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=p, complexity=complexity, fn=fn,
    ))


# ══════════════════════════════════════════════════════════════════════════
# Mathematical kernels — pure functions on log-return / close arrays.
# ══════════════════════════════════════════════════════════════════════════

def _log_return_1(df) -> pd.Series:
    """Bar-to-bar log return via the Registry (never raw OHLCV columns)."""
    return l1_series(df, "price.motion.log_return_1")


def _close(df) -> pd.Series:
    return l1_series(df, "price.magnitude.close")


def _high(df) -> pd.Series:
    return l1_series(df, "price.magnitude.high")


def _low(df) -> pd.Series:
    return l1_series(df, "price.magnitude.low")


def _tau_return(r1: np.ndarray, tau: int) -> np.ndarray:
    """τ-scale returns from bar-to-bar returns: r_τ(t) = Σ r_1(t-τ+1..t)."""
    if tau <= 1:
        return r1
    csum = np.cumsum(np.concatenate([[0.0], r1]))
    return csum[tau:] - csum[:-tau]


def _log_log_slope(y_log: np.ndarray, x_log: np.ndarray):
    """Return (slope, r_squared) of OLS fit y = a + b·x in log space."""
    n = len(x_log)
    if n < 3:
        return np.nan, np.nan
    mask = np.isfinite(y_log) & np.isfinite(x_log)
    if mask.sum() < 3:
        return np.nan, np.nan
    x = x_log[mask]; y = y_log[mask]
    x_mean = x.mean(); y_mean = y.mean()
    sxx = float(((x - x_mean) ** 2).sum())
    if sxx <= EPS:
        return np.nan, np.nan
    sxy = float(((x - x_mean) * (y - y_mean)).sum())
    syy = float(((y - y_mean) ** 2).sum())
    slope = sxy / sxx
    r2 = (sxy ** 2) / (sxx * syy) if syy > EPS else np.nan
    return float(slope), float(r2)


# ── Variance-scaling exponent (Family A) ─────────────────────────────────

def _variance_scaling_kernel(r1_window: np.ndarray):
    """Return (α, R²) from log Var[r_τ] vs log τ over S_VAR."""
    varlog, taulog = [], []
    for tau in S_VAR:
        if len(r1_window) < 4 * tau:
            continue
        r_tau = _tau_return(r1_window, tau)
        if len(r_tau) < 8:
            continue
        v = np.var(r_tau, ddof=1)
        if v > EPS:
            varlog.append(np.log(v))
            taulog.append(np.log(tau))
    if len(taulog) < 3:
        return np.nan, np.nan
    return _log_log_slope(np.array(varlog), np.array(taulog))


def _rolling_variance_scaling(df) -> tuple[pd.Series, pd.Series]:
    """Rolling (α, R²) of the variance-scaling law."""
    r1 = _log_return_1(df).values
    n = len(r1)
    alpha = np.full(n, np.nan)
    r2    = np.full(n, np.nan)
    for i in range(W_FIT, n + 1):
        window = r1[i - W_FIT:i]
        if np.isnan(window).any():
            continue
        a, q = _variance_scaling_kernel(window)
        alpha[i - 1] = a; r2[i - 1] = q
    idx = df.index
    return pd.Series(alpha, index=idx), pd.Series(r2, index=idx)


# ── Range-scaling exponent (Family F) ─────────────────────────────────────

def _range_scaling_kernel(high_win: np.ndarray, low_win: np.ndarray):
    """Slope β of log ⟨range(τ)⟩ vs log τ where range(τ) = max(high, τ) − min(low, τ)."""
    rlog, taulog = [], []
    n = len(high_win)
    for tau in S_RANGE:
        if n < 4 * tau:
            continue
        # non-overlapping τ-window range means
        m = n // tau
        if m < 4:
            continue
        h_ranges = []
        for k in range(m):
            a = k * tau; b = (k + 1) * tau
            h_ranges.append(high_win[a:b].max() - low_win[a:b].min())
        mean_range = float(np.mean(h_ranges))
        if mean_range > EPS:
            rlog.append(np.log(mean_range))
            taulog.append(np.log(tau))
    if len(taulog) < 3:
        return np.nan, np.nan
    return _log_log_slope(np.array(rlog), np.array(taulog))


def _rolling_range_scaling(df) -> tuple[pd.Series, pd.Series]:
    hi = _high(df).values; lo = _low(df).values
    n = len(hi)
    beta = np.full(n, np.nan)
    r2   = np.full(n, np.nan)
    for i in range(W_FIT, n + 1):
        b, q = _range_scaling_kernel(hi[i - W_FIT:i], lo[i - W_FIT:i])
        beta[i - 1] = b; r2[i - 1] = q
    idx = df.index
    return pd.Series(beta, index=idx), pd.Series(r2, index=idx)


# ── Structure-function generalised Hurst (Family B) ───────────────────────

def _generalized_hurst_kernel(r1_window: np.ndarray, q: float):
    """H(q) = slope of log ⟨|r_τ|^q⟩ vs log τ over S_STRUCT."""
    mlog, taulog = [], []
    for tau in S_STRUCT:
        if len(r1_window) < 4 * tau:
            continue
        r_tau = _tau_return(r1_window, tau)
        if len(r_tau) < 8:
            continue
        m = float(np.mean(np.abs(r_tau) ** q))
        if m > EPS:
            mlog.append(np.log(m))
            taulog.append(np.log(tau))
    if len(taulog) < 3:
        return np.nan
    slope, _ = _log_log_slope(np.array(mlog), np.array(taulog))
    # H(q) is the slope divided by q (structure-function convention).
    if q <= EPS:
        return np.nan
    return slope / q if np.isfinite(slope) else np.nan


def _rolling_gen_hurst(df, q: int) -> pd.Series:
    r1 = _log_return_1(df).values
    n = len(r1)
    out = np.full(n, np.nan)
    for i in range(W_FIT, n + 1):
        w = r1[i - W_FIT:i]
        if np.isnan(w).any():
            continue
        out[i - 1] = _generalized_hurst_kernel(w, float(q))
    return pd.Series(out, index=df.index)


# ── Variance-Ratio envelope (Family C) ────────────────────────────────────

def _variance_ratio_series(df) -> pd.DataFrame:
    """Compute VR(τ) for τ ∈ S_VR on the rolling window W_FIT.
    Returns a DataFrame indexed like df with one column per τ."""
    r1 = _log_return_1(df).values
    n = len(r1)
    cols = {tau: np.full(n, np.nan) for tau in S_VR}
    for i in range(W_FIT, n + 1):
        w = r1[i - W_FIT:i]
        if np.isnan(w).any():
            continue
        var_1 = np.var(w, ddof=1)
        if var_1 <= EPS:
            continue
        for tau in S_VR:
            r_tau = _tau_return(w, tau)
            if len(r_tau) < 4:
                continue
            var_t = np.var(r_tau, ddof=1)
            cols[tau][i - 1] = var_t / (tau * var_1)
    return pd.DataFrame({str(tau): pd.Series(cols[tau], index=df.index)
                         for tau in S_VR})


# ── Haar wavelet variance scaling (Family G) ──────────────────────────────

def _haar_detail_variances(x: np.ndarray, levels: int) -> np.ndarray:
    """Non-decimated (à trous) Haar wavelet detail variances at levels 1..levels."""
    out = np.full(levels, np.nan)
    y = x.copy()
    n = len(y)
    for j in range(1, levels + 1):
        step = 2 ** (j - 1)
        if step * 2 >= n:
            break
        # Haar detail at level j
        left = y[:-step]
        right = y[step:]
        d = right - left
        if len(d) > 3:
            v = float(np.var(d, ddof=1))
            if v > EPS:
                out[j - 1] = v
    return out


def _rolling_wavelet_scaling(df) -> pd.Series:
    r1 = _log_return_1(df).values
    n = len(r1)
    slope = np.full(n, np.nan)
    levels = max(S_WAVE)
    for i in range(W_FIT_WAV, n + 1):
        w = r1[i - W_FIT_WAV:i]
        if np.isnan(w).any():
            continue
        v = _haar_detail_variances(w, levels)
        y = np.log(v)
        x = np.log(2.0 ** np.arange(1, levels + 1))
        mask = np.isfinite(y)
        if mask.sum() < 3:
            continue
        s, _ = _log_log_slope(y[mask], x[mask])
        slope[i - 1] = s
    return pd.Series(slope, index=df.index)


# ── Cross-window Hurst / FD consistency (Family D, E) ─────────────────────

def _cross_window_std(df, fids: tuple[str, ...]) -> pd.Series:
    """Rolling std of the values of ≥3 L1 features at the current bar."""
    sers = [l1_series(df, fid) for fid in fids]
    S = pd.concat(sers, axis=1)
    return S.std(axis=1, ddof=1)


def _cross_window_range(df, fids: tuple[str, ...]) -> pd.Series:
    sers = [l1_series(df, fid) for fid in fids]
    S = pd.concat(sers, axis=1)
    return S.max(axis=1) - S.min(axis=1)


# ── Composite self-similarity score & flag (Family H) ─────────────────────

def _clip01(s: pd.Series) -> pd.Series:
    return s.clip(0.0, 1.0)


_FRACTAL_CACHE = {}

def _self_similarity_components(df):
    """Compute the five sub-scores of the composite. Each sub-score is a
    value in [0, 1] that equals 1 for a strictly self-similar Brownian
    input (see spec §5.6). Returns a dict of pd.Series."""
    cache_key = id(df)
    if cache_key in _FRACTAL_CACHE:
        return _FRACTAL_CACHE[cache_key]

    alpha_var, r2_var = _rolling_variance_scaling(df)
    beta_rng,  r2_rng = _rolling_range_scaling(df)
    hurst_std = _cross_window_std(
        df, ("price.geometry.hurst_32", "price.geometry.hurst_64",
             "price.geometry.hurst_128"))
    h1 = _rolling_gen_hurst(df, q=1)
    h3 = _rolling_gen_hurst(df, q=3)
    mf_spread = (h1 - h3).abs()
    # Sub-scores: each mapped so BM (H=0.5) yields exactly 1.0.
    sc_var_r2   = _clip01(r2_var)                          # BM ≈ 1
    sc_rng_r2   = _clip01(r2_rng)                          # BM ≈ 1
    sc_rng_beta = _clip01(1.0 - (beta_rng - 0.5).abs())    # BM: β=0.5 → 1
    sc_hurst    = _clip01(1.0 - hurst_std / 0.3)           # BM: std=0 → 1
    sc_mf       = _clip01(1.0 - mf_spread / 0.3)           # BM: spread=0 → 1
    res = {
        "alpha_var": alpha_var, "beta_rng": beta_rng,
        "hurst_std": hurst_std, "mf_spread": mf_spread,
        "sc_var_r2": sc_var_r2, "sc_rng_r2": sc_rng_r2,
        "sc_rng_beta": sc_rng_beta, "sc_hurst": sc_hurst, "sc_mf": sc_mf,
    }
    if len(_FRACTAL_CACHE) > 64:
        _FRACTAL_CACHE.pop(next(iter(_FRACTAL_CACHE)))
    _FRACTAL_CACHE[cache_key] = res
    return res


def _self_similarity_score(df) -> pd.Series:
    c = _self_similarity_components(df)
    subs = pd.concat([c["sc_var_r2"], c["sc_rng_r2"], c["sc_rng_beta"],
                      c["sc_hurst"], c["sc_mf"]], axis=1)
    # Geometric mean of positives; NaN if any is missing.
    log_mean = np.log(subs.clip(lower=EPS)).mean(axis=1)
    return _clip01(np.exp(log_mean))


def _self_similarity_flag(df) -> pd.Series:
    c = _self_similarity_components(df)
    score = _self_similarity_score(df)
    # Every sub-input must agree on Brownian-side of its canonical value.
    # We measure "same-side of BM" via the five sub-scores each ≥ 0.5
    # (i.e. no sub-score is catastrophically low).
    subs = pd.concat([c["sc_var_r2"], c["sc_rng_r2"], c["sc_rng_beta"],
                      c["sc_hurst"], c["sc_mf"]], axis=1)
    all_agree = (subs >= 0.5).all(axis=1).astype(int)
    flag = ((score > 0.75) & (all_agree > 0)).astype(int)
    return flag


# ══════════════════════════════════════════════════════════════════════════
# Feature registrations
# ══════════════════════════════════════════════════════════════════════════

# ── 5.1 Geometry (5) ──────────────────────────────────────────────────────

def _var_scaling_alpha(df) -> pd.Series:
    return _rolling_variance_scaling(df)[0]


def _var_scaling_r2(df) -> pd.Series:
    return _rolling_variance_scaling(df)[1]


_reg("fractal_relationships.geometry.variance_scaling_exponent_2_64",
     "Variance-Scaling Exponent (τ∈{2..64})", "Geometry", "variance_scaling",
     f"OLS slope of log Var[r_τ] vs log τ across τ ∈ {list(S_VAR)}. "
     f"α=1 for i.i.d. Gaussian returns (Brownian).",
     "α = slope(log Var[r_τ], log τ)",
     "α>1 super-diffusive; α<1 sub-diffusive; α≈1 Brownian.",
     _var_scaling_alpha,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_VAR,
     complexity="O(n·W·|S|)")

_reg("fractal_relationships.geometry.variance_scaling_r2_2_64",
     "Variance-Scaling Fit R² (τ∈{2..64})", "Geometry", "variance_scaling",
     "Goodness of fit of the variance-scaling law across ≥3 scales.",
     "R² of log Var[r_τ] vs log τ",
     "1 = perfect power law; <1 = scale-dependent departure.",
     _var_scaling_r2,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_VAR)


def _rng_scaling_beta(df) -> pd.Series:
    return _rolling_range_scaling(df)[0]


def _rng_scaling_r2(df) -> pd.Series:
    return _rolling_range_scaling(df)[1]


def _rng_scaling_dev(df) -> pd.Series:
    return (_rng_scaling_beta(df) - 0.5).abs()


_reg("fractal_relationships.geometry.range_scaling_exponent_5_80",
     "Range-Scaling Exponent (τ∈{5..80})", "Geometry", "range_scaling",
     f"OLS slope of log ⟨range(τ)⟩ vs log τ across τ ∈ {list(S_RANGE)}.",
     "β = slope(log Range(τ), log τ)",
     "β=0.5 Brownian; β>0.5 persistent range; β<0.5 anti-persistent.",
     _rng_scaling_beta,
     inputs=["L1:price.magnitude.high", "L1:price.magnitude.low"],
     scales=S_RANGE)

_reg("fractal_relationships.geometry.range_scaling_r2_5_80",
     "Range-Scaling Fit R² (τ∈{5..80})", "Geometry", "range_scaling",
     "Goodness of fit of the range-scaling law across ≥3 scales.",
     "R² of log Range(τ) vs log τ",
     "1 = perfect power law; <1 = scale-dependent departure.",
     _rng_scaling_r2,
     inputs=["L1:price.magnitude.high", "L1:price.magnitude.low"],
     scales=S_RANGE)

_reg("fractal_relationships.geometry.range_scaling_deviation_from_brownian_5_80",
     "|Range-Scaling β − 0.5|", "Geometry", "range_scaling",
     "Magnitude of departure from Brownian roughness in the range-scaling law.",
     "|β − 0.5|",
     "0 = Brownian; positive = non-Brownian roughness at some scale.",
     _rng_scaling_dev,
     inputs=["L1:price.magnitude.high", "L1:price.magnitude.low"],
     scales=S_RANGE)


# ── 5.2 Statistics — generalised Hurst + wavelet (5) ──────────────────────

def _gen_h1(df): return _rolling_gen_hurst(df, q=1)
def _gen_h2(df): return _rolling_gen_hurst(df, q=2)
def _gen_h3(df): return _rolling_gen_hurst(df, q=3)


_reg("fractal_relationships.statistics.generalized_hurst_h1_2_32",
     "Generalised Hurst H(q=1) — τ∈{2..32}", "Statistics", "structure_function",
     "First-order structure-function generalised Hurst.",
     "slope(log ⟨|r_τ|¹⟩, log τ) / 1",
     "H(1)≈0.5 monofractal Brownian; >0.5 persistent; <0.5 anti-persistent.",
     _gen_h1,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_STRUCT)

_reg("fractal_relationships.statistics.generalized_hurst_h2_2_32",
     "Generalised Hurst H(q=2) — τ∈{2..32}", "Statistics", "structure_function",
     "Second-order generalised Hurst (canonical Hurst analogue).",
     "slope(log ⟨|r_τ|²⟩, log τ) / 2",
     "H(2)≈0.5 monofractal Brownian.",
     _gen_h2,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_STRUCT)

_reg("fractal_relationships.statistics.generalized_hurst_h3_2_32",
     "Generalised Hurst H(q=3) — τ∈{2..32}", "Statistics", "structure_function",
     "Third-order generalised Hurst.",
     "slope(log ⟨|r_τ|³⟩, log τ) / 3",
     "H(3)≈0.5 monofractal Brownian.",
     _gen_h3,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_STRUCT)


def _mf_spread(df):
    return _gen_h1(df) - _gen_h3(df)


_reg("fractal_relationships.statistics.multifractal_spread_h1_minus_h3_2_32",
     "Multifractal Spread H(1) − H(3) — τ∈{2..32}",
     "Statistics", "multifractality",
     "Difference between first- and third-order generalised Hurst. "
     "Zero for monofractals; positive under multifractal scaling.",
     "H(1) − H(3)",
     "0 = monofractal; ≠0 = scale-dependent moment-order asymmetry.",
     _mf_spread,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_STRUCT)

_reg("fractal_relationships.statistics.wavelet_variance_scaling_exponent_1_4",
     "Wavelet-Variance Scaling Exponent (Haar levels 1..4)",
     "Statistics", "wavelet_scaling",
     f"Slope of log Var[Haar-detail_j(r_1)] vs log(2^j) across "
     f"levels j ∈ {list(S_WAVE)}. For i.i.d. returns the slope ≈ 0.",
     "slope(log Var[d_j], log 2^j)",
     "0 = white-noise returns; >0 persistent autocorrelation; <0 anti-persistent.",
     _rolling_wavelet_scaling,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_WAVE,
     complexity="O(n·W)")


# ── 5.3 Distribution — variance-ratio envelope (3) ────────────────────────

def _vr_max_dev(df) -> pd.Series:
    vr = _variance_ratio_series(df)
    return (vr - 1.0).abs().max(axis=1)


def _vr_scale_std(df) -> pd.Series:
    vr = _variance_ratio_series(df)
    return vr.std(axis=1, ddof=1)


def _vr_signed_extreme(df) -> pd.Series:
    """The signed VR value at the τ where |VR−1| is largest."""
    vr = _variance_ratio_series(df)
    dev = (vr - 1.0).abs()
    out = pd.Series(np.nan, index=vr.index, dtype=float)
    valid = dev.notna().any(axis=1)
    if not valid.any():
        return out
    
    # For each row pick the column of the max |VR-1|.
    idxmax = dev.loc[valid].idxmax(axis=1)
    for c in vr.columns:
        mask = (idxmax == c)
        out.loc[mask[mask].index] = vr.loc[mask[mask].index, c]
    return out


_reg("fractal_relationships.distribution.variance_ratio_max_deviation_from_unity_2_16",
     "VR Max Deviation from Unity — τ∈{2..16}", "Distribution", "variance_ratio",
     f"Envelope of the Lo–MacKinlay variance-ratio departure from 1 across "
     f"τ ∈ {list(S_VR)}.",
     "max_τ |Var[r_τ]/(τ·Var[r_1]) − 1|",
     "0 = random-walk consistent at every scale; >0 = scale-dependent departure.",
     _vr_max_dev,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_VR)

_reg("fractal_relationships.distribution.variance_ratio_scale_std_2_16",
     "VR Scale-std — τ∈{2..16}", "Distribution", "variance_ratio",
     "Standard deviation of VR(τ) across τ — measures scale-heterogeneity of VR.",
     "std_τ(VR(τ))",
     "0 = same VR at every scale; >0 = VR value depends on scale.",
     _vr_scale_std,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_VR)

_reg("fractal_relationships.distribution.variance_ratio_signed_extreme_2_16",
     "VR Signed Extreme — τ∈{2..16}", "Distribution", "variance_ratio",
     "Signed VR value at the τ achieving the largest |VR−1|.",
     "VR(τ*) where τ* = argmax_τ |VR(τ)−1|",
     ">1 super-diffusive across scales; <1 sub-diffusive; ≈1 random-walk.",
     _vr_signed_extreme,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_VR)


# ── 5.4 Regime — cross-window consistency + self-similarity (5) ──────────

_HURST_FIDS = ("price.geometry.hurst_32", "price.geometry.hurst_64",
               "price.geometry.hurst_128")
_FD_FIDS    = ("price.geometry.higuchi_fd_25", "price.geometry.higuchi_fd_50",
               "price.geometry.higuchi_fd_100")


def _hurst_cross_std(df):
    return _cross_window_std(df, _HURST_FIDS)


def _hurst_cross_range(df):
    return _cross_window_range(df, _HURST_FIDS)


def _fd_cross_std(df):
    return _cross_window_std(df, _FD_FIDS)


_reg("fractal_relationships.regime.hurst_cross_window_std_32_64_128",
     "Hurst Cross-Window σ (w∈{32,64,128})", "Regime", "cross_window_stability",
     f"Standard deviation of R/S Hurst across L1 windows {list(S_HURST)}.",
     "std({H_32, H_64, H_128})",
     "0 = scale-invariant Hurst; >0 = Hurst drifts with the window.",
     _hurst_cross_std,
     inputs=[f"L1:{fid}" for fid in _HURST_FIDS],
     scales=S_HURST, complexity="O(n)")

_reg("fractal_relationships.regime.hurst_cross_window_range_32_64_128",
     "Hurst Cross-Window Range (w∈{32,64,128})",
     "Regime", "cross_window_stability",
     f"Range (max − min) of R/S Hurst across L1 windows {list(S_HURST)}.",
     "max − min of {H_32, H_64, H_128}",
     "Envelope width of the Hurst estimate across scales.",
     _hurst_cross_range,
     inputs=[f"L1:{fid}" for fid in _HURST_FIDS],
     scales=S_HURST, complexity="O(n)")

_reg("fractal_relationships.regime.higuchi_fd_cross_window_std_25_50_100",
     "Higuchi FD Cross-Window σ (w∈{25,50,100})",
     "Regime", "cross_window_stability",
     f"Standard deviation of Higuchi FD across L1 windows {list(S_FD)}.",
     "std({FD_25, FD_50, FD_100})",
     "0 = scale-invariant fractal dimension; >0 = FD depends on window.",
     _fd_cross_std,
     inputs=[f"L1:{fid}" for fid in _FD_FIDS],
     scales=S_FD, complexity="O(n)")

_reg("fractal_relationships.regime.self_similarity_score",
     "Self-Similarity Score (composite)", "Regime", "self_similarity",
     "Geometric mean of five sub-scores each normalised so a strictly "
     "self-similar Brownian input yields sub-score = 1. Aggregates ≥3 "
     "scale-invariance measurements (variance-scaling R², range-scaling R², "
     "|β−0.5|, Hurst cross-window σ, |H(1)−H(3)|).",
     "prod_i(sub_i)^(1/5), sub_i ∈ [0,1]",
     "1 = internally consistent scaling laws; 0 = scale-inhomogeneous market.",
     _self_similarity_score,
     inputs=["L1:price.motion.log_return_1",
             "L1:price.magnitude.high", "L1:price.magnitude.low"]
            + [f"L1:{fid}" for fid in _HURST_FIDS],
     scales=tuple(sorted(set(S_VAR + S_RANGE + S_STRUCT + S_HURST))),
     complexity="O(n·W·|S|)")

_reg("fractal_relationships.regime.self_similarity_flag",
     "Self-Similarity Flag (binary)", "Regime", "self_similarity",
     "1 iff self_similarity_score > 0.75 AND every sub-score ≥ 0.5.",
     "1[score > 0.75 ∧ all sub-scores ≥ 0.5]",
     "1 = every scale-invariance sub-measurement agrees; 0 otherwise.",
     _self_similarity_flag,
     inputs=["L1:price.motion.log_return_1",
             "L1:price.magnitude.high", "L1:price.magnitude.low"]
            + [f"L1:{fid}" for fid in _HURST_FIDS],
     scales=tuple(sorted(set(S_VAR + S_RANGE + S_STRUCT + S_HURST))),
     complexity="O(n·W·|S|)")


# ── 5.5 Position — rolling percentile ranks (3) ───────────────────────────

def _rank60_var_alpha(df):
    return _var_scaling_alpha(df).rolling(W_RANK,
        min_periods=max(2, W_RANK // 2)).rank(pct=True)


def _rank60_mf_spread(df):
    return _mf_spread(df).rolling(W_RANK,
        min_periods=max(2, W_RANK // 2)).rank(pct=True)


def _rank60_ss_score(df):
    return _self_similarity_score(df).rolling(W_RANK,
        min_periods=max(2, W_RANK // 2)).rank(pct=True)


_reg("fractal_relationships.position.variance_scaling_exponent_rank_60",
     "Variance-Scaling α — 60-bar Rank", "Position", "rank_of_scaling",
     "Rolling percentile rank of variance-scaling exponent over 60 bars.",
     "rank_pct(α, 60)",
     "0 = current α among the smallest recent; 1 = among the largest.",
     _rank60_var_alpha,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_VAR)

_reg("fractal_relationships.position.multifractal_spread_rank_60",
     "Multifractal Spread — 60-bar Rank", "Position", "rank_of_scaling",
     "Rolling percentile rank of the H(1)−H(3) multifractal spread.",
     "rank_pct(H(1)−H(3), 60)",
     "0 = spread among the smallest recent; 1 = among the largest.",
     _rank60_mf_spread,
     inputs=["L1:price.motion.log_return_1"],
     scales=S_STRUCT)

_reg("fractal_relationships.position.self_similarity_score_rank_60",
     "Self-Similarity Score — 60-bar Rank", "Position", "rank_of_scaling",
     "Rolling percentile rank of the composite self-similarity score.",
     "rank_pct(score, 60)",
     "0 = market is unusually scale-heterogeneous vs recent; 1 = unusually self-similar.",
     _rank60_ss_score,
     inputs=["L1:price.motion.log_return_1",
             "L1:price.magnitude.high", "L1:price.magnitude.low"]
            + [f"L1:{fid}" for fid in _HURST_FIDS],
     scales=tuple(sorted(set(S_VAR + S_RANGE + S_STRUCT + S_HURST))))

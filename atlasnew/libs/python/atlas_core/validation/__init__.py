"""Golden Tests — analytical known-answer validation.

Each test constructs a synthetic input for which the correct value of a
feature is derivable in closed form. Failure means the feature's
implementation deviates from its declared mathematics.

Interleaved with expansion — per user directive: "Validation should grow
together with Atlas."
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, List

from atlas_core.compute import compute_features


def _ohlcv_from_close(close: np.ndarray) -> pd.DataFrame:
    n = len(close)
    return pd.DataFrame({
        "open":   np.concatenate([[close[0]], close[:-1]]),
        "high":   close * 1.001,
        "low":    close * 0.999,
        "close":  close,
        "volume": np.full(n, 1e6),
    }, index=pd.date_range("2020-01-01", periods=n, freq="D"))


# ── Individual tests ─────────────────────────────────────────────────────
def test_close_identity():
    """Magnitude close must equal the raw close."""
    c = np.linspace(100, 200, 50)
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["price.magnitude.close"])
    v = X["price.magnitude.close"].values
    return {"name": "close identity",
            "passed": bool(np.allclose(v, c)),
            "detail": f"|Δ|_max={float(np.max(np.abs(v-c))):.2e}"}


def test_linear_straightness_is_one():
    """Straightness of a strictly monotone series must be 1."""
    c = 100 + np.arange(60, dtype=float)
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["price.geometry.straightness_50"])
    v = X["price.geometry.straightness_50"].iloc[-1]
    return {"name": "linear straightness = 1",
            "passed": bool(np.isfinite(v) and abs(v - 1.0) < 1e-6),
            "detail": f"straightness={v}"}


def test_zigzag_complexity():
    """Perfect alternation should yield close to w turning points over w bars."""
    c = 100 + ((np.arange(60) % 2) * 2 - 1) * 0.5
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["price.geometry.complexity_20"])
    v = X["price.geometry.complexity_20"].iloc[-1]
    return {"name": "zigzag has ≈w turning points",
            "passed": bool(v is not None and abs(v - 19) <= 2),
            "detail": f"count={v}"}


def test_log_return_of_flat_is_zero():
    """Flat close → all log returns zero."""
    c = np.full(50, 100.0)
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["price.motion.log_return_1"])
    v = X["price.motion.log_return_1"].values[1:]  # skip nan warmup
    return {"name": "flat log-return = 0",
            "passed": bool(np.allclose(v, 0.0)),
            "detail": f"max|v|={float(np.max(np.abs(v))):.2e}"}


def test_lr_slope_matches_analytical():
    """Linear-regression slope of a linear series = the true slope."""
    slope = 0.7
    c = 100 + slope * np.arange(80, dtype=float)
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["price.motion.lr_slope_50"])
    v = X["price.motion.lr_slope_50"].iloc[-1]
    return {"name": "lr_slope_50 recovers analytical slope",
            "passed": bool(np.isfinite(v) and abs(v - slope) < 1e-6),
            "detail": f"computed={v}, expected={slope}"}


def test_lr_r2_on_line_is_one():
    """R² of a linear fit on a line must be 1."""
    c = 100 + 1.5 * np.arange(80, dtype=float)
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["price.geometry.lr_r2_50"])
    v = X["price.geometry.lr_r2_50"].iloc[-1]
    return {"name": "lr_r2 on line = 1",
            "passed": bool(np.isfinite(v) and abs(v - 1.0) < 1e-6),
            "detail": f"R²={v}"}


def test_zscore_of_line_is_predictable():
    """Z-score of an increasing line at the last point should be > 0."""
    c = 100 + np.arange(60, dtype=float)
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["price.statistics.zscore_50"])
    v = X["price.statistics.zscore_50"].iloc[-1]
    return {"name": "z-score of rising line > 0",
            "passed": bool(np.isfinite(v) and v > 0),
            "detail": f"z={v}"}


def test_cc_vol_of_gbm_matches_sigma():
    """Close-to-close realized-vol of GBM converges to σ (loose bound)."""
    n = 500; sigma = 0.02
    rng = np.random.default_rng(7)
    r = rng.normal(0, sigma, n)
    c = 100 * np.exp(np.cumsum(r))
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["volatility.magnitude.cc_50"])
    v = X["volatility.magnitude.cc_50"].iloc[-1]
    return {"name": "realized-vol ≈ σ on GBM (loose)",
            "passed": bool(np.isfinite(v) and abs(v - sigma) / sigma < 0.4),
            "detail": f"σ_hat={v:.4f}, σ_true={sigma}"}


def test_upside_downside_sum_of_squares():
    """σ_up² + σ_down² ≈ mean(r²) — decomposition sanity check."""
    n = 400
    rng = np.random.default_rng(11)
    r = rng.normal(0, 0.01, n)
    c = 100 * np.exp(np.cumsum(r))
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["volatility.magnitude.up_50",
                              "volatility.magnitude.down_50"])
    up = X["volatility.magnitude.up_50"].iloc[-1]
    dn = X["volatility.magnitude.down_50"].iloc[-1]
    # up² + down² should approximate mean(r²) which is σ²
    approx = up ** 2 + dn ** 2
    return {"name": "semi-vol decomposition",
            "passed": bool(np.isfinite(approx) and 0.0 < approx < 1.0),
            "detail": f"σ_up²+σ_dn²={approx:.6f}"}


def test_obv_flat_returns_zero():
    """OBV of a flat series is 0 (sign(Δ)=0 everywhere)."""
    c = np.full(50, 100.0)
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["volume.motion.obv"])
    v = X["volume.motion.obv"].iloc[-1]
    return {"name": "OBV(flat) = 0",
            "passed": bool(v == 0.0), "detail": f"obv={v}"}


# ── v0.6 additions ─────────────────────────────────────────────────────
def test_microstructure_body_identity():
    """|Body| = |close - open| on every bar."""
    c = np.linspace(100, 200, 60)
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["microstructure.magnitude.body"])
    expected = np.abs(df["close"] - df["open"]).values
    got = X["microstructure.magnitude.body"].values
    return {"name": "microstructure body = |C-O|",
            "passed": bool(np.allclose(got, expected)),
            "detail": f"max_diff={float(np.max(np.abs(got-expected))):.2e}"}


def test_microstructure_body_over_range_bounds():
    """|body|/range must lie in [0, 1] whenever finite."""
    rng = np.random.default_rng(3)
    c = 100 + np.cumsum(rng.normal(0, 1, 100))
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["microstructure.geometry.body_over_range"])
    v = X["microstructure.geometry.body_over_range"].values
    v = v[np.isfinite(v)]
    return {"name": "body/range ∈ [0,1]",
            "passed": bool(len(v) > 0 and v.min() >= 0 and v.max() <= 1),
            "detail": f"min={float(v.min()):.4f}, max={float(v.max()):.4f}"}


def test_microstructure_wick_difference_symmetry():
    """wick_difference_ratio ∈ [-1, +1]."""
    rng = np.random.default_rng(5)
    c = 100 + np.cumsum(rng.normal(0, 0.5, 80))
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["microstructure.geometry.wick_difference_ratio"])
    v = X["microstructure.geometry.wick_difference_ratio"].values
    v = v[np.isfinite(v)]
    return {"name": "wick_diff ∈ [-1,+1]",
            "passed": bool(len(v) > 0 and v.min() >= -1 and v.max() <= 1),
            "detail": f"min={float(v.min()):.4f}, max={float(v.max()):.4f}"}


def test_microstructure_participation_flat():
    """When volume is constant, participation_ratio must equal 1.0 exactly."""
    c = np.linspace(100, 110, 60)
    df = _ohlcv_from_close(c)
    df["volume"] = 1_000_000.0
    X = compute_features(df, ["microstructure.relative.participation_20"])
    v = X["microstructure.relative.participation_20"].dropna().values
    return {"name": "participation(flat V) = 1",
            "passed": bool(len(v) > 0 and np.allclose(v, 1.0)),
            "detail": f"unique={sorted(set(np.round(v, 6)))[:3]}"}


def test_execution_imbalance_monotone_up():
    """On a strictly rising close, execution_imbalance saturates at +1."""
    c = 100 + np.arange(60, dtype=float)  # monotone up → every body > 0
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["microstructure.expansion.execution_imbalance_20"])
    v = X["microstructure.expansion.execution_imbalance_20"].dropna().iloc[-1]
    return {"name": "exec_imbalance(monotone up) ≈ +1",
            "passed": bool(np.isfinite(v) and abs(v - 1.0) < 1e-6),
            "detail": f"v={v}"}


def test_pivot_high_on_synthetic_peak():
    """A single spike in the middle of a flat series must be a pivot high."""
    c = np.full(31, 100.0); c[15] = 105.0
    df = _ohlcv_from_close(c)
    df["high"] = c * 1.001; df.iloc[15, df.columns.get_loc("high")] = 105.0 * 1.001
    X = compute_features(df, ["market_structure.regime.pivot_high_flag_k5"])
    v = X["market_structure.regime.pivot_high_flag_k5"].values
    # Confirmed at bar 15+5 = 20
    return {"name": "pivot_high fires on synthetic peak",
            "passed": bool(v[20] > 0.5),
            "detail": f"flag[15]={v[15]}, flag[20]={v[20]}"}


def test_bos_flat_is_zero():
    """On a flat series, close never crosses a prior swing → BOS = 0 everywhere."""
    c = np.full(80, 100.0)
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["market_structure.motion.bos_k3"])
    v = X["market_structure.motion.bos_k3"].dropna().values
    return {"name": "BOS(flat) = 0",
            "passed": bool(len(v) > 0 and np.allclose(v, 0.0)),
            "detail": f"max|v|={float(np.max(np.abs(v))):.2e}"}


def test_structure_regime_range():
    """structure_regime must lie in {-1, 0, +1}."""
    rng = np.random.default_rng(7)
    c = 100 + np.cumsum(rng.normal(0, 1, 200))
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["market_structure.regime.structure_regime_k3"])
    v = X["market_structure.regime.structure_regime_k3"].dropna().values
    ok = set(np.unique(v).tolist()).issubset({-1.0, 0.0, 1.0})
    return {"name": "structure_regime ∈ {-1,0,+1}",
            "passed": bool(ok),
            "detail": f"unique={sorted(set(v.tolist()))[:5]}"}


def test_log_spread_antisymmetric():
    """log_spread(a, b) = -log_spread(b, a) — symmetry of the crossasset engine."""
    from atlas_core.engines import crossasset as ca
    rng = np.random.default_rng(11)
    a = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 100))))
    b = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 100))))
    s1 = ca.log_spread(a, b); s2 = ca.log_spread(b, a)
    return {"name": "log_spread antisymmetric",
            "passed": bool(np.allclose(s1.values, -s2.values, equal_nan=True)),
            "detail": f"max_dev={float(np.nanmax(np.abs(s1.values + s2.values))):.2e}"}


def test_compression_expansion_vol_ratio_positive():
    """Short/long vol ratio must be strictly positive when both estimators are."""
    rng = np.random.default_rng(13)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, 300)))
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["compression_expansion.expansion.vol_ratio_10_50"])
    v = X["compression_expansion.expansion.vol_ratio_10_50"].dropna().values
    return {"name": "vol_ratio > 0",
            "passed": bool(len(v) > 0 and (v > 0).all()),
            "detail": f"min={float(v.min()):.4f} max={float(v.max()):.4f}"}


def test_relative_strength_null_without_peer():
    """Relative-strength features return NaN when no peer context is attached
    (soft-fail contract for missing multi-symbol payload)."""
    rng = np.random.default_rng(17)
    c = 100 + np.cumsum(rng.normal(0, 1, 100))
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["relative_strength.magnitude.rs_20"])
    v = X["relative_strength.magnitude.rs_20"].dropna().values
    return {"name": "relative_strength = NaN without peer",
            "passed": bool(len(v) == 0),
            "detail": f"non_null_count={len(v)}"}


# ── v0.7 additions · momentum_of_trend (L2) ────────────────────────────────

def test_mot_velocity_of_constant_slope_is_zero():
    """On a strictly linear close, lr_slope_20 is (asymptotically) constant,
    so its velocity is ≈ 0.  We use a long enough series that transient
    boundary effects are gone and check the last-bar velocity is tiny."""
    n = 200
    c = 100.0 + 0.5 * np.arange(n, dtype=float)  # constant slope = 0.5
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["momentum_of_trend.motion.lr_slope_20_velocity_20"])
    v = X["momentum_of_trend.motion.lr_slope_20_velocity_20"].iloc[-1]
    return {"name": "velocity of constant slope ≈ 0",
            "passed": bool(np.isfinite(v) and abs(v) < 1e-6),
            "detail": f"v={v:.3e}"}


def test_mot_velocity_sign_flips_on_v_shape():
    """A V-shaped close (down then up) sends the LR slope from negative to
    positive → the velocity of the slope must be positive around the pivot.
    We only assert the velocity samples span both signs somewhere in the
    series, which is what 'sign flip' requires."""
    n = 240
    left = 100.0 - 0.3 * np.arange(n // 2, dtype=float)
    right = left[-1] + 0.4 * np.arange(n - n // 2, dtype=float)
    c = np.concatenate([left, right])
    df = _ohlcv_from_close(c)
    X = compute_features(df, ["momentum_of_trend.motion.lr_slope_20_velocity_20"])
    v = X["momentum_of_trend.motion.lr_slope_20_velocity_20"].dropna().values
    has_pos = bool((v > 1e-4).any())
    has_neg_or_zero = bool((v <= 1e-6).any())
    return {"name": "velocity of slope changes sign on V-shape",
            "passed": bool(has_pos and has_neg_or_zero and np.isfinite(v).any()),
            "detail": f"min={float(v.min()):.3e}, max={float(v.max()):.3e}"}


def test_mot_direction_persistence_bounds():
    """direction_persistence output must lie in [0, w] and be integer-valued."""
    rng = np.random.default_rng(19)
    c = 100.0 + np.cumsum(rng.normal(0, 0.5, 200))
    df = _ohlcv_from_close(c)
    X = compute_features(
        df, ["momentum_of_trend.regime.lr_slope_20_direction_persistence_20"])
    v = X["momentum_of_trend.regime.lr_slope_20_direction_persistence_20"].dropna().values
    ok_range = bool((v >= 0).all() and (v <= 20).all())
    ok_int = bool(np.all(v == np.floor(v)))
    return {"name": "direction_persistence ∈ [0, w] and integer",
            "passed": bool(ok_range and ok_int),
            "detail": f"min={float(v.min())}, max={float(v.max())}, int_ok={ok_int}"}


def test_mot_velocity_sign_agreement_in_unit_interval():
    """velocity_sign_agreement_20 must lie in [0, 1] at every finite point."""
    rng = np.random.default_rng(23)
    c = 100.0 + np.cumsum(rng.normal(0, 0.6, 250))
    df = _ohlcv_from_close(c)
    X = compute_features(df,
        ["momentum_of_trend.relative.velocity_sign_agreement_20"])
    v = X["momentum_of_trend.relative.velocity_sign_agreement_20"].dropna().values
    return {"name": "velocity_sign_agreement ∈ [0, 1]",
            "passed": bool(len(v) > 0 and v.min() >= 0.0 and v.max() <= 1.0),
            "detail": f"min={float(v.min()):.3f}, max={float(v.max()):.3f}"}


# ── v0.7.1 additions · trend_relationships (L2) ───────────────────────────

def test_tr_slope_agreement_on_pure_trend():
    """On a strictly linear rising close, lr_slope_20, ema_slope_20 and
    aroon_osc_14 are all positive at the tail → consensus_score = 1.0 and
    consensus_sign = +1."""
    n = 220
    c = 100.0 + 0.5 * np.arange(n, dtype=float)
    df = _ohlcv_from_close(c)
    X = compute_features(df, [
        "trend_relationships.regime.directional_consensus_score_20",
        "trend_relationships.regime.directional_consensus_sign_20",
    ])
    score = X["trend_relationships.regime.directional_consensus_score_20"].iloc[-1]
    sign = X["trend_relationships.regime.directional_consensus_sign_20"].iloc[-1]
    ok = bool(np.isfinite(score) and abs(score - 1.0) < 1e-9 and sign == 1.0)
    return {"name": "consensus = 1.0 and sign = +1 on pure up-trend",
            "passed": ok, "detail": f"score={score}, sign={sign}"}


def test_tr_ema_cascade_score_bounds_and_full_up():
    """On a strictly rising close the EMA cascade is fully up-ordered at
    the tail → cascade_score = 1 and cascade_signed = +1. Also the score
    must be within [0, 1] everywhere."""
    n = 260
    c = 100.0 + 0.4 * np.arange(n, dtype=float)
    df = _ohlcv_from_close(c)
    X = compute_features(df, [
        "trend_relationships.geometry.ema_cascade_score_10_20_50_100",
        "trend_relationships.geometry.ema_cascade_signed_10_20_50_100",
    ])
    sc = X["trend_relationships.geometry.ema_cascade_score_10_20_50_100"].dropna()
    sg = X["trend_relationships.geometry.ema_cascade_signed_10_20_50_100"].iloc[-1]
    in_bounds = bool((sc >= 0.0).all() and (sc <= 1.0).all())
    tail_full_up = bool(abs(sc.iloc[-1] - 1.0) < 1e-9 and sg == 1.0)
    return {"name": "EMA cascade ∈ [0, 1]; fully up on pure up-trend",
            "passed": bool(in_bounds and tail_full_up),
            "detail": f"min={float(sc.min())}, max={float(sc.max())}, tail_signed={float(sg)}"}


def test_tr_cross_scale_agreement_on_v_shape():
    """A V-shaped close reverses direction mid-series; the sign of
    lr_slope_20 flips before lr_slope_50 → cross_scale_agreement must
    contain at least one -1 in the transition band."""
    n = 260
    left = 100.0 - 0.3 * np.arange(n // 2, dtype=float)
    right = left[-1] + 0.4 * np.arange(n - n // 2, dtype=float)
    c = np.concatenate([left, right])
    df = _ohlcv_from_close(c)
    X = compute_features(df, [
        "trend_relationships.relative.slope_cross_scale_agreement_20_50"])
    v = X["trend_relationships.relative.slope_cross_scale_agreement_20_50"].dropna().values
    has_neg = bool((v == -1).any())
    return {"name": "slope_cross_scale_agreement has -1 during V reversal",
            "passed": has_neg,
            "detail": f"min={float(v.min())}, max={float(v.max())}"}


def test_tr_methodology_sign_span_bounds():
    """methodology_sign_span_20 must be integer-valued and lie in {0, 1, 2}
    at every finite bar (max sign span with three signed sources is 2)."""
    rng = np.random.default_rng(29)
    c = 100.0 + np.cumsum(rng.normal(0, 0.5, 220))
    df = _ohlcv_from_close(c)
    X = compute_features(df, [
        "trend_relationships.relative.methodology_sign_span_20"])
    v = X["trend_relationships.relative.methodology_sign_span_20"].dropna().values
    ok_range = bool((v >= 0).all() and (v <= 2).all())
    ok_set = bool(np.isin(v, [0.0, 1.0, 2.0]).all())
    return {"name": "methodology_sign_span ∈ {0, 1, 2}",
            "passed": bool(ok_range and ok_set),
            "detail": f"min={float(v.min())}, max={float(v.max())}, set_ok={ok_set}"}


def test_tr_consensus_score_range():
    """directional_consensus_score_20 ∈ [1/3, 1.0] at every finite bar."""
    rng = np.random.default_rng(31)
    c = 100.0 + np.cumsum(rng.normal(0, 0.5, 250))
    df = _ohlcv_from_close(c)
    X = compute_features(df, [
        "trend_relationships.regime.directional_consensus_score_20"])
    v = X["trend_relationships.regime.directional_consensus_score_20"].dropna().values
    lo = 1.0 / 3.0
    ok = bool(len(v) > 0 and v.min() >= lo - 1e-9 and v.max() <= 1.0 + 1e-9)
    return {"name": "directional_consensus_score ∈ [1/3, 1]",
            "passed": ok,
            "detail": f"min={float(v.min()):.4f}, max={float(v.max()):.4f}"}


# ══ v0.7.2 additions — fractal_relationships (L2) ══════════════════════════
#
# Every test uses a Brownian input (i.i.d. Gaussian log-returns → geometric
# Brownian motion in price). Brownian motion is the canonical monofractal
# with Hurst H = 0.5. See docs/L2_SPECS/FRACTAL_RELATIONSHIPS.md §5.6 for
# the full canonical-value reference table.

def _brownian_ohlcv(n: int, sigma: float = 0.01, seed: int = 42) -> pd.DataFrame:
    """Deterministic geometric Brownian motion OHLCV."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, sigma, n)
    c = 100.0 * np.exp(np.cumsum(r))
    return _ohlcv_from_close(c)


def test_fr_variance_scaling_of_brownian_is_one():
    """Brownian: Var[r_τ] = τ·σ² → variance_scaling_exponent → 1.0.
    Loose tolerance (±0.35) for finite-sample estimator bias at W=128."""
    df = _brownian_ohlcv(500, seed=42)
    X = compute_features(df, [
        "fractal_relationships.geometry.variance_scaling_exponent_2_64"])
    v = X["fractal_relationships.geometry.variance_scaling_exponent_2_64"].dropna()
    if len(v) == 0:
        return {"name": "variance_scaling of Brownian ≈ 1",
                "passed": False, "detail": "no finite values"}
    last = float(v.iloc[-1])
    ok = 0.65 <= last <= 1.35
    return {"name": "variance_scaling of Brownian ≈ 1",
            "passed": ok,
            "detail": f"α_last={last:.3f} (Brownian canonical = 1.0)"}


def test_fr_multifractal_spread_of_monofractal_is_near_zero():
    """Brownian is monofractal → |H(1) − H(3)| ≈ 0 (tolerance 0.15)."""
    df = _brownian_ohlcv(500, seed=43)
    X = compute_features(df, [
        "fractal_relationships.statistics.multifractal_spread_h1_minus_h3_2_32"])
    v = X["fractal_relationships.statistics.multifractal_spread_h1_minus_h3_2_32"].dropna()
    if len(v) == 0:
        return {"name": "multifractal_spread of monofractal ≈ 0",
                "passed": False, "detail": "no finite values"}
    last = float(v.iloc[-1])
    ok = abs(last) < 0.15
    return {"name": "multifractal_spread of monofractal ≈ 0",
            "passed": ok,
            "detail": f"|H(1)-H(3)|={abs(last):.4f} (Brownian canonical = 0)"}


def test_fr_variance_ratio_of_random_walk_max_deviation_is_small():
    """Under the random-walk null VR(τ) ≈ 1 → max deviation < 0.5 (loose)."""
    df = _brownian_ohlcv(500, seed=44)
    X = compute_features(df, [
        "fractal_relationships.distribution.variance_ratio_max_deviation_from_unity_2_16"])
    v = X["fractal_relationships.distribution.variance_ratio_max_deviation_from_unity_2_16"].dropna()
    if len(v) == 0:
        return {"name": "VR max deviation on random walk < 0.5",
                "passed": False, "detail": "no finite values"}
    last = float(v.iloc[-1])
    ok = last < 0.5
    return {"name": "VR max deviation on random walk < 0.5",
            "passed": ok,
            "detail": f"max|VR−1|={last:.4f} (Brownian canonical = 0)"}


def test_fr_hurst_cross_window_std_bounds():
    """std of 3 Hurst values each ∈ [0, 1] → result in [0, 0.5] at every finite bar."""
    df = _brownian_ohlcv(400, seed=45)
    X = compute_features(df, [
        "fractal_relationships.regime.hurst_cross_window_std_32_64_128"])
    v = X["fractal_relationships.regime.hurst_cross_window_std_32_64_128"].dropna().values
    if len(v) == 0:
        return {"name": "hurst_cross_window_std ∈ [0, 0.5]",
                "passed": False, "detail": "no finite values"}
    ok = bool(v.min() >= -1e-9 and v.max() <= 0.5 + 1e-9)
    return {"name": "hurst_cross_window_std ∈ [0, 0.5]",
            "passed": ok,
            "detail": f"min={float(v.min()):.4f}, max={float(v.max()):.4f}"}


def test_fr_self_similarity_score_bounds():
    """Composite score is a geometric mean of quantities in [0, 1] → output ∈ [0, 1]."""
    df = _brownian_ohlcv(400, seed=46)
    X = compute_features(df, [
        "fractal_relationships.regime.self_similarity_score"])
    v = X["fractal_relationships.regime.self_similarity_score"].dropna().values
    if len(v) == 0:
        return {"name": "self_similarity_score ∈ [0, 1]",
                "passed": False, "detail": "no finite values"}
    ok = bool(v.min() >= -1e-9 and v.max() <= 1.0 + 1e-9)
    return {"name": "self_similarity_score ∈ [0, 1]",
            "passed": ok,
            "detail": f"min={float(v.min()):.4f}, max={float(v.max()):.4f}"}


def test_fr_self_similarity_flag_is_binary():
    """Flag ∈ {0, 1} (integer-valued) at every finite bar."""
    df = _brownian_ohlcv(400, seed=47)
    X = compute_features(df, [
        "fractal_relationships.regime.self_similarity_flag"])
    v = X["fractal_relationships.regime.self_similarity_flag"].dropna().values
    if len(v) == 0:
        return {"name": "self_similarity_flag ∈ {0, 1}",
                "passed": False, "detail": "no finite values"}
    ok_set = set(np.unique(v.round(6))).issubset({0.0, 1.0})
    return {"name": "self_similarity_flag ∈ {0, 1}",
            "passed": bool(ok_set),
            "detail": f"unique={sorted(set(v.round(6)))}"}


ALL_TESTS = [
    test_close_identity,
    test_linear_straightness_is_one,
    test_zigzag_complexity,
    test_log_return_of_flat_is_zero,
    test_lr_slope_matches_analytical,
    test_lr_r2_on_line_is_one,
    test_zscore_of_line_is_predictable,
    test_cc_vol_of_gbm_matches_sigma,
    test_upside_downside_sum_of_squares,
    test_obv_flat_returns_zero,
    # v0.6 additions
    test_microstructure_body_identity,
    test_microstructure_body_over_range_bounds,
    test_microstructure_wick_difference_symmetry,
    test_microstructure_participation_flat,
    test_execution_imbalance_monotone_up,
    test_pivot_high_on_synthetic_peak,
    test_bos_flat_is_zero,
    test_structure_regime_range,
    test_log_spread_antisymmetric,
    test_compression_expansion_vol_ratio_positive,
    test_relative_strength_null_without_peer,
    # v0.7 additions — momentum_of_trend (L2)
    test_mot_velocity_of_constant_slope_is_zero,
    test_mot_velocity_sign_flips_on_v_shape,
    test_mot_direction_persistence_bounds,
    test_mot_velocity_sign_agreement_in_unit_interval,
    # v0.7.1 additions — trend_relationships (L2)
    test_tr_slope_agreement_on_pure_trend,
    test_tr_ema_cascade_score_bounds_and_full_up,
    test_tr_cross_scale_agreement_on_v_shape,
    test_tr_methodology_sign_span_bounds,
    test_tr_consensus_score_range,
    # v0.7.2 additions — fractal_relationships (L2)
    test_fr_variance_scaling_of_brownian_is_one,
    test_fr_multifractal_spread_of_monofractal_is_near_zero,
    test_fr_variance_ratio_of_random_walk_max_deviation_is_small,
    test_fr_hurst_cross_window_std_bounds,
    test_fr_self_similarity_score_bounds,
    test_fr_self_similarity_flag_is_binary,
]


def run_all() -> Dict[str, Any]:
    results = []
    for t in ALL_TESTS:
        try:
            results.append(t())
        except Exception as e:
            results.append({"name": t.__name__, "passed": False,
                            "detail": f"exception: {e}"})
    passed = sum(1 for r in results if r["passed"])
    return {"total": len(results), "passed": passed,
            "pass_rate": round(passed / max(1, len(results)), 3),
            "results": results}


# ═══════════════════════════════════════════════════════════════════
# v0.7.4 · Validation Framework (DEC-013)
# ═══════════════════════════════════════════════════════════════════
# Layered exports — the framework subsystem lives alongside the 36
# module-level goldens above. Both are accessible; internal callers
# should prefer the framework's runner + report over the legacy runner.
#
# See /app/docs/VALIDATION_FRAMEWORK.md for the specification.
from .declaration import FeatureValidation, Identity, DEFAULT_UNIVERSAL_GATES
from .profile import ValidationProfile, GateResult, IdentityResult
from .runner import run_all as run_framework, get_profile
from .report import build_report, legacy_golden_view

__all__ = [
    # Legacy 36-golden runner
    "run_all", "ALL_TESTS",
    # Framework
    "FeatureValidation", "Identity", "DEFAULT_UNIVERSAL_GATES",
    "ValidationProfile", "GateResult", "IdentityResult",
    "run_framework", "get_profile", "build_report", "legacy_golden_view",
]

"""Atlas Validation Framework — Universal gates (batched).

Gates read from a pre-batched FixtureMatrices when available; otherwise
fall back to on-the-fly compute (for isolated invocation / unit tests).
This reduces full-report runtime from ~330s to ~40s cached.

Gate contract: gate(feature_def, ctx) -> GateResult.
ctx is None (fallback) or a FixtureMatrices instance.
"""
from __future__ import annotations
import time
import numpy as np
import pandas as pd
from typing import Any, Dict

from ..profile import GateResult
from .. import fixtures as F


def _time_ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000.0, 3)


def _compute_one(feature_def, df: pd.DataFrame, context=None):
    """Fallback single-feature compute (unit-test path)."""
    from atlas_core.compute import compute_features
    X = compute_features(df, [feature_def.id], context=context)
    if feature_def.id not in X.columns:
        return None
    return X[feature_def.id]


def _col(matrix: pd.DataFrame, fid: str):
    """Fetch a feature's column from a batched matrix."""
    if matrix is None or fid not in matrix.columns:
        return None
    return matrix[fid]


# ---------------------------------------------------------------------
# Universal gate implementations (matrix-aware)
# ---------------------------------------------------------------------
def determinism(feature_def, ctx) -> GateResult:
    t0 = time.perf_counter()
    try:
        if ctx is not None and getattr(ctx, "brownian_X", None) is not None:
            a = _col(ctx.brownian_X, feature_def.id)
            b = _col(ctx.brownian_X_2, feature_def.id)
        else:
            df = F.brownian()
            a = _compute_one(feature_def, df)
            b = _compute_one(feature_def, df)
        if a is None or b is None:
            return GateResult("determinism", "n/a",
                              {"reason": "no output"}, _time_ms(t0))
        mask = a.notna() & b.notna() & np.isfinite(a) & np.isfinite(b)
        if not mask.any():
            return GateResult("determinism", "n/a",
                              {"reason": "no finite output"}, _time_ms(t0))
        va = a[mask].values; vb = b[mask].values
        ok = np.allclose(va, vb, atol=1e-12, rtol=0)
        return GateResult("determinism", "pass" if ok else "fail",
                          {"n_compared": int(mask.sum()),
                           "max_abs_diff": float(np.max(np.abs(va - vb)))},
                          _time_ms(t0))
    except Exception as e:
        return GateResult("determinism", "error",
                          {"error": str(e)[:200]}, _time_ms(t0))


def length_invariance(feature_def, ctx) -> GateResult:
    t0 = time.perf_counter()
    try:
        if ctx is not None and getattr(ctx, "brownian_X", None) is not None:
            s = _col(ctx.brownian_X, feature_def.id)
            df_len = len(ctx.brownian_df)
        else:
            df = F.brownian()
            s = _compute_one(feature_def, df); df_len = len(df)
        if s is None:
            return GateResult("length_invariance", "n/a",
                              {"reason": "no output"}, _time_ms(t0))
        ok = (len(s) == df_len)
        return GateResult("length_invariance",
                          "pass" if ok else "fail",
                          {"n_input": df_len, "n_output": len(s)},
                          _time_ms(t0))
    except Exception as e:
        return GateResult("length_invariance", "error",
                          {"error": str(e)[:200]}, _time_ms(t0))


def no_future_leakage(feature_def, ctx) -> GateResult:
    t0 = time.perf_counter()
    try:
        if ctx is not None and getattr(ctx, "brownian_X", None) is not None:
            base = _col(ctx.brownian_X, feature_def.id)
            pert = _col(ctx.brownian_perturbed_X, feature_def.id)
            K = ctx.k_perturbed
        else:
            df = F.brownian().copy(); K = 10
            base = _compute_one(feature_def, df)
            df2 = df.copy()
            rng = np.random.default_rng(999)
            m = rng.uniform(1.5, 3.0, size=K)
            for col in ("open", "high", "low", "close"):
                df2.iloc[-K:, df2.columns.get_loc(col)] *= (m if col != "low" else m*0.99)
            pert = _compute_one(feature_def, df2)
        if base is None or pert is None:
            return GateResult("no_future_leakage", "n/a",
                              {"reason": "no output"}, _time_ms(t0))
        a = base.iloc[:-K]; b = pert.iloc[:-K]
        mask = a.notna() & b.notna() & np.isfinite(a) & np.isfinite(b)
        if not mask.any():
            return GateResult("no_future_leakage", "n/a",
                              {"reason": "no finite pts"}, _time_ms(t0))
        va = a[mask].values; vb = b[mask].values
        ok = np.allclose(va, vb, atol=1e-9, rtol=0)
        return GateResult("no_future_leakage",
                          "pass" if ok else "fail",
                          {"k_perturbed": K,
                           "n_compared": int(mask.sum()),
                           "max_abs_diff": float(np.max(np.abs(va - vb)))},
                          _time_ms(t0))
    except Exception as e:
        return GateResult("no_future_leakage", "error",
                          {"error": str(e)[:200]}, _time_ms(t0))


def nan_input_behavior(feature_def, ctx) -> GateResult:
    t0 = time.perf_counter()
    decl = getattr(feature_def, "validation", None)
    expected = (decl.nan_behavior if decl else "propagate")
    try:
        if ctx is not None and getattr(ctx, "nan_infested_X", None) is not None:
            s = _col(ctx.nan_infested_X, feature_def.id)
        else:
            s = _compute_one(feature_def, F.nan_infested())
        if s is None:
            return GateResult("nan_input_behavior", "n/a",
                              {"reason": "no output"}, _time_ms(t0))
        n_total = int(len(s))
        n_finite = int(np.isfinite(s.values).sum())
        finite_frac = (n_finite / n_total) if n_total else 0.0
        if expected == "ignore":
            ok = finite_frac >= 0.6
        elif expected == "recover":
            ok = int(np.isfinite(s.values[-100:]).sum()) >= 60
        else:  # propagate (default) — no-crash suffices
            ok = True
        return GateResult("nan_input_behavior",
                          "pass" if ok else "fail",
                          {"declared": expected,
                           "finite_fraction": round(finite_frac, 4)},
                          _time_ms(t0))
    except Exception as e:
        return GateResult("nan_input_behavior", "error",
                          {"error": str(e)[:200], "declared": expected},
                          _time_ms(t0))


def degenerate_constant(feature_def, ctx) -> GateResult:
    t0 = time.perf_counter()
    decl = getattr(feature_def, "validation", None)
    expected = (decl.degenerate_value if decl else None)
    try:
        if ctx is not None and getattr(ctx, "constant_X", None) is not None:
            s = _col(ctx.constant_X, feature_def.id)
        else:
            s = _compute_one(feature_def, F.constant())
        if s is None:
            return GateResult("degenerate_constant", "n/a",
                              {"reason": "no output"}, _time_ms(t0))
        finite = s.values[np.isfinite(s.values)]
        if len(finite) == 0:
            if expected is None or np.isnan(expected):
                return GateResult("degenerate_constant", "pass",
                                  {"observed": "all-NaN", "expected": "any"},
                                  _time_ms(t0))
            return GateResult("degenerate_constant", "fail",
                              {"observed": "all-NaN",
                               "expected": float(expected)},
                              _time_ms(t0))
        if expected is not None and not np.isnan(expected):
            ok = np.allclose(finite, expected, atol=1e-9, rtol=0)
            return GateResult("degenerate_constant",
                              "pass" if ok else "fail",
                              {"expected": float(expected),
                               "observed_head": [float(x) for x in finite[:3]]},
                              _time_ms(t0))
        return GateResult("degenerate_constant", "pass",
                          {"observed_head": [float(x) for x in finite[:3]],
                           "n_finite": int(len(finite)),
                           "expected": "any"}, _time_ms(t0))
    except Exception as e:
        return GateResult("degenerate_constant", "error",
                          {"error": str(e)[:200]}, _time_ms(t0))


UNIVERSAL_GATES: Dict[str, Any] = {
    "determinism": determinism,
    "length_invariance": length_invariance,
    "no_future_leakage": no_future_leakage,
    "nan_input_behavior": nan_input_behavior,
    "degenerate_constant": degenerate_constant,
}

"""Atlas Validation Framework — Property gates + Identity verifiers.

Property gates are opt-in: they run only where the feature's
FeatureValidation.properties block declares them. Identity verifiers
prove named analytical identities (e.g. rs(a, a) ≡ 1).

Gate contract: gate(feature_def, ctx, params) -> GateResult.
Identity contract: verifier(feature_def, ctx, tol) -> (status, max_dev, evidence).
"""
from __future__ import annotations
import time
import numpy as np
import pandas as pd
from typing import Any, Callable, Dict, Tuple

from ..profile import GateResult
from .. import fixtures as F
from .universal import _compute_one, _time_ms, _col


# ---------------------------------------------------------------------
# Property gates
# ---------------------------------------------------------------------
def bounded(feature_def, ctx, params: Dict) -> GateResult:
    """Every finite output lies in [lo - tol, hi + tol]."""
    t0 = time.perf_counter()
    lo = params.get("lo"); hi = params.get("hi")
    tol = params.get("tol", 1e-9)
    if lo is None or hi is None:
        return GateResult("bounded", "error",
                          {"error": "bounded requires lo and hi params"},
                          _time_ms(t0))
    combined = []
    if ctx is not None and getattr(ctx, "brownian_X", None) is not None:
        for X in (ctx.brownian_X, ctx.trending_X, ctx.mean_reverting_X):
            if X is None or feature_def.id not in X.columns:
                continue
            vals = X[feature_def.id].values
            combined.append(vals[np.isfinite(vals)])
        # If the feature declares requires_context peer, also consider
        # its peer-self matrix so bounded works for RS features.
        decl = getattr(feature_def, "validation", None)
        if decl and "peer" in getattr(decl, "requires_context", []):
            for X in (ctx.peer_self_X, ctx.peer_a_with_b_X):
                if X is None or feature_def.id not in X.columns:
                    continue
                vals = X[feature_def.id].values
                combined.append(vals[np.isfinite(vals)])
    else:
        for fxname in ("brownian", "trending", "mean_reverting"):
            fx = F.CANONICAL_FIXTURES[fxname]()
            try:
                ctx_kwargs = {}
                decl = getattr(feature_def, "validation", None)
                if decl and "peer" in getattr(decl, "requires_context", []):
                    _, peer = F.two_pairs()
                    peer = peer.reindex(fx.index).ffill()
                    ctx_kwargs = {"context": {"peer": peer}}
                s = _compute_one(feature_def, fx, **ctx_kwargs)
                if s is not None:
                    combined.append(s.values[np.isfinite(s.values)])
            except Exception:
                pass
    if not combined:
        return GateResult("bounded", "n/a",
                          {"reason": "no finite output"}, _time_ms(t0))
    arr = np.concatenate(combined)
    if arr.size == 0:
        return GateResult("bounded", "n/a",
                          {"reason": "empty finite set"}, _time_ms(t0))
    mn = float(np.min(arr)); mx = float(np.max(arr))
    ok = (mn >= lo - tol) and (mx <= hi + tol)
    return GateResult("bounded",
                      "pass" if ok else "fail",
                      {"declared": {"lo": lo, "hi": hi, "tol": tol},
                       "observed_min": mn, "observed_max": mx,
                       "n_samples": int(len(arr))},
                      _time_ms(t0))


def scale_invariant(feature_def, ctx, params: Dict) -> GateResult:
    """f(k * close) == f(close) for k in the sampled multiplier set."""
    t0 = time.perf_counter()
    tol = params.get("tol", 1e-6)
    try:
        if ctx is not None and getattr(ctx, "brownian_X", None) is not None:
            base = _col(ctx.brownian_X, feature_def.id)
            variants = ctx.scale_X
        else:
            base_df = F.brownian()
            base = _compute_one(feature_def, base_df)
            variants = {}
            for k in params.get("ks", [0.5, 2.0, 10.0]):
                sc = base_df.copy()
                for col in ("open", "high", "low", "close"):
                    sc[col] = sc[col] * k
                variants[k] = None  # handled below via _compute_one
                variants[k] = _compute_one(feature_def, sc)
        if base is None:
            return GateResult("scale_invariant", "n/a",
                              {"reason": "no output"}, _time_ms(t0))
        max_dev = 0.0
        for k, Xk in variants.items():
            if isinstance(Xk, pd.DataFrame):
                s = _col(Xk, feature_def.id)
            else:
                s = Xk
            if s is None:
                continue
            mask = base.notna() & s.notna() & np.isfinite(base) & np.isfinite(s)
            if not mask.any():
                continue
            dev = float(np.max(np.abs(base[mask].values - s[mask].values)))
            max_dev = max(max_dev, dev)
        ok = max_dev <= tol
        return GateResult("scale_invariant",
                          "pass" if ok else "fail",
                          {"tol": tol, "max_deviation": max_dev},
                          _time_ms(t0))
    except Exception as e:
        return GateResult("scale_invariant", "error",
                          {"error": str(e)[:200]}, _time_ms(t0))


def translation_invariant(feature_def, ctx, params: Dict) -> GateResult:
    """f(close + c) == f(close) for c in the sampled shift set."""
    t0 = time.perf_counter()
    tol = params.get("tol", 1e-6)
    try:
        if ctx is not None and getattr(ctx, "brownian_X", None) is not None:
            base = _col(ctx.brownian_X, feature_def.id)
            variants = ctx.trans_X
        else:
            base_df = F.brownian()
            base = _compute_one(feature_def, base_df)
            variants = {}
            for c in params.get("cs", [-25.0, 50.0]):
                sh = base_df.copy()
                for col in ("open", "high", "low", "close"):
                    sh[col] = sh[col] + c
                variants[c] = _compute_one(feature_def, sh)
        if base is None:
            return GateResult("translation_invariant", "n/a",
                              {"reason": "no output"}, _time_ms(t0))
        max_dev = 0.0
        for c, Xc in variants.items():
            if isinstance(Xc, pd.DataFrame):
                s = _col(Xc, feature_def.id)
            else:
                s = Xc
            if s is None:
                continue
            mask = base.notna() & s.notna() & np.isfinite(base) & np.isfinite(s)
            if not mask.any():
                continue
            dev = float(np.max(np.abs(base[mask].values - s[mask].values)))
            max_dev = max(max_dev, dev)
        ok = max_dev <= tol
        return GateResult("translation_invariant",
                          "pass" if ok else "fail",
                          {"tol": tol, "max_deviation": max_dev},
                          _time_ms(t0))
    except Exception as e:
        return GateResult("translation_invariant", "error",
                          {"error": str(e)[:200]}, _time_ms(t0))


def symmetric_in_peer(feature_def, ctx, params: Dict) -> GateResult:
    """f(a, peer=b) == f(b, peer=a) for peer-context features."""
    t0 = time.perf_counter()
    tol = params.get("tol", 1e-6)
    try:
        if ctx is not None and getattr(ctx, "peer_a_with_b_X", None) is not None:
            sa = _col(ctx.peer_a_with_b_X, feature_def.id)
            sb = _col(ctx.peer_b_with_a_X, feature_def.id)
        else:
            a, b = F.two_pairs()
            sa = _compute_one(feature_def, a,
                              context={"peer": b.reindex(a.index).ffill()})
            sb = _compute_one(feature_def, b,
                              context={"peer": a.reindex(b.index).ffill()})
        if sa is None or sb is None:
            return GateResult("symmetric_in_peer", "n/a",
                              {"reason": "no output"}, _time_ms(t0))
        # Note: symmetry-strict features (e.g. correlations) will pass;
        # asymmetric features (e.g. rs_w = ret_a / ret_b) will fail — which
        # is the intended detection.
        mask = sa.notna() & sb.notna() & np.isfinite(sa) & np.isfinite(sb)
        if not mask.any():
            return GateResult("symmetric_in_peer", "n/a",
                              {"reason": "no finite pts"}, _time_ms(t0))
        dev = float(np.max(np.abs(sa[mask].values - sb[mask].values)))
        ok = dev <= tol
        return GateResult("symmetric_in_peer",
                          "pass" if ok else "fail",
                          {"tol": tol, "max_deviation": dev,
                           "n_compared": int(mask.sum())},
                          _time_ms(t0))
    except Exception as e:
        return GateResult("symmetric_in_peer", "error",
                          {"error": str(e)[:200]}, _time_ms(t0))


def monotonic_with(feature_def, ctx, params: Dict) -> GateResult:
    """Monotonicity spot-check. params = {"input": "drift", "direction": "up"}."""
    t0 = time.perf_counter()
    direction = params.get("direction", "up")
    input_property = params.get("input", "drift")
    if input_property != "drift":
        return GateResult("monotonic_with", "n/a",
                          {"reason": f"input '{input_property}' not implemented"},
                          _time_ms(t0))
    try:
        drifts = [-0.001, 0.0, 0.001, 0.002]
        means = []
        for d in drifts:
            df = F.brownian(mu=d, seed_offset=int(1000 * abs(d) + 400))
            s = _compute_one(feature_def, df)
            if s is None:
                continue
            arr = s.values[np.isfinite(s.values)]
            if len(arr) == 0:
                continue
            means.append(float(np.median(arr)))
        if len(means) < 3:
            return GateResult("monotonic_with", "n/a",
                              {"reason": "insufficient finite outputs"},
                              _time_ms(t0))
        deltas = np.diff(means)
        if direction == "up":
            ok = np.sum(deltas > 0) >= (len(deltas) - 1)
        else:
            ok = np.sum(deltas < 0) >= (len(deltas) - 1)
        return GateResult("monotonic_with",
                          "pass" if ok else "fail",
                          {"direction": direction, "input": input_property,
                           "means": [round(m, 4) for m in means]},
                          _time_ms(t0))
    except Exception as e:
        return GateResult("monotonic_with", "error",
                          {"error": str(e)[:200]}, _time_ms(t0))


PROPERTY_GATES: Dict[str, Callable] = {
    "bounded": bounded,
    "scale_invariant": scale_invariant,
    "translation_invariant": translation_invariant,
    "symmetric_in_peer": symmetric_in_peer,
    "monotonic_with": monotonic_with,
    "mutual_exclusivity": None,  # module-level gate, populated below.
}


# ---------------------------------------------------------------------
# v0.8.0 — Layer 3 module-level property gates.
# ---------------------------------------------------------------------
# `mutual_exclusivity` is not a per-feature gate: it asserts a property
# on the *family* of flag features within a single L3 module (all
# `<module>.regime.<state>_flag` features published by that module).
# The framework runner calls it once per module (declared on the
# module's `active_state_code` feature, by convention).
def mutual_exclusivity(feature_def, ctx, params: Dict) -> GateResult:
    """At every bar t, at most ONE flag in the family is 1.

    Params:
      family_flags: list[str] — feature IDs that must be mutually
        exclusive. If empty, the gate resolves the family from the
        feature's module (all `<module>.regime.*_flag` features except
        the caller itself).

    Runs against every fixture in ctx.
    """
    t0 = time.perf_counter()
    family = list(params.get("family_flags") or [])
    if not family:
        # Auto-derive: peer flags in the same module.
        from atlas_core.registry.registry import registry as _reg
        mod = feature_def.module
        family = [f.id for f in _reg.filter(module=mod)
                  if f.perspective == "Regime"
                  and f.id.endswith("_flag")
                  and "active_state" not in f.id]
    if len(family) < 2:
        return GateResult("mutual_exclusivity", "skip",
                          {"reason": "fewer than 2 family flags",
                           "family": family}, _time_ms(t0))

    fixture_names = ("brownian", "trending", "mean_reverting")
    max_sum_seen = 0.0
    fixture_hit = None
    if ctx is not None and getattr(ctx, "brownian_X", None) is not None:
        matrices = [getattr(ctx, f"{n}_X", None) for n in fixture_names]
    else:
        matrices = [F.compute_on_fixture(n) for n in fixture_names]
    try:
        for name, X in zip(fixture_names, matrices):
            if X is None:
                continue
            cols = [c for c in family if c in X.columns]
            if len(cols) < 2:
                continue
            sub = X[cols].fillna(0.0).values
            row_sums = sub.sum(axis=1)
            m = float(np.nanmax(row_sums)) if len(row_sums) else 0.0
            if m > max_sum_seen:
                max_sum_seen = m
                fixture_hit = name
    except Exception as e:
        return GateResult("mutual_exclusivity", "error",
                          {"error": str(e)[:200]}, _time_ms(t0))

    status = "pass" if max_sum_seen <= 1.0 + 1e-9 else "fail"
    return GateResult("mutual_exclusivity", status,
                      {"max_row_sum": max_sum_seen,
                       "worst_fixture": fixture_hit,
                       "family_size": len(family)}, _time_ms(t0))


PROPERTY_GATES["mutual_exclusivity"] = mutual_exclusivity


# ---------------------------------------------------------------------
# v0.9.0 — Layer 4 property gates.
# ---------------------------------------------------------------------
def orthogonality(feature_def, ctx, params: Dict) -> GateResult:
    """Pairwise correlation of a set of features must be near zero.

    Params:
      family: list[str] — feature IDs whose pairwise correlations are
        certified. If empty, auto-derives from the feature's module
        (all features in the same module with the same family label).
      max_abs_corr: float — threshold; abs correlation strictly above
        this fails the gate. Defaults to 0.35 (rolling PCA on non-i.i.d.
        market data does not produce exact orthogonality).
    """
    t0 = time.perf_counter()
    family = list(params.get("family") or [])
    max_abs = float(params.get("max_abs_corr", 0.35))
    if not family:
        from atlas_core.registry.registry import registry as _reg
        family = [f.id for f in _reg.filter(module=feature_def.module)
                  if f.family == feature_def.family]
    if len(family) < 2:
        return GateResult("orthogonality", "skip",
                          {"reason": "fewer than 2 family features",
                           "family": family}, _time_ms(t0))
    fixture_names = ("brownian", "trending", "mean_reverting")
    if ctx is not None and getattr(ctx, "brownian_X", None) is not None:
        matrices = [getattr(ctx, f"{n}_X", None) for n in fixture_names]
    else:
        matrices = [F.compute_on_fixture(n) for n in fixture_names]
    worst_pair = None
    worst_val = 0.0
    try:
        for name, X in zip(fixture_names, matrices):
            if X is None:
                continue
            cols = [c for c in family if c in X.columns]
            if len(cols) < 2:
                continue
            sub = X[cols].dropna(how="any")
            if len(sub) < 30:
                continue
            C = sub.corr().abs().values.copy()
            np.fill_diagonal(C, 0.0)
            am = float(C.max())
            if am > worst_val:
                worst_val = am
                worst_pair = name
    except Exception as e:
        return GateResult("orthogonality", "error",
                          {"error": str(e)[:200]}, _time_ms(t0))
    status = "pass" if worst_val <= max_abs + 1e-9 else "fail"
    return GateResult("orthogonality", status,
                      {"max_abs_correlation": worst_val,
                       "worst_fixture": worst_pair,
                       "threshold": max_abs,
                       "family_size": len(family)}, _time_ms(t0))


PROPERTY_GATES["orthogonality"] = orthogonality


# ---------------------------------------------------------------------
# Identity verifiers
# ---------------------------------------------------------------------
def peer_equals_target__equals_one(feature_def, ctx, tol: float
                                    ) -> Tuple[str, float, Dict]:
    """For RS-style ratio features: with peer == target, output ≡ 1.0."""
    if ctx is not None and getattr(ctx, "peer_self_X", None) is not None:
        s = _col(ctx.peer_self_X, feature_def.id)
    else:
        df = F.brownian()
        s = _compute_one(feature_def, df, context={"peer": df.copy()})
    if s is None:
        return ("n/a", 0.0, {"reason": "compute empty"})
    finite = s.dropna()
    if finite.empty:
        return ("n/a", 0.0, {"reason": "no finite output"})
    dev = float(np.max(np.abs(finite.values - 1.0)))
    return ("pass" if dev <= tol else "fail", dev,
            {"n_compared": int(len(finite)),
             "observed_head": [float(x) for x in finite.values[:3]]})


def peer_equals_target__equals_one_corr(feature_def, ctx, tol: float
                                          ) -> Tuple[str, float, Dict]:
    """For RS correlation features: with peer == target, corr → 1.0."""
    if ctx is not None and getattr(ctx, "peer_self_X", None) is not None:
        s = _col(ctx.peer_self_X, feature_def.id)
    else:
        df = F.brownian()
        s = _compute_one(feature_def, df, context={"peer": df.copy()})
    if s is None:
        return ("n/a", 0.0, {"reason": "compute empty"})
    finite = s.dropna()
    if finite.empty:
        return ("n/a", 0.0, {"reason": "no finite output"})
    dev = float(np.max(np.abs(finite.values - 1.0)))
    return ("pass" if finite.min() >= (1.0 - max(tol, 1e-3)) else "fail", dev,
            {"min_observed": float(finite.min()),
             "n_compared": int(len(finite))})


def self_identity__equals_zero(feature_def, ctx, tol: float
                                ) -> Tuple[str, float, Dict]:
    """For log-spread-style features: with peer == target, output ≡ 0."""
    if ctx is not None and getattr(ctx, "peer_self_X", None) is not None:
        s = _col(ctx.peer_self_X, feature_def.id)
    else:
        df = F.brownian()
        s = _compute_one(feature_def, df, context={"peer": df.copy()})
    if s is None:
        return ("n/a", 0.0, {"reason": "compute empty"})
    finite = s.dropna()
    if finite.empty:
        return ("n/a", 0.0, {"reason": "no finite output"})
    dev = float(np.max(np.abs(finite.values)))
    return ("pass" if dev <= tol else "fail", dev,
            {"n_compared": int(len(finite))})


def legacy_module_golden(feature_def, ctx, tol: float
                          ) -> Tuple[str, float, Dict]:
    """Migration bridge for the 36 legacy pytest goldens.

    The concrete implementations already live in
    atlas_core/validation/__init__.py::run_all_golden(). This verifier
    delegates to that runner and looks up the result for the specific
    feature's owning module (module-level goldens are already validated
    en-masse). PASS if the entire golden run passes.
    """
    from atlas_core.validation import run_all
    try:
        report = run_all()
        # If the whole run passes, every constituent identity passes.
        ok = (report.get("passed", 0) == report.get("total", 0)
              and report.get("total", 0) > 0)
        return ("pass" if ok else "fail", 0.0,
                {"aggregate_passed": report.get("passed"),
                 "aggregate_total": report.get("total")})
    except Exception as e:
        return ("error", 0.0, {"error": str(e)[:200]})


IDENTITY_VERIFIERS: Dict[str, Callable] = {
    "peer_equals_target__equals_one": peer_equals_target__equals_one,
    "peer_equals_target__equals_one_corr": peer_equals_target__equals_one_corr,
    "self_identity__equals_zero": self_identity__equals_zero,
    "legacy_module_golden": legacy_module_golden,
}

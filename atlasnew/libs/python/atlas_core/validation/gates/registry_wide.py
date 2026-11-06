"""Atlas Validation Framework — Registry-wide gates.

Applied ONCE per report, not per feature. Detect duplication, invariant
breaches, and cross-module consistency issues.
"""
from __future__ import annotations
import time
import hashlib
import numpy as np
import pandas as pd
from typing import Any, Callable, Dict, List

from ..profile import GateResult
from .. import fixtures as F
from .universal import _compute_one, _time_ms


def unique_formula_hash(registry, ctx) -> GateResult:
    """The Registry contract: no duplicate formula+params within the same
    module (silent guardrail at register-time). This gate certifies that
    contract held. Cross-module formula duplicates (e.g. price.magnitude.body
    == microstructure.magnitude.body) are surfaced separately by the
    no_duplicate_values gate on numerical output — they are Registry-level
    debt tracked in KNOWN_LIMITATIONS §5 (Registry duplication), not a
    Registry-contract violation.
    """
    t0 = time.perf_counter()
    hashes = {}
    dups = []
    for f in registry.all():
        h = f.formula_hash if hasattr(f, "formula_hash") else \
            hashlib.sha1((f.formula or "").encode()).hexdigest()[:12]
        # Key by module to mirror Registry contract exactly.
        key = f"{f.module}:{h}"
        if key in hashes:
            dups.append((f.id, hashes[key]))
        hashes[key] = f.id
    return GateResult("unique_formula_hash",
                      "pass" if not dups else "fail",
                      {"n_features": len(hashes),
                       "duplicates_within_module": dups[:20],
                       "note": ("cross-module duplicates are surfaced by "
                                 "no_duplicate_values, not by this gate")},
                      _time_ms(t0))


def no_duplicate_values(registry, ctx) -> GateResult:
    """No two features produce numerically-identical output on the
    canonical Brownian fixture. Bucket-hash on tail-100 quantised to
    6 decimals, then pairwise verify within collisions.
    """
    t0 = time.perf_counter()
    from atlas_core.compute import compute_features
    if ctx is not None and getattr(ctx, "brownian_X", None) is not None:
        X = ctx.brownian_X
    else:
        df = F.brownian()
        ids = [f.id for f in registry.all()]
        try:
            X = compute_features(df, ids)
        except Exception as e:
            return GateResult("no_duplicate_values", "error",
                              {"error": str(e)[:200]}, _time_ms(t0))

    buckets: Dict[str, List[str]] = {}
    for fid in X.columns:
        tail = X[fid].iloc[-100:].values
        finite_tail = tail[np.isfinite(tail)]
        if len(finite_tail) < 10:
            continue
        q = np.round(finite_tail, 6).tobytes()
        h = hashlib.sha1(q).hexdigest()[:16]
        buckets.setdefault(h, []).append(fid)

    duplicates: List[List[str]] = []
    for group in buckets.values():
        if len(group) <= 1:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a = X[group[i]].values; b = X[group[j]].values
                mask = np.isfinite(a) & np.isfinite(b)
                if not mask.any():
                    continue
                if np.allclose(a[mask], b[mask], atol=1e-6, rtol=0):
                    duplicates.append([group[i], group[j]])

    return GateResult("no_duplicate_values",
                      "pass" if not duplicates else "fail",
                      {"n_features": int(X.shape[1]),
                       "n_pairs_checked": sum(len(g)*(len(g)-1)//2
                                              for g in buckets.values()),
                       "duplicates": duplicates[:20]},
                      _time_ms(t0))


def three_scale_rule(registry, ctx) -> GateResult:
    """Every fractal_relationships.* feature carries params['scales'] with
    len >= 3 (v0.7.2 architectural guardrail promoted to framework gate)."""
    t0 = time.perf_counter()
    offenders = []
    checked = 0
    for f in registry.all():
        if not f.id.startswith("fractal_relationships."):
            continue
        checked += 1
        scales = (f.params or {}).get("scales") if hasattr(f, "params") else None
        if not scales or len(scales) < 3:
            offenders.append(f.id)
    return GateResult("three_scale_rule",
                      "pass" if not offenders else "fail",
                      {"n_fractal_features": checked,
                       "offenders": offenders},
                      _time_ms(t0))


def context_isolation(registry, ctx) -> GateResult:
    """Features declaring requires_context=["peer"] must return all-NaN
    when no context is supplied (DEC-007 soft-fail contract)."""
    t0 = time.perf_counter()
    from atlas_core.compute import compute_features
    ids = [f.id for f in registry.all()
           if getattr(f, "validation", None) and
              "peer" in getattr(f.validation, "requires_context", [])]
    if not ids:
        return GateResult("context_isolation", "n/a",
                          {"reason": "no features declare requires_context"},
                          _time_ms(t0))
    try:
        if ctx is not None and getattr(ctx, "no_context_context_features_X", None) is not None:
            X = ctx.no_context_context_features_X
        else:
            X = compute_features(F.brownian(), ids, context=None)
    except Exception as e:
        return GateResult("context_isolation", "error",
                          {"error": str(e)[:200]}, _time_ms(t0))
    offenders = []
    for fid in ids:
        if fid not in X.columns:
            continue
        finite_count = int(np.isfinite(X[fid].values).sum())
        if finite_count > 0:
            offenders.append({"id": fid, "n_finite": finite_count})
    return GateResult("context_isolation",
                      "pass" if not offenders else "fail",
                      {"n_checked": len(ids), "offenders": offenders[:10]},
                      _time_ms(t0))


REGISTRY_WIDE_GATES: Dict[str, Callable] = {
    "unique_formula_hash": unique_formula_hash,
    "no_duplicate_values": no_duplicate_values,
    "three_scale_rule": three_scale_rule,
    "context_isolation": context_isolation,
}

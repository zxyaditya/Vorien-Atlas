"""Atlas Validation Framework — Report aggregator.

Aggregates every ValidationProfile into Registry-wide rollups grouped
by module and layer. Backwards-compatible /api/validation/golden view
is derived from the same data structure.
"""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .runner import run_all
from .profile import ValidationProfile


def build_report(module_filter: Optional[str] = None,
                 layer_filter: Optional[str] = None,
                 force: bool = False) -> Dict[str, Any]:
    """Produce the aggregate report as a JSON-serialisable dict."""
    from atlas_core.registry import registry
    data = run_all(force=force)
    profiles: Dict[str, ValidationProfile] = data["profiles"]
    registry_wide = data["registry_wide"]

    per_module = defaultdict(lambda: {"n": 0, "mean_coverage": 0.0,
                                       "n_pass_universal": 0,
                                       "n_fail": 0,
                                       "n_warnings": 0,
                                       "n_exemptions": 0})
    per_layer = defaultdict(lambda: {"n": 0, "mean_coverage": 0.0})
    features_out: List[Dict[str, Any]] = []
    for f in registry.all():
        p = profiles.get(f.id)
        if p is None:
            continue
        if module_filter and f.module != module_filter:
            continue
        if layer_filter and str(f.layer) != str(layer_filter):
            continue

        # Rollup accounting.
        module_bucket = per_module[f.module]
        module_bucket["n"] += 1
        module_bucket["mean_coverage"] += p.coverage_score
        universal_pass = sum(1 for g in p.gate_results
                             if g.status == "pass")
        universal_fail = sum(1 for g in p.gate_results
                             if g.status == "fail")
        module_bucket["n_pass_universal"] += universal_pass
        module_bucket["n_fail"] += universal_fail
        module_bucket["n_warnings"] += len(p.warnings)
        module_bucket["n_exemptions"] += len(p.declaration.exemptions)

        layer_bucket = per_layer[str(f.layer)]
        layer_bucket["n"] += 1
        layer_bucket["mean_coverage"] += p.coverage_score

        features_out.append(p.summary())

    for _, b in per_module.items():
        if b["n"]:
            b["mean_coverage"] = round(b["mean_coverage"] / b["n"], 4)
    for _, b in per_layer.items():
        if b["n"]:
            b["mean_coverage"] = round(b["mean_coverage"] / b["n"], 4)

    return {
        "generated_at": next(iter(profiles.values())).last_run
                          if profiles else "",
        "n_features": len(features_out),
        "registry_wide_gates": [g.to_dict() for g in registry_wide],
        "per_layer": dict(per_layer),
        "per_module": dict(per_module),
        "features": features_out,
        "cached": data.get("cached", False),
    }


def legacy_golden_view(force: bool = False) -> Dict[str, Any]:
    """Backwards-compatible /api/validation/golden shape.

    Returns {passed, total, pass_rate, details:[...]} derived from all
    identity results flagged as golden=True across the Registry, PLUS
    the aggregate legacy_module_golden identity if present.
    """
    from atlas_core.validation import run_all as _legacy_run
    data = run_all(force=force)
    profiles: Dict[str, ValidationProfile] = data["profiles"]

    # Prefer the framework-native count of golden-flagged identities
    # when features have declared them. If no golden identities have
    # been declared yet, fall back to the legacy module-level runner
    # so the endpoint keeps its historical semantics.
    framework_goldens = []
    for p in profiles.values():
        for ir in p.identity_results:
            if ir.golden:
                framework_goldens.append(ir)

    if framework_goldens:
        passed = sum(1 for ir in framework_goldens if ir.status == "pass")
        total  = len(framework_goldens)
        details = [{"name": ir.name, "passed": (ir.status == "pass"),
                    "max_deviation": ir.max_deviation,
                    "tolerance": ir.tolerance}
                    for ir in framework_goldens]
        # Also fold in the legacy module goldens so total matches history.
        legacy = _legacy_run()
        legacy_details = legacy.get("results", [])
        combined = details + legacy_details
        total_pass = passed + legacy.get("passed", 0)
        total_all  = total + legacy.get("total", 0)
        return {
            "passed": total_pass,
            "total":  total_all,
            "pass_rate": total_pass / max(1, total_all),
            # Both keys populated for compatibility:
            "results": combined,
            "details": combined,
            "source": "framework+legacy",
        }

    # Nothing declared yet — pure legacy.
    legacy = _legacy_run()
    legacy["source"] = "legacy"
    # Mirror `results` under `details` for a stable API surface.
    legacy["details"] = legacy.get("results", [])
    return legacy

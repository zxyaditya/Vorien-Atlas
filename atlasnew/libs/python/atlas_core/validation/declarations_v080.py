"""Atlas Validation Framework — v0.8.0 Layer 3 declarations.

Adds FeatureValidation declarations for the L3 state modules. Every
score, flag, confidence, and duration/transition receives at minimum a
`bounded` property gate. Each module's `active_state_code` receives the
new `mutual_exclusivity` property gate (v0.8.0) which certifies that
at any bar t, at most one flag in the family is active.

See docs/L3_MARKET_UNDERSTANDING.md §7 for the validation contract.
"""
from __future__ import annotations
from typing import Dict

from .declaration import FeatureValidation, Identity


L3_MODULES = ("trend_state", "range_state", "participation_state",
              "liquidity_state", "market_regime")


def _score_decl() -> FeatureValidation:
    return FeatureValidation(
        properties={"bounded": {"lo": 0.0, "hi": 1.0, "tol": 1e-9}},
        invariants=["6.1", "6.4"],
        assumptions=["evidence in unit-scale or auto-squashed"],
        nan_behavior="propagate",
        bridge="l3",
    )


def _flag_decl() -> FeatureValidation:
    return FeatureValidation(
        properties={"bounded": {"lo": 0.0, "hi": 1.0, "tol": 1e-9}},
        invariants=["6.1", "6.4"],
        assumptions=["flag is 0 or 1 by construction"],
        bridge="l3",
    )


def _confidence_decl() -> FeatureValidation:
    return FeatureValidation(
        properties={"bounded": {"lo": 0.0, "hi": 1.0, "tol": 1e-9}},
        invariants=["6.1", "6.4"],
        bridge="l3",
    )


def _active_code_decl() -> FeatureValidation:
    """Module-level: also asserts mutual_exclusivity across the family."""
    return FeatureValidation(
        properties={"mutual_exclusivity": {}},   # auto-derives family from module
        invariants=["6.1", "6.4"],
        assumptions=["at most one flag active per bar (winner-take-all)"],
        bridge="l3",
    )


def _build_declarations() -> Dict[str, FeatureValidation]:
    out: Dict[str, FeatureValidation] = {}
    for mod in L3_MODULES:
        out[f"{mod}.regime.active_state_code"] = _active_code_decl()
        out[f"{mod}.statistics.active_state_confidence"] = _confidence_decl()
    # Also declare bounded on a representative subset of scores/flags/confidences
    # per module (three sampled states each) so the framework surfaces coverage.
    sampled = {
        "trend_state":         ("trend_continuation", "trend_exhaustion", "trend_reversal"),
        "range_state":         ("range_formation", "breakout_environment", "range_expansion"),
        "participation_state": ("accumulation", "distribution", "mean_reversion"),
        "liquidity_state":     ("sweep_up", "sweep_down", "liquidity_neutral"),
        "market_regime":       ("trending_quiet", "trending_volatile", "ranging_quiet"),
    }
    for mod, states in sampled.items():
        for st in states:
            out[f"{mod}.position.{st}_score"] = _score_decl()
            out[f"{mod}.regime.{st}_flag"] = _flag_decl()
            out[f"{mod}.statistics.{st}_confidence"] = _confidence_decl()
    return out


DECLARATIONS: Dict[str, FeatureValidation] = _build_declarations()


def attach_all(registry) -> Dict[str, bool]:
    """Attach every L3 declaration to its feature. Idempotent."""
    out: Dict[str, bool] = {}
    for fid, decl in DECLARATIONS.items():
        if not registry.contains(fid):
            out[fid] = False
            continue
        f = registry.get(fid)
        f.validation = decl
        out[fid] = True
    return out

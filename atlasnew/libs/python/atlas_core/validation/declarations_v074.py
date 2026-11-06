"""Atlas Validation Framework — v0.7.4 initial declarations.

Attaches FeatureValidation declarations to a representative subset
of the Registry (~20 features across modules). Every future feature
declares its validation profile as part of the DEC-012 workflow;
this file exists only to seed the pattern.

Runs post-Registry-population by side effect at import time.
"""
from __future__ import annotations
from typing import Dict

from .declaration import FeatureValidation, Identity


def _attach(registry, feature_id: str, decl: FeatureValidation) -> bool:
    """Idempotent: attach a declaration to a feature. Returns True if
    the feature exists and the declaration was attached."""
    if not registry.contains(feature_id):
        return False
    f = registry.get(feature_id)
    f.validation = decl
    return True


# ----- Declaration catalogue --------------------------------------------------
DECLARATIONS: Dict[str, FeatureValidation] = {

    # ═══ Bounded features (correlations, ratios, normalised scores) ═══
    "relative_strength.statistics.corr_20": FeatureValidation(
        properties={"bounded": {"lo": -1.0, "hi": 1.0, "tol": 1e-6},
                    "symmetric_in_peer": {"tol": 1e-6}},
        invariants=["6.4", "6.1"],
        assumptions=["≥ 20 bars", "peer aligned to target index"],
        requires_context=["peer"],
        identities=[
            Identity(
                name="corr_of_self_equals_one",
                condition="peer=target",
                expected="corr → 1.0 for the finite tail",
                verifier="peer_equals_target__equals_one_corr",
                tolerance=1e-3,
                golden=False,
            ),
        ],
        complexity="O(n)",
        bridge="l1",
    ),
    "relative_strength.statistics.corr_50": FeatureValidation(
        properties={"bounded": {"lo": -1.0, "hi": 1.0, "tol": 1e-6},
                    "symmetric_in_peer": {"tol": 1e-6}},
        invariants=["6.4"],
        assumptions=["≥ 50 bars", "peer aligned to target index"],
        requires_context=["peer"],
    ),

    # ═══ Identity when peer == target (RS-family goldens as declared identities) ═══
    "relative_strength.magnitude.rs_20": FeatureValidation(
        invariants=["6.4"],
        assumptions=["≥ 20 bars", "close > 0"],
        requires_context=["peer"],
        identities=[
            Identity(
                name="rs_20_equals_one_when_peer_equals_target",
                condition="peer=target (identical series)",
                expected="rs_w ≡ 1.0",
                verifier="peer_equals_target__equals_one",
                tolerance=1e-9,
                golden=True,
            ),
        ],
    ),
    "relative_strength.magnitude.rs_50": FeatureValidation(
        invariants=["6.4"],
        assumptions=["≥ 50 bars", "close > 0"],
        requires_context=["peer"],
        identities=[
            Identity(
                name="rs_50_equals_one_when_peer_equals_target",
                condition="peer=target (identical series)",
                expected="rs_w ≡ 1.0",
                verifier="peer_equals_target__equals_one",
                tolerance=1e-9,
                golden=True,
            ),
        ],
    ),
    "relative_strength.geometry.log_spread": FeatureValidation(
        invariants=["6.4"],
        assumptions=["close > 0", "peer close > 0"],
        requires_context=["peer"],
        identities=[
            Identity(
                name="log_spread_equals_zero_when_peer_equals_target",
                condition="peer=target",
                expected="ln P_a − ln P_b ≡ 0",
                verifier="self_identity__equals_zero",
                tolerance=1e-9,
                golden=True,
            ),
        ],
    ),

    # ═══ Scale-invariant features (Hurst, correlations of returns, RSI) ═══
    "price.geometry.hurst_64": FeatureValidation(
        properties={"bounded": {"lo": 0.0, "hi": 1.0, "tol": 0.05},
                    "scale_invariant": {"tol": 1e-4}},
        invariants=["6.4"],
        assumptions=["≥ 64 bars", "close > 0"],
        complexity="O(n log n)",
        stability={"unstable_when": "σ_returns ≈ 0"},
    ),
    "price.regime.choppiness_30": FeatureValidation(
        properties={"bounded": {"lo": 0.0, "hi": 100.0, "tol": 1e-3},
                    "scale_invariant": {"tol": 1e-4}},
        invariants=["6.4"],
        assumptions=["≥ 30 bars"],
    ),

    # ═══ Fractal Relationships — verify Three-Scale Rule commitment ═══
    "fractal_relationships.regime.self_similarity_score": FeatureValidation(
        properties={"bounded": {"lo": 0.0, "hi": 1.0, "tol": 1e-3}},
        invariants=["6.4"],
        assumptions=["≥ 128 bars"],
        complexity="O(n log n)",
    ),
    "fractal_relationships.regime.self_similarity_flag": FeatureValidation(
        properties={"bounded": {"lo": 0.0, "hi": 1.0, "tol": 0}},
        invariants=["6.4"],
        assumptions=["≥ 128 bars"],
    ),

    # ═══ Trend Alignment — bounded score ═══
    "trend_relationships.regime.directional_consensus_score_20":
        FeatureValidation(
            properties={"bounded": {"lo": -1.0, "hi": 1.0, "tol": 1e-3}},
            invariants=["6.4"],
            assumptions=["≥ 20 bars"],
        ),

    # ═══ Momentum-of-Trend — velocity of a slope; degenerate on constant ═══
    "momentum_of_trend.motion.lr_slope_20_velocity_10": FeatureValidation(
        invariants=["6.4"],
        assumptions=["≥ 30 bars"],
        stability={"unstable_when": "trend slope ≈ 0 (numerical noise dominant)"},
    ),

    # ═══ Volume + volatility — canonical L1 measurement features ═══
    "volume.magnitude.log": FeatureValidation(
        invariants=["6.4"],
        assumptions=["volume > 0"],
    ),
    "volatility.magnitude.cc_20": FeatureValidation(
        properties={"scale_invariant": {"tol": 1e-4}},
        invariants=["6.4"],
        assumptions=["≥ 20 bars"],
        stability={"unstable_when": "constant input → NaN / 0 by construction"},
    ),

    # ═══ Microstructure L1 — body ratio bounded [0, 1] ═══
    "microstructure.geometry.body_over_range": FeatureValidation(
        properties={"bounded": {"lo": 0.0, "hi": 1.0, "tol": 1e-6}},
        invariants=["6.4"],
        assumptions=["high > low"],
    ),

    # ═══ Market Structure — pivot flag family ═══
    "market_structure.regime.pivot_high_flag_k3": FeatureValidation(
        properties={"bounded": {"lo": 0.0, "hi": 1.0, "tol": 0}},
        invariants=["6.4"],
    ),

    # ═══ Liquidity — Amihud ═══
    "liquidity.magnitude.amihud_20": FeatureValidation(
        invariants=["6.4"],
        assumptions=["volume > 0", "close > 0"],
    ),

    # ═══ Price magnitude — canonical primitive; strong universal-gate guarantees ═══
    "price.magnitude.close": FeatureValidation(
        invariants=["6.4"],
        assumptions=[],
        bridge="direct",  # L1 primitive; not consumed via _l1_bridge
    ),
    "price.motion.log_return_1": FeatureValidation(
        properties={"translation_invariant": {"tol": 1e-6}},
        invariants=["6.4"],
        assumptions=["close > 0"],
    ),
}


def attach_all(registry) -> Dict[str, bool]:
    """Attach every declaration in DECLARATIONS to its feature.

    Returns {feature_id: attached_bool}. Missing features (module hasn't
    shipped yet) return False without raising.
    """
    out = {}
    for fid, decl in DECLARATIONS.items():
        out[fid] = _attach(registry, fid, decl)
    return out

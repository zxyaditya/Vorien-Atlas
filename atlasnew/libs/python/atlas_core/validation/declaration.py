"""Atlas Validation Framework — Declaration dataclasses.

Author-supplied metadata attached (optionally) to every FeatureDefinition.
Describes what mathematical guarantees the feature CLAIMS to satisfy.
Proof of those claims is produced by the ValidationRunner and stored in a
ValidationProfile (see profile.py).

See docs/VALIDATION_FRAMEWORK.md for the full specification.
DEC-013 authorises this subsystem.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


# Universal gates every feature is subject to by default. A feature can
# exempt itself from a universal gate only with a written reason.
DEFAULT_UNIVERSAL_GATES: List[str] = [
    "determinism",
    "length_invariance",
    "no_future_leakage",
    "nan_input_behavior",
    "degenerate_constant",
]


@dataclass
class Identity:
    """A named analytical identity the feature claims to satisfy.

    Example (attached to relative_strength.magnitude.rs_20):
        Identity(name="rs_identity_when_peer_equals_target",
                 condition="peer=target",
                 expected="output identically 1.0 after leading window",
                 verifier="peer_equals_target__equals_one",
                 tolerance=1e-9,
                 golden=True)

    `verifier` is an ID into the identity-verifier registry in
    gates/properties.py — the actual code that generates the input,
    computes the output, and compares against the expected pattern.
    `golden=True` marks the identity as a legacy golden test (for the
    backwards-compatible /api/validation/golden endpoint).
    """
    name: str
    condition: str
    expected: str
    verifier: str
    tolerance: float = 1e-9
    golden: bool = False


@dataclass
class FeatureValidation:
    """Declaration block attached to a FeatureDefinition.

    Silence is permission: undeclared properties are not tested.
    Exemption requires written reason: any skip of a universal gate must
    carry an explanation that will live in the profile forever.
    """
    # --- Universal gates ---
    gates: List[str] = field(default_factory=lambda: list(DEFAULT_UNIVERSAL_GATES))
    nan_behavior: str = "propagate"  # "propagate" | "ignore" | "recover"
    degenerate_value: Optional[float] = None  # None = any (typically NaN allowed)
    exemptions: Dict[str, str] = field(default_factory=dict)  # gate_id → reason

    # --- Property gates (opt-in) ---
    # e.g. {"bounded": {"lo": -1.0, "hi": 1.0}, "scale_invariant": {}}
    properties: Dict[str, Dict] = field(default_factory=dict)

    # --- Analytical identities ---
    identities: List[Identity] = field(default_factory=list)

    # --- Book 1 invariants the feature commits to (e.g. "6.4", "6.1") ---
    invariants: List[str] = field(default_factory=list)

    # --- Author-stated preconditions (e.g. "close > 0", "len(df) >= 100") ---
    assumptions: List[str] = field(default_factory=list)

    # --- Complexity + numerical-stability metadata ---
    complexity: str = "O(n)"
    stability: Dict[str, str] = field(default_factory=dict)

    # --- Multi-symbol context requirement (DEC-007) ---
    requires_context: List[str] = field(default_factory=list)  # e.g. ["peer"]

    # --- Layer-bridge declaration (forward-compatibility with L3+) ---
    # "l1" (via _l1_bridge) | "l2" (future _l2_bridge, Session 8+) |
    # "l3" (future) | "direct" (only permitted for L1 primitive features).
    bridge: str = "l1"

    def golden_identities(self) -> List[Identity]:
        """Subset of identities flagged as legacy golden tests."""
        return [i for i in self.identities if i.golden]

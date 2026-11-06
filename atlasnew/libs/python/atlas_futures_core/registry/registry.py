"""The Registry — simple feature store.

Per user directive: minimal metadata surface. Keeps a silent duplicate-
formula check as a mechanical Rule-1 safety net (no user-facing cost).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional, Any
import hashlib


LAYERS = {1: "Measurement", 2: "Relationships", 3: "Market Understanding",
          4: "Representation"}

PERSPECTIVES = [
    "Magnitude", "Motion", "Geometry", "Relative", "Position",
    "Statistics", "Distribution", "Entropy", "Expansion",
    "Clustering", "Regime",
]


@dataclass
class FeatureDefinition:
    id: str
    name: str
    layer: int
    module: str
    perspective: str
    family: str
    definition: str
    formula: str
    interpretation: str
    inputs: List[str]
    params: Dict[str, Any] = field(default_factory=dict)
    complexity: str = "O(n)"
    fn: Optional[Callable] = None
    # v0.7.4 — optional Validation Framework declaration (DEC-013).
    # See atlas_core/validation/declaration.py::FeatureValidation.
    # Backwards-compatible: features that predate the framework carry
    # validation=None and are subject only to universal gates.
    validation: Optional[Any] = None

    @property
    def formula_hash(self) -> str:
        """Stable 12-char SHA-1 of formula+params. Used by the
        Validation Framework registry-wide gate unique_formula_hash."""
        payload = (self.formula or "") + str(sorted((self.params or {}).items()))
        return hashlib.sha1(payload.encode()).hexdigest()[:12]

    def to_public_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("fn", None)
        # Replace the raw validation dataclass with a lightweight summary;
        # the full profile is served via /api/validation/profile/{id}.
        if d.get("validation") is not None and self.validation is not None:
            decl = self.validation
            d["validation"] = {
                "gates": list(getattr(decl, "gates", []) or []),
                "properties": dict(getattr(decl, "properties", {}) or {}),
                "invariants": list(getattr(decl, "invariants", []) or []),
                "assumptions": list(getattr(decl, "assumptions", []) or []),
                "exemptions": dict(getattr(decl, "exemptions", {}) or {}),
                "nan_behavior": getattr(decl, "nan_behavior", "propagate"),
                "requires_context": list(getattr(decl, "requires_context", []) or []),
                "bridge": getattr(decl, "bridge", "l1"),
                "n_identities": len(getattr(decl, "identities", []) or []),
            }
        return d


class _Registry:
    def __init__(self) -> None:
        self._features: Dict[str, FeatureDefinition] = {}
        self._math_seen: Dict[str, str] = {}  # silent Rule-1 guardrail

    def register(self, feature: FeatureDefinition) -> None:
        # Silent uniqueness guardrail — only rejects EXACT formula+params duplicates
        # within the same module. Zero user-facing complexity.
        key = f"{feature.module}:" + hashlib.sha1(
            (feature.formula + str(sorted(feature.params.items()))).encode()
        ).hexdigest()[:12]
        if key in self._math_seen and self._math_seen[key] != feature.id:
            raise ValueError(
                f"Duplicate mathematical concept in '{feature.module}': "
                f"'{feature.id}' collides with '{self._math_seen[key]}'"
            )
        self._math_seen[key] = feature.id
        self._features[feature.id] = feature

    def get(self, feature_id: str) -> FeatureDefinition:
        return self._features[feature_id]

    def contains(self, feature_id: str) -> bool:
        return feature_id in self._features

    def all(self) -> List[FeatureDefinition]:
        return list(self._features.values())

    def filter(self, **criteria) -> List[FeatureDefinition]:
        out = self.all()
        for k, v in criteria.items():
            if v is None:
                continue
            out = [f for f in out if getattr(f, k, None) == v]
        return out

    def stats(self) -> Dict[str, Any]:
        feats = self.all()
        by_layer, by_module, by_persp, by_family = {}, {}, {}, {}
        for f in feats:
            by_layer[f.layer] = by_layer.get(f.layer, 0) + 1
            by_module[f.module] = by_module.get(f.module, 0) + 1
            by_persp[f.perspective] = by_persp.get(f.perspective, 0) + 1
            key = f"{f.module}/{f.perspective}/{f.family}"
            by_family[key] = by_family.get(key, 0) + 1
        return {"total": len(feats), "by_layer": by_layer,
                "by_module": by_module, "by_perspective": by_persp,
                "by_family": by_family}


registry = _Registry()

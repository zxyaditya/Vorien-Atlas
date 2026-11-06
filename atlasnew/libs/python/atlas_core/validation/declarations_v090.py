"""Atlas Validation Framework — v0.9.0 Layer 4 declarations.

- `orthogonality` gate on the 5 embedding principal components.
- `bounded[0, 1]` on state_encodings position/clustering features.
- `bounded[0, 1]` on meta_features regime scores.
"""
from __future__ import annotations
from typing import Dict

from .declaration import FeatureValidation


def _pc_decl() -> FeatureValidation:
    return FeatureValidation(
        properties={"orthogonality": {"max_abs_corr": 0.35}},
        invariants=["6.1", "6.4"],
        assumptions=["rolling PCA components should be near-orthogonal by construction"],
        bridge="l4",
    )


def _bounded01_decl() -> FeatureValidation:
    return FeatureValidation(
        properties={"bounded": {"lo": 0.0, "hi": 1.0, "tol": 1e-9}},
        invariants=["6.1", "6.4"],
        bridge="l4",
    )


def _build_declarations() -> Dict[str, FeatureValidation]:
    out: Dict[str, FeatureValidation] = {}
    # Embedding PCs (orthogonality gate — one declaration covers the family
    # since the gate auto-derives the family from the module+family label).
    out["embeddings.geometry.pc1"] = _pc_decl()
    out["embeddings.geometry.pc2"] = _pc_decl()
    out["embeddings.geometry.pc3"] = _pc_decl()
    out["embeddings.geometry.pc4"] = _pc_decl()
    out["embeddings.geometry.pc5"] = _pc_decl()
    # Meta-features bounded to [0, 1]:
    for fid in ("meta_features.regime.l3_family_agreement_score",
                "meta_features.position.l3_active_family_fraction",
                "meta_features.position.l3_confidence_mean_rank_100"):
        out[fid] = _bounded01_decl()
    # State-encoding rank features bounded to [0, 1]:
    for short in ("consensus_score_20", "self_similarity",
                  "hurst_64", "choppiness_14", "mr_confidence"):
        out[f"state_encodings.position.rank100_{short}"] = _bounded01_decl()
    return out


DECLARATIONS: Dict[str, FeatureValidation] = _build_declarations()


def attach_all(registry) -> Dict[str, bool]:
    out: Dict[str, bool] = {}
    for fid, decl in DECLARATIONS.items():
        if not registry.contains(fid):
            out[fid] = False
            continue
        f = registry.get(fid)
        f.validation = decl
        out[fid] = True
    return out

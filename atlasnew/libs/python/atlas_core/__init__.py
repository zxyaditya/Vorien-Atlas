"""Atlas Core — Mathematical Market Representation Framework.

Book 1 governs. This package is Layer 1-4 pure. It contains no
prediction, no execution, no opinions about trading. It only
measures, relates, contextualizes, and represents.

Book 1 Invariant 5.6 enforced: no machine-learning models live here.
ML (XGBoost/RF/etc.) lives in decision_engine.ml (Layer-5 consumer).

Public interface:
    - registry: the source-of-truth for features
    - engines: domain-neutral mathematical machinery
    - layers: the five conceptual layers (L1 shipped; L2 partial as of v0.6)
    - compute: feature computation orchestrator
"""
from atlas_core.registry.registry import registry
from atlas_core.compute.compute import compute_features, list_features

# v0.7.4 — Validation Framework (DEC-013). Attach declarations to the
# ~20 representative features seeded in this ship. Every future feature
# declares its validation profile as part of the DEC-012 workflow.
# See docs/VALIDATION_FRAMEWORK.md.
try:
    # Import layers first so all features register before we attach.
    from atlas_core import layers as _layers  # noqa: F401
    from atlas_core.validation.declarations_v074 import attach_all as _attach_v074
    from atlas_core.validation.declarations_v080 import attach_all as _attach_v080
    from atlas_core.validation.declarations_v090 import attach_all as _attach_v090
    _attach_v074(registry)
    _attach_v080(registry)
    _attach_v090(registry)
except Exception as _e:                       # pragma: no cover
    # Framework declarations are best-effort at import; never break Registry boot.
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "validation declarations attach_all failed: %s", _e)

__all__ = ["registry", "compute_features", "list_features"]
__version__ = "1.0.0"

"""Layer 4 — Representation.

Book 1 Ch. 5: "How should this market understanding be represented
for intelligent systems?" See docs/L4_REPRESENTATION.md and DEC-016.
"""
from __future__ import annotations
from . import cross_module_interactions        # noqa: F401
from . import meta_features                    # noqa: F401
from . import state_encodings                  # noqa: F401
from . import multi_scale_representations      # noqa: F401
from . import embeddings                       # noqa: F401

# The L4 → future Learning System handshake. Stable pointer to the
# embedding features so future L5 code (analogue z-space v2, learned
# voter conditioning) does not have to re-hunt them.
L4_EMBEDDING_IDS = [
    "embeddings.geometry.pc1", "embeddings.geometry.pc2",
    "embeddings.geometry.pc3", "embeddings.geometry.pc4",
    "embeddings.geometry.pc5",
    "embeddings.statistics.evr_1", "embeddings.statistics.evr_2",
    "embeddings.statistics.evr_3", "embeddings.statistics.evr_4",
    "embeddings.statistics.evr_5",
]

"""Layer 2 — Relationships (Book 1, Chapter 5).

Layer 2 modules consume Layer 1 measurements and study relationships
between them. Information flows upward (Invariant 6.4): L2 never
re-measures raw OHLCV — it goes through the Registry via the L1 bridge.

Modules shipped in v0.6:
  • market_structure       (swings, HH/HL/LH/LL, BOS, CHoCH, ...)
  • swing_dynamics         (amplitude, interval, cadence)
  • compression_expansion  (short/long window ratios of vol, range)
  • relative_strength      (pairwise vs peer via context)

Added in v0.7:
  • momentum_of_trend      (temporal derivative of L1 trend measurements)
  • trend_relationships    (cross-source/cross-scale agreement of trend measurements)
  • fractal_relationships  (self-similarity / scale-invariance across ≥3 scales)
"""
from atlas_core.layers.l2_relationships import market_structure  # noqa: F401
from atlas_core.layers.l2_relationships import swing_dynamics    # noqa: F401
from atlas_core.layers.l2_relationships import compression_expansion  # noqa: F401
from atlas_core.layers.l2_relationships import relative_strength # noqa: F401
from atlas_core.layers.l2_relationships import momentum_of_trend # noqa: F401
from atlas_core.layers.l2_relationships import trend_relationships       # noqa: F401
from atlas_core.layers.l2_relationships import fractal_relationships     # noqa: F401
from atlas_core.layers.l2_relationships import _l1_bridge                # noqa: F401
from atlas_core.layers.l2_relationships import stat_arb_features         # noqa: F401
from atlas_core.layers.l2_relationships import derivatives               # noqa: F401

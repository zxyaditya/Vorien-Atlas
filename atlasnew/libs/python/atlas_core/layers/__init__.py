"""Atlas layers — conceptual hierarchy.

  L1 Measurement          — shipped (v0.6)
  L2 Relationships        — shipped (v0.6 → v0.7.3, 7 modules)
  L3 Market Understanding — shipped (v0.8.0, 5 modules)
  L4 Representation       — shipped (v0.9.0, 5 modules)

Load order matters: higher layers import lower ones via each layer's
own bridge (DEC-006, DEC-014, DEC-016).
"""
from atlas_core.layers import l1_measurement            # noqa: F401
from atlas_core.layers import l2_relationships          # noqa: F401
from atlas_core.layers import l3_market_understanding   # noqa: F401
from atlas_core.layers import l4_representation         # noqa: F401

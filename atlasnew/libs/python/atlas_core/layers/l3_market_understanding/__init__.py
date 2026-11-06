"""Layer 3 — Market Understanding.

Book 1 Ch. 5: "What market environment currently exists?"

Contextual states built from many interacting L2 relationships.
See docs/L3_MARKET_UNDERSTANDING.md for the milestone specification
and DEC-014 (access contract) + DEC-015 (state-kernel primitives).

All modules below are imported for their registration side-effects.
"""
from __future__ import annotations

# Side-effect imports — each module registers its features into the Registry.
from . import trend_state           # noqa: F401
from . import range_state           # noqa: F401
from . import participation_state   # noqa: F401
from . import liquidity_state       # noqa: F401
from . import market_regime         # noqa: F401

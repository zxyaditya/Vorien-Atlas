"""State encodings — Layer 4.

Book 1 Ch. 5 exemplar: state encodings. Deterministic (label-free)
encodings. See docs/L4_REPRESENTATION.md §6.3.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l4_representation._layer_bridge import (
    l1_series, l2_series, l3_series,
)
from atlas_core.layers.l4_representation._representation_kernel import (
    quantile_bin, rolling_rank,
)

MODULE = "state_encodings"


def _reg(id_, name, perspective, family, definition, formula, interp,
         fn, inputs, params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=4, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=params or {}, complexity=complexity, fn=fn,
    ))


# --- Ordinal (quantile-bin, 5 bins) encodings of curated L2/L1 features ---
_ORDINAL_INPUTS = [
    ("L2:trend_relationships.regime.directional_consensus_score_20",
     "consensus_score_20"),
    ("L2:relative_strength.magnitude.rs_20", "rs_20"),
    ("L1:price.regime.adx_14", "adx_14"),
    ("L1:volatility.expansion.short_long_ratio", "vol_short_long"),
    ("L1:volume.regime.pv_confirmation_20", "pv_confirmation"),
    ("L2:momentum_of_trend.motion.lr_slope_20_velocity_20", "slope_vel_20"),
]

for tag, short in _ORDINAL_INPUTS:
    src = tag.split(":", 1)[1]
    def _ord_fn(df, s=src, t=tag):
        s_ser = l2_series(df, s) if t.startswith("L2:") else l1_series(df, s)
        return quantile_bin(s_ser, k=5, lookback=100)
    _reg(f"{MODULE}.clustering.ordinal5_{short}",
         f"Ordinal (5-bin) encoding of {short}", "Clustering", "ordinal",
         f"Rolling 5-bin quantile encoding of {src} over 100 bars.",
         f"quantile_bin({src}, k=5, lookback=100)",
         f"Discretised {short} for ML consumers; label-free.",
         _ord_fn, inputs=[tag],
         params={"k": 5, "lookback": 100, "source": src})

# --- Percentile-rank encodings ---
_RANK_INPUTS = [
    ("L2:trend_relationships.regime.directional_consensus_score_20",
     "consensus_score_20"),
    ("L2:fractal_relationships.regime.self_similarity_score", "self_similarity"),
    ("L1:price.geometry.hurst_64", "hurst_64"),
    ("L1:price.regime.choppiness_14", "choppiness_14"),
    ("L3:market_regime.statistics.active_state_confidence", "mr_confidence"),
]

for tag, short in _RANK_INPUTS:
    src = tag.split(":", 1)[1]
    layer = tag.split(":", 1)[0]
    def _rank_fn(df, s=src, ly=layer):
        if ly == "L1":  s_ser = l1_series(df, s)
        elif ly == "L2": s_ser = l2_series(df, s)
        else:            s_ser = l3_series(df, s)
        return rolling_rank(s_ser, window=100)
    _reg(f"{MODULE}.position.rank100_{short}",
         f"Rolling 100-bar percentile rank of {short}", "Position", "rank",
         f"Percentile rank in [0, 1] of {src} over 100 bars.",
         f"rolling_rank({src}, 100)",
         f"Position of {short} vs its recent history.",
         _rank_fn, inputs=[tag], params={"window": 100, "source": src})

# --- L3 module code one-hot NOT re-shipped: L3 already publishes them ---
# --- L3 direction-family ordinal (custom) ---
def _ts_direction(df):
    c = l3_series(df, "trend_state.regime.active_state_code").fillna(0).astype(int)
    # 0=none, 1=continuation, 2=exhaustion, 3=reversal → severity 0/1/2/3
    return c.astype(float)
_reg(f"{MODULE}.clustering.trend_state_ordinal_severity",
     "Trend state ordinal severity", "Clustering", "state",
     "Ordinal severity of trend_state active code (continuation=1, exhaustion=2, reversal=3).",
     "active_state_code(trend_state)",
     "Severity ordering treating the L3 code as ordinal, not categorical.",
     _ts_direction,
     inputs=["L3:trend_state.regime.active_state_code"],
     params={"source": "trend_state"})

def _range_ordinal(df):
    return l3_series(df, "range_state.regime.active_state_code").fillna(0).astype(float)
_reg(f"{MODULE}.clustering.range_state_ordinal_severity",
     "Range state ordinal severity", "Clustering", "state",
     "Ordinal severity of range_state active code.",
     "active_state_code(range_state)", "Ordinal treatment of range family.",
     _range_ordinal,
     inputs=["L3:range_state.regime.active_state_code"],
     params={"source": "range_state"})

# --- Composite state encoding: L3 codes joined into a base-6 integer ---
def _state_composite(df):
    modules = ["trend_state", "range_state", "participation_state",
               "liquidity_state", "market_regime"]
    codes = [l3_series(df, f"{m}.regime.active_state_code").fillna(0).astype(int)
             for m in modules]
    combo = codes[0] * 1 + codes[1] * 6 + codes[2] * 36 + codes[3] * 216 + codes[4] * 1296
    return combo.astype(float)
_reg(f"{MODULE}.clustering.l3_composite_code",
     "L3 composite code (base-6)", "Clustering", "state",
     "Compound integer encoding of the 5 L3 active_state_codes.",
     "c1 + 6*c2 + 36*c3 + 216*c4 + 1296*c5",
     "Single integer identifying the joint L3 state at bar t.",
     _state_composite,
     inputs=["L3:*.regime.active_state_code"])

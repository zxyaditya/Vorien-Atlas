"""Embeddings — Layer 4.

Book 1 Ch. 5 exemplar: feature embeddings + dimensionality reduction.
Rolling deterministic PCA of a curated 20-feature input matrix onto
the top-5 principal components. Roll-forward, no future leakage.
See docs/L4_REPRESENTATION.md §6.5.

This module is the **L4 → future Learning System handshake**: the
5 PC time series + 5 EVR time series constitute the compact z-space
that the analogue-engine v2 (v1.0+) will consume.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l4_representation._layer_bridge import (
    l1_series, l2_series, l3_series,
)
from atlas_core.layers.l4_representation._representation_kernel import rolling_pca

MODULE = "embeddings"
K = 5
LOOKBACK = 250

# Curated 20-feature input matrix (mix of L1, L2, L3 numerics; chosen for
# information diversity across perspectives, not by correlation).
EMB_INPUTS = [
    # L1 measurements
    ("L1", "price.motion.log_return_10"),
    ("L1", "price.motion.log_return_20"),
    ("L1", "price.motion.lr_slope_50"),
    ("L1", "price.geometry.hurst_64"),
    ("L1", "price.regime.adx_14"),
    ("L1", "price.regime.choppiness_14"),
    ("L1", "price.statistics.zscore_20"),
    ("L1", "volatility.magnitude.std_20"),
    ("L1", "volatility.regime.tercile_200"),
    ("L1", "volume.regime.signed_ema_20"),
    ("L1", "volume.position.pct_rank_100"),
    ("L1", "liquidity.regime.tercile_200"),
    ("L1", "microstructure.expansion.execution_imbalance_20"),
    # L2 relationships
    ("L2", "trend_relationships.regime.directional_consensus_score_20"),
    ("L2", "fractal_relationships.regime.self_similarity_score"),
    ("L2", "market_structure.motion.bos_k5"),
    ("L2", "momentum_of_trend.motion.lr_slope_20_velocity_20"),
    # L3 states
    ("L3", "trend_state.statistics.active_state_confidence"),
    ("L3", "market_regime.statistics.active_state_confidence"),
    ("L3", "participation_state.statistics.active_state_confidence"),
]


def _reg(id_, name, perspective, family, definition, formula, interp,
         fn, inputs, params=None, complexity="O(n·W·d²)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=4, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=params or {}, complexity=complexity, fn=fn,
    ))


# Cache the (pcs, evr) DataFrames per-df to avoid recomputing PCA five
# times when the five PC feature functions are each called.
_PCA_CACHE: dict = {}


def _get_pca(df: pd.DataFrame):
    key = id(df)
    if key in _PCA_CACHE:
        return _PCA_CACHE[key]
    cols = {}
    for layer, fid in EMB_INPUTS:
        if layer == "L1":
            s = l1_series(df, fid)
        elif layer == "L2":
            s = l2_series(df, fid)
        else:
            s = l3_series(df, fid)
        cols[fid] = s
    M = pd.DataFrame(cols, index=df.index)
    pcs, evr = rolling_pca(M, k=K, lookback=LOOKBACK)
    _PCA_CACHE[key] = (pcs, evr)
    # Small LRU-ish cap so long runs don't leak memory.
    if len(_PCA_CACHE) > 8:
        _PCA_CACHE.pop(next(iter(_PCA_CACHE)))
    return _PCA_CACHE[key]


for i in range(1, K + 1):
    def _pc_fn(df, ii=i):
        pcs, _ = _get_pca(df)
        return pcs[f"pc{ii}"]
    _reg(f"{MODULE}.geometry.pc{i}",
         f"Rolling PCA principal component {i}",
         "Geometry", "pca_component",
         f"Projection of the current bar's standardised input vector "
         f"onto the {i}-th principal component of a rolling {LOOKBACK}-bar window.",
         f"Vt[{i}] @ z(x_t)   (over trailing {LOOKBACK} bars)",
         f"Compact coordinate {i} of the market state in a 5-dim z-space.",
         _pc_fn,
         inputs=[t for _, t in EMB_INPUTS],
         params={"k_index": i, "lookback": LOOKBACK,
                 "input_count": len(EMB_INPUTS)},
         complexity=f"O(n·{LOOKBACK}·{len(EMB_INPUTS)}²)")

for i in range(1, K + 1):
    def _evr_fn(df, ii=i):
        _, evr = _get_pca(df)
        return evr[f"evr_{ii}"]
    _reg(f"{MODULE}.statistics.evr_{i}",
         f"Rolling PCA explained-variance ratio {i}",
         "Statistics", "pca_evr",
         f"Explained-variance ratio of principal component {i} in a "
         f"rolling {LOOKBACK}-bar window.",
         f"σ²_{{{i}}} / Σσ²   (over trailing {LOOKBACK} bars)",
         f"How much of the variance PC{i} captures at bar t.",
         _evr_fn,
         inputs=[t for _, t in EMB_INPUTS],
         params={"k_index": i, "lookback": LOOKBACK},
         complexity=f"O(n·{LOOKBACK}·{len(EMB_INPUTS)}²)")


def _clear_pca_cache():
    """Called by the orchestrator via _layer_bridge.clear_cache().

    The bridge module's clear_cache() flushes only the bridge caches;
    we hook _PCA_CACHE clearing into it explicitly.
    """
    _PCA_CACHE.clear()

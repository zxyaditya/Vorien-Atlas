"""L3 Layer Bridge — the ONLY sanctioned way for L3 to access L1/L2 values.

DEC-014 (v0.8.0):
  L3 modules access lower layers exclusively through this parallel
  bridge. This module is L3-owned and does NOT share a cache with
  `l2_relationships._l1_bridge`. Each layer owns its own cache so
  cross-layer interference is architecturally impossible.

Usage inside an L3 feature function:

    from atlas_core.layers.l3_market_understanding._layer_bridge import (
        l1_series, l2_series,
    )
    consensus = l2_series(df, "trend_relationships.regime.directional_consensus_score_20")
    hurst     = l1_series(df, "price.geometry.hurst_64")

Both caches are keyed on (id(df), feature_id) and flushed on entry+exit
of every compute_features call by the orchestrator (DEC-011).
"""
from __future__ import annotations
import pandas as pd
from typing import Dict, Optional

from atlas_core.registry.registry import registry

class _AtlasContextDict(dict):
    def __eq__(self, other):
        return self is other

_L1_CACHE: Dict = {}
_L2_CACHE: Dict = {}
_CACHE_MAX = 128  # small LRU-ish cap; identity-keyed


def _key(df, feature_id):
    return (id(df), feature_id)


def _evict(cache: Dict) -> None:
    if len(cache) > _CACHE_MAX:
        cache.pop(next(iter(cache)))


def _compute_and_align(df: pd.DataFrame, feature_id: str) -> pd.Series:
    """Look up feature in the Registry, run its fn, align to df.index.

    Soft-fail contract: returns an all-NaN series with df.index if the
    feature is missing, has no callable, or raises. Never raises up to
    the caller — matches DEC-007 discipline.
    """
    try:
        f = registry.get(feature_id)
    except KeyError:
        return pd.Series(float("nan"), index=df.index, dtype=float)
    if f.fn is None:
        return pd.Series(float("nan"), index=df.index, dtype=float)
    try:
        s = pd.Series(f.fn(df)).astype(float)
    except Exception:
        return pd.Series(float("nan"), index=df.index, dtype=float)
    if len(s) == len(df.index):
        s.index = df.index
    elif len(s) < len(df.index):
        # Pad head with NaN so caller can safely align on df.index.
        out = pd.Series(float("nan"), index=df.index, dtype=float)
        out.iloc[-len(s):] = s.values
        s = out
    else:
        s = s.iloc[-len(df.index):]
        s.index = df.index
    return s


def l1_series(df: pd.DataFrame, feature_id: str) -> pd.Series:
    """Return the L1 feature's series for this df. Cached."""
    k = _key(df, feature_id)
    if k in _L1_CACHE:
        return _L1_CACHE[k]
    s = _compute_and_align(df, feature_id)
    _evict(_L1_CACHE)
    _L1_CACHE[k] = s
    return s


def l2_series(df: pd.DataFrame, feature_id: str,
              context: Optional[Dict[str, pd.DataFrame]] = None) -> pd.Series:
    """Return the L2 feature's series for this df. Cached.

    Honours df.attrs['_atlas_context'] if the L2 feature requires peer
    (DEC-007). If ``context`` is supplied, it is temporarily attached
    to df.attrs for the duration of this call, then restored.
    """
    k = _key(df, feature_id)
    if k in _L2_CACHE:
        return _L2_CACHE[k]
    prior_ctx = df.attrs.get("_atlas_context") if hasattr(df, "attrs") else None
    try:
        if context is not None and hasattr(df, "attrs"):
            df.attrs["_atlas_context"] = _AtlasContextDict(context)
        s = _compute_and_align(df, feature_id)
    finally:
        if context is not None and hasattr(df, "attrs"):
            if prior_ctx is None:
                df.attrs.pop("_atlas_context", None)
            else:
                df.attrs["_atlas_context"] = prior_ctx
    _evict(_L2_CACHE)
    _L2_CACHE[k] = s
    return s


def clear_cache() -> None:
    """Flush both caches. Called by the compute orchestrator on entry+exit."""
    _L1_CACHE.clear()
    _L2_CACHE.clear()

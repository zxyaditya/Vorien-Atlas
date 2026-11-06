"""L4 Layer Bridge — the ONLY sanctioned way for L4 to access L1/L2/L3.

DEC-016 (v0.9.0). Parallel-bridge principle continued from DEC-014.
Each layer owns its cache; no cross-layer coupling. Flushed by the
compute orchestrator on entry+exit of every compute_features call.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

class _AtlasContextDict(dict):
    def __eq__(self, other):
        return self is other
from typing import Dict, Optional

from atlas_core.registry.registry import registry

_L1_CACHE: Dict = {}
_L2_CACHE: Dict = {}
_L3_CACHE: Dict = {}
_CACHE_MAX = 128


def _key(df, feature_id): return (id(df), feature_id)


def _evict(c: Dict) -> None:
    if len(c) > _CACHE_MAX:
        c.pop(next(iter(c)))


def _compute_and_align(df: pd.DataFrame, feature_id: str) -> pd.Series:
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
        out = pd.Series(float("nan"), index=df.index, dtype=float)
        out.iloc[-len(s):] = s.values
        s = out
    else:
        s = s.iloc[-len(df.index):]
        s.index = df.index
    return s


def l1_series(df: pd.DataFrame, feature_id: str) -> pd.Series:
    k = _key(df, feature_id)
    if k in _L1_CACHE:
        return _L1_CACHE[k]
    s = _compute_and_align(df, feature_id)
    _evict(_L1_CACHE); _L1_CACHE[k] = s
    return s


def l2_series(df: pd.DataFrame, feature_id: str,
              context: Optional[Dict[str, pd.DataFrame]] = None) -> pd.Series:
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
    _evict(_L2_CACHE); _L2_CACHE[k] = s
    return s


def l3_series(df: pd.DataFrame, feature_id: str) -> pd.Series:
    k = _key(df, feature_id)
    if k in _L3_CACHE:
        return _L3_CACHE[k]
    s = _compute_and_align(df, feature_id)
    _evict(_L3_CACHE); _L3_CACHE[k] = s
    return s


def clear_cache() -> None:
    """Flush all three L4 bridge caches. Called by the orchestrator.

    Also flushes the embeddings module's rolling-PCA cache which is
    keyed on id(df) and would otherwise leak between compute calls.
    """
    _L1_CACHE.clear(); _L2_CACHE.clear(); _L3_CACHE.clear()
    try:
        from atlas_core.layers.l4_representation import embeddings as _emb
        _emb._clear_pca_cache()
    except Exception:
        pass  # best-effort; embeddings may not yet be imported at first flush.

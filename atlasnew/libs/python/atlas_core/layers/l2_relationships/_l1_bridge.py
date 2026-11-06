"""L1 Bridge — the only sanctioned way for L2 to access L1 values.

Book 1 Invariant 6.4: information always flows upward. L2 must consume
L1 through the Registry — not by re-implementing L1 math and not by
reaching into L1 module internals. This bridge fulfils that contract.

Usage inside an L2 feature function:

    from atlas_core.layers.l2_relationships._l1_bridge import l1_series
    close = l1_series(df, "price.magnitude.close")
    hurst = l1_series(df, "price.geometry.hurst_64")

Cache is keyed on id(df) so identical DataFrames within a single compute
call don't recompute the same L1 feature multiple times.
"""
from __future__ import annotations
import pandas as pd
from typing import Dict
from atlas_core.registry.registry import registry

_CACHE: Dict = {}
_CACHE_MAX = 64  # small LRU-ish cap; identity-keyed


def _cache_key(df, feature_id):
    return (id(df), feature_id)


def l1_series(df: pd.DataFrame, feature_id: str) -> pd.Series:
    """Return the registered feature's series for this df. Cached."""
    key = _cache_key(df, feature_id)
    if key in _CACHE:
        return _CACHE[key]
    try:
        f = registry.get(feature_id)
    except KeyError:
        return pd.Series(index=df.index, dtype=float)
    if f.fn is None:
        return pd.Series(index=df.index, dtype=float)
    s = pd.Series(f.fn(df)).astype(float)
    s.index = df.index[:len(s)] if len(s) <= len(df.index) else s.index
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = s
    return s


def clear_cache():
    _CACHE.clear()

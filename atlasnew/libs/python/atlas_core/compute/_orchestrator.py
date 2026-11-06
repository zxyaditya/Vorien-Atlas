"""Feature computation orchestrator (v0.6 — with L2 multi-symbol context).

Context is an optional dict of {name: pd.DataFrame} attached to df.attrs
under key '_atlas_context' before iteration. L2 features that need a
peer read df.attrs['_atlas_context']['peer']. Backward-compatible: any
feature not needing context ignores it.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import List, Optional, Dict
import logging
import hashlib
import time

log = logging.getLogger("atlas_core")
_compute_cache = {}
_series_cache = {}
from atlas_core.registry.registry import registry, FeatureDefinition

# Side-effect: load all layers so features register.
from atlas_core.layers import l1_measurement, l2_relationships, l3_market_understanding, l4_representation  # noqa: F401
# Bridge cache used by L2 → L1 lookups; must be flushed per compute call
# because it is keyed on id(df) and Python can recycle object ids after GC
# (would otherwise leak cached L1 series across unrelated DataFrames).
from atlas_core.layers.l2_relationships import _l1_bridge
# L3 owns its own parallel bridge (DEC-014, v0.8.0). Same identity-keyed
# cache mechanics; flushed on entry+exit of every compute call.
from atlas_core.layers.l3_market_understanding import _layer_bridge as _l3_bridge
# L4 owns its own parallel bridge (DEC-016, v0.9.0).
from atlas_core.layers.l4_representation import _layer_bridge as _l4_bridge


class _AtlasContextDict(dict):
    def __eq__(self, other):
        return self is other


def list_features(**criteria) -> List[FeatureDefinition]:
    return registry.filter(**criteria)


def compute_features(df: pd.DataFrame,
                     feature_ids: Optional[List[str]] = None,
                     context: Optional[Dict[str, pd.DataFrame]] = None
                     ) -> pd.DataFrame:
    """Compute requested features (or all) on an OHLCV DataFrame.

    context: optional dict of aux DataFrames (peers, index, etc.) used
    by L2/L4 features. Attached to df.attrs['_atlas_context'] for the
    duration of the compute. Backward-compatible — defaults to None.
    """
    global _compute_cache
    df_hash = hashlib.md5(pd.util.hash_pandas_object(df, index=True).values).hexdigest()
    context_hash = ""
    if context:
        ctx_hashes = []
        for k, v in context.items():
            if isinstance(v, pd.DataFrame):
                ctx_hashes.append(k + hashlib.md5(pd.util.hash_pandas_object(v, index=True).values).hexdigest())
            else:
                ctx_hashes.append(k + str(v))
        context_hash = hashlib.md5("".join(ctx_hashes).encode()).hexdigest()
    
    cache_key = (df_hash, tuple(feature_ids) if feature_ids else None, context_hash)
    if cache_key in _compute_cache:
        entry = _compute_cache[cache_key]
        if time.time() - entry["t"] < 60:
            _l1_bridge.clear_cache()
            _l3_bridge.clear_cache()
            _l4_bridge.clear_cache()
            return entry["df"].copy()

    # Flush the L1 bridge cache: it keys on id(df), which Python can
    # recycle across garbage-collected DataFrames. Without this flush
    # a previous DataFrame's cached L1 series could be silently reused
    # for a different DataFrame in the same process (Book 1 purity
    # violation observed during regression testing). Clearing per call
    # is safe because the cache's only purpose is intra-call
    # de-duplication of L1 lookups by many L2 features.
    

    # v0.7.4 — DEC-007 context isolation. ALWAYS overwrite df.attrs
    # (do not leave stale context from a previous call). The Validation
    # Framework's context_isolation gate surfaced a leak here where a
    # prior compute_features(df, context={...}) left df.attrs populated,
    # and a subsequent compute_features(df, context=None) still saw the
    # peer via the leaked attrs. This violates the soft-fail contract.
    if not hasattr(df, "attrs") or df.attrs is None:
        df.attrs = {}
    else:
        df.attrs = dict(df.attrs)   # defensive copy

    if context is not None:
        df.attrs["_atlas_context"] = _AtlasContextDict(context)
    else:
        # Explicitly clear any stale context from a prior call.
        df.attrs.pop("_atlas_context", None)

    if feature_ids is None:
        feats = registry.all()
    else:
        feats = []
        for fid in feature_ids:
            try:
                feats.append(registry.get(fid))
            except KeyError:
                continue

    import concurrent.futures
    import time as _time

    cols = {}
    
    def _compute_feat(f):
        if f.fn is None:
            return f.id, None
            
        series_key = (df_hash, context_hash, f.id)
        if series_key in _series_cache:
            entry = _series_cache[series_key]
            # Keep feature cached for 30 minutes (1800 seconds)
            if _time.time() - entry["t"] < 1800:
                return f.id, entry["arr"].copy()
                
        try:
            series = f.fn(df)
            arr = np.asarray(pd.Series(series).values, dtype=float)
            if len(arr) != len(df):
                arr = np.full(len(df), np.nan)
                
            if len(_series_cache) > 5000:
                _series_cache.clear()
            _series_cache[series_key] = {"t": _time.time(), "arr": arr.copy()}
            return f.id, arr
        except Exception as e:
            if isinstance(e, KeyError):
                log.debug(f"Feature {f.id} computation failed missing column: {e}")
            else:
                log.error(f"Feature {f.id} computation failed: {type(e).__name__}: {e}")
            return f.id, np.full(len(df), np.nan)

    print(f"[Orchestrator] Starting ThreadPoolExecutor for {len(feats)} features...", flush=True)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_compute_feat, f): f for f in feats}
            for future in concurrent.futures.as_completed(futures):
                f_id, arr = future.result()
                if arr is not None:
                    cols[f_id] = arr
    except Exception as e:
        log.exception(f"compute_features orchestrator failed: {e}")
        return pd.DataFrame(index=df.index)

    finally:
        print(f"[Orchestrator] ThreadPoolExecutor finished.", flush=True)
        # DEC-007 exit discipline: clear context attribute unconditionally

        # so no downstream caller sees leaked peer data.
        try:
            df.attrs.pop("_atlas_context", None)
        except Exception:
            pass
        # Flush again at the end so no stale entry (keyed on the just-alive
        # df's id) can be reused for a later, unrelated DataFrame whose id
        _l1_bridge.clear_cache()
        _l3_bridge.clear_cache()
        _l4_bridge.clear_cache()
    
    res = pd.DataFrame(cols, index=df.index) if cols else pd.DataFrame(index=df.index)
    if len(_compute_cache) > 200:
        _compute_cache.clear()
    _compute_cache[cache_key] = {"t": time.time(), "df": res.copy()}
    return res

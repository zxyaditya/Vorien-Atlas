"""Precomputed fixture matrices for the Validation Framework.

Computing 665 features × 5 gates × 2 recomputes was ~330s per report.
Batching compute_features(df, ALL_IDS) once per fixture drops it to
~40s per full report (single-pass per fixture). Gates then look up
their series from the precomputed matrix rather than triggering a
fresh compute.

Cached with the same TTL as the runner. Called by ValidationRunner.
"""
from __future__ import annotations
import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import fixtures as F


class FixtureMatrices:
    """Container for the batched compute outputs used by every gate."""

    def __init__(self) -> None:
        self.brownian_df: Optional[pd.DataFrame] = None
        self.brownian_X: Optional[pd.DataFrame] = None
        self.brownian_X_2: Optional[pd.DataFrame] = None  # for determinism
        self.trending_X: Optional[pd.DataFrame] = None
        self.mean_reverting_X: Optional[pd.DataFrame] = None
        self.constant_X: Optional[pd.DataFrame] = None
        self.nan_infested_X: Optional[pd.DataFrame] = None

        # Perturbed variants for no_future_leakage
        self.brownian_perturbed_df: Optional[pd.DataFrame] = None
        self.brownian_perturbed_X: Optional[pd.DataFrame] = None
        self.k_perturbed: int = 10

        # Scale/translation-transformed variants for property gates
        self.scale_multipliers: List[float] = [0.5, 2.0, 10.0]
        self.scale_X: Dict[float, pd.DataFrame] = {}
        self.trans_shifts: List[float] = [-25.0, 50.0]
        self.trans_X: Dict[float, pd.DataFrame] = {}

        # Peer-context matrices (for identity verifiers + symmetric_in_peer)
        self.peer_a_df: Optional[pd.DataFrame] = None
        self.peer_b_df: Optional[pd.DataFrame] = None
        self.peer_self_X: Optional[pd.DataFrame] = None   # peer = target = brownian_df
        self.peer_a_with_b_X: Optional[pd.DataFrame] = None
        self.peer_b_with_a_X: Optional[pd.DataFrame] = None

        # Context-isolation: features declaring requires_context computed
        # WITHOUT context (soft-fail contract check).
        self.no_context_context_features_X: Optional[pd.DataFrame] = None

        self.built_at: float = 0.0

    def build(self, registry) -> "FixtureMatrices":
        from atlas_core.compute import compute_features
        ids = [f.id for f in registry.all()]
        # -- Base fixtures ------------------------------------------------
        self.brownian_df = F.brownian()
        self.brownian_X = compute_features(self.brownian_df, ids)
        self.brownian_X_2 = compute_features(self.brownian_df, ids)
        self.trending_X = compute_features(F.trending(), ids)
        self.mean_reverting_X = compute_features(F.mean_reverting(), ids)
        self.constant_X = compute_features(F.constant(), ids)
        self.nan_infested_X = compute_features(F.nan_infested(), ids)
        # -- No-future-leakage perturbed variant --------------------------
        df2 = self.brownian_df.copy()
        rng = np.random.default_rng(999)
        K = self.k_perturbed
        mult = rng.uniform(1.5, 3.0, size=K)
        for col in ("open", "high", "low", "close"):
            factor = mult if col != "low" else mult * 0.99
            df2.iloc[-K:, df2.columns.get_loc(col)] *= factor
        self.brownian_perturbed_df = df2
        self.brownian_perturbed_X = compute_features(df2, ids)
        # -- Scale-invariant fixtures ------------------------------------
        for k in self.scale_multipliers:
            scaled = self.brownian_df.copy()
            for col in ("open", "high", "low", "close"):
                scaled[col] = scaled[col] * k
            self.scale_X[k] = compute_features(scaled, ids)
        # -- Translation-invariant fixtures ------------------------------
        for c in self.trans_shifts:
            shifted = self.brownian_df.copy()
            for col in ("open", "high", "low", "close"):
                shifted[col] = shifted[col] + c
            self.trans_X[c] = compute_features(shifted, ids)
        # -- Peer-context fixtures ---------------------------------------
        a, b = F.two_pairs()
        self.peer_a_df, self.peer_b_df = a, b
        peer_a_aligned = a.reindex(a.index).ffill()
        peer_b_aligned = b.reindex(a.index).ffill()
        self.peer_self_X = compute_features(self.brownian_df, ids,
                                             context={"peer": self.brownian_df.copy()})
        self.peer_a_with_b_X = compute_features(a, ids,
                                                 context={"peer": peer_b_aligned})
        self.peer_b_with_a_X = compute_features(b, ids,
                                                 context={"peer": peer_a_aligned})
        # -- Context-isolation (no context supplied) ---------------------
        ctx_ids = [f.id for f in registry.all()
                    if getattr(f, "validation", None) and
                       "peer" in getattr(f.validation, "requires_context", [])]
        if ctx_ids:
            self.no_context_context_features_X = compute_features(
                self.brownian_df, ctx_ids, context=None)
        else:
            self.no_context_context_features_X = pd.DataFrame(
                index=self.brownian_df.index)
        self.built_at = time.time()
        return self

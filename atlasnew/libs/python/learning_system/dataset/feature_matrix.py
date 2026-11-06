"""Feature Matrix Generator — thin wrapper around atlas_core.compute.

Only responsibility: given an OHLCV DataFrame + a list of Atlas feature
IDs, produce an aligned pd.DataFrame with strict NaN policy for ML use.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from atlas_core.compute import compute_features
from atlas_core.registry.registry import registry


def build_feature_matrix(
    df: pd.DataFrame,
    feature_ids: List[str],
    context: Optional[Dict[str, pd.DataFrame]] = None,
    dropna_policy: str = "any",
) -> pd.DataFrame:
    """Compute Atlas features and apply the ML-consumption NaN policy.

    - dropna_policy="any": drop rows that contain any NaN.
    - dropna_policy="all": drop rows where every feature is NaN.
    - dropna_policy="none": return raw (caller handles NaNs).

    Unknown feature IDs are silently dropped (compute_features already
    guards). If none are known, raises ValueError.
    """
    known = [fid for fid in feature_ids if registry.contains(fid)]
    if not known:
        raise ValueError(
            f"None of the requested feature IDs are registered: "
            f"{feature_ids[:5]}..."
        )
    X = compute_features(df, known, context=context)
    X = X.replace([np.inf, -np.inf], np.nan)
    if dropna_policy == "any":
        X = X.dropna(axis=0, how="any")
    elif dropna_policy == "all":
        X = X.dropna(axis=0, how="all")
    # "none" → no filtering.
    # Guarantee numeric dtype (compute_features already returns float64,
    # but be defensive against Registry regressions).
    X = X.astype(float)
    return X

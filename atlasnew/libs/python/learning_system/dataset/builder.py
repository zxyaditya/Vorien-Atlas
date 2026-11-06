"""DatasetBuilder — compose feature matrix + labels + splits into a Dataset.

The Dataset object is immutable and self-describing: it carries the
spec, the aligned (X, y) matrices, the valid-row mask, and enough
metadata for reproducibility (n_features, class balance, index range).
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from learning_system.contracts import DatasetSpec, to_json_safe
from learning_system.dataset.feature_matrix import build_feature_matrix
from learning_system.dataset.labels import generate_labels


@dataclass
class Dataset:
    spec: DatasetSpec
    X: pd.DataFrame
    y: pd.Series
    index: pd.Index
    n_rows: int
    n_features: int
    class_balance: Dict[str, int]
    fingerprint: str          # sha1 of spec + shape (for tracking)
    n_raw_rows: int = 0
    n_nan_dropped: int = 0
    n_horizon_dropped: int = 0
    index_range: List[str] = field(default_factory=list)


@dataclass
class DatasetPreview:
    n_rows: int
    n_features: int
    class_balance: Dict[str, int]
    horizon: int
    label_kind: str
    label_params: Dict[str, Any]
    dropped_by_nan: int
    dropped_by_label: int
    index_range: List[str] = field(default_factory=list)


def _fingerprint(spec: DatasetSpec, X: pd.DataFrame, y: pd.Series) -> str:
    payload = {
        "spec": to_json_safe(spec),
        "shape": [int(X.shape[0]), int(X.shape[1])],
        "index_first": str(X.index[0]) if len(X) else "",
        "index_last": str(X.index[-1]) if len(X) else "",
        "pos_rate": float((y > 0).mean()) if len(y) else 0.0,
    }
    return hashlib.sha1(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def build_dataset(df: pd.DataFrame, spec: DatasetSpec,
                   context: Optional[Dict[str, pd.DataFrame]] = None,
                   ) -> Dataset:
    """Full pipeline: features → labels → align → mask."""
    if len(df) < spec.min_history:
        raise ValueError(
            f"df has {len(df)} rows; DatasetSpec.min_history = {spec.min_history}"
        )
    n_raw_rows = len(df)
    index_start = str(df.index[0]) if len(df) > 0 else ""
    index_end = str(df.index[-1]) if len(df) > 0 else ""
    
    X = build_feature_matrix(df, spec.feature_ids, context=context,
                              dropna_policy=spec.dropna_policy)
    n_after_nan = len(X)
    n_nan_dropped = n_raw_rows - n_after_nan
    
    # Extract regime flags for dynamic labeling and filtering
    req_features = [
        "market_regime.regime.trending_quiet_flag",
        "market_regime.regime.trending_volatile_flag",
        "trend_state.regime.trend_continuation_flag",
        "meta_features.regime.l3_family_agreement_score",
        "range_state.regime.breakout_environment_flag"
    ]
    X_regime = build_feature_matrix(df, req_features, context=context, dropna_policy="none")
    
    t_quiet = X_regime.get("market_regime.regime.trending_quiet_flag", pd.Series(1.0, index=X_regime.index))
    t_vol = X_regime.get("market_regime.regime.trending_volatile_flag", pd.Series(1.0, index=X_regime.index))
    t_cont = X_regime.get("trend_state.regime.trend_continuation_flag", pd.Series(1.0, index=X_regime.index))
    t_agree = X_regime.get("meta_features.regime.l3_family_agreement_score", pd.Series(1.0, index=X_regime.index))
    t_breakout = X_regime.get("range_state.regime.breakout_environment_flag", pd.Series(0.0, index=X_regime.index))
    
    # Generate labels, passing regime flags if supported by labeler
    y, valid = generate_labels(df, kind=spec.label_kind,
                                horizon=spec.horizon,
                                t_quiet=t_quiet, t_vol=t_vol, t_breakout=t_breakout,
                                **spec.label_params)
                                
    if getattr(spec, "regime_filter", False):
        is_trending = (t_quiet == 1) | (t_vol == 1)
        is_breaking_out = (t_breakout == 1)
        is_continuing = (t_cont == 1)
        is_coherent = (t_agree > 0.5)
        
        regime_ok = (is_trending & is_continuing & is_coherent) | (is_breaking_out & is_coherent)
        
        # Intersect with the valid mask (which is a boolean numpy array of the same length)
        # Ensure regime_ok is a boolean numpy array
        regime_ok_arr = regime_ok.reindex(df.index).fillna(False).values
        valid = valid & regime_ok_arr

    # Intersect the index of X with the valid label mask.
    common = X.index.intersection(y.index[valid])
    n_after_label = len(common)
    n_horizon_dropped = n_after_nan - n_after_label
    
    X = X.loc[common]
    y = y.loc[common].astype(np.int8)
    if len(X) < 30:
        raise ValueError(
            f"Dataset too small after label + NaN filtering: n={len(X)}"
        )
    counts = y.value_counts().to_dict()
    balance = {str(int(k)): int(v) for k, v in counts.items()}
    return Dataset(
        spec=spec, X=X, y=y, index=X.index,
        n_rows=int(len(X)), n_features=int(X.shape[1]),
        class_balance=balance,
        fingerprint=_fingerprint(spec, X, y),
        n_raw_rows=n_raw_rows,
        n_nan_dropped=n_nan_dropped,
        n_horizon_dropped=n_horizon_dropped,
        index_range=[index_start, index_end],
    )


def preview_dataset(df: pd.DataFrame, spec: DatasetSpec,
                     context: Optional[Dict[str, pd.DataFrame]] = None,
                     ) -> DatasetPreview:
    """Quick shape/balance inspection without keeping the matrix alive."""
    n_before = len(df)
    try:
        ds = build_dataset(df, spec, context=context)
    except ValueError as e:
        return DatasetPreview(
            n_rows=0, n_features=0, class_balance={},
            horizon=spec.horizon, label_kind=spec.label_kind,
            label_params=dict(spec.label_params),
            dropped_by_nan=0, dropped_by_label=n_before,
            index_range=[],
        )
    return DatasetPreview(
        n_rows=ds.n_rows,
        n_features=ds.n_features,
        class_balance=ds.class_balance,
        horizon=spec.horizon,
        label_kind=spec.label_kind,
        label_params=dict(spec.label_params),
        dropped_by_nan=int(max(0, n_before - ds.n_rows - spec.horizon)),
        dropped_by_label=int(spec.horizon),
        index_range=[str(ds.index[0]), str(ds.index[-1])],
    )

"""Learning System contracts — the vocabulary every subsystem shares.

Dataclasses only; no runtime logic. Every dataclass is JSON-serialisable
through `asdict()` so experiment records can live in Mongo without
custom encoders.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DatasetSpec:
    """How to build (X, y) from an OHLCV DataFrame."""
    feature_ids: List[str]              # Atlas feature IDs (L1..L4)
    horizon: int = 5                    # bars forward for label
    label_kind: str = "sign"            # sign | quantile | vol_norm | triple_barrier
    label_params: Dict[str, Any] = field(default_factory=dict)
    min_history: int = 200              # reject datasets smaller than this
    dropna_policy: str = "none"         # any | all | none
    regime_filter: bool = False         # Only train on valid regime bars


@dataclass(frozen=True)
class SplitSpec:
    """How to split (X, y) into folds."""
    kind: str = "walk_forward"          # walk_forward | expanding | purged_kfold
    n_folds: int = 5
    embargo: int = 0                    # bars removed around test window (leakage guard)
    train_size: float = 0.7             # single-shot mode; ignored for K-fold
    step: int = 0                       # walk-forward step (0 = auto = n // (n_folds+1))


@dataclass(frozen=True)
class ModelSpec:
    kind: str                           # registered model kind (see MODEL_REGISTRY)
    hyperparams: Dict[str, Any] = field(default_factory=dict)
    seed: int = 42


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    dataset: DatasetSpec
    split: SplitSpec
    model: ModelSpec
    tags: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class FoldMetrics:
    fold: int
    n_train: int
    n_test: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    metrics: Dict[str, float]
    top_features: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ExperimentResult:
    experiment_id: str
    spec: ExperimentSpec
    folds: List[FoldMetrics]
    aggregate: Dict[str, float]         # mean/std over folds
    model_ids: List[str]                # per-fold model IDs in the registry
    duration_seconds: float
    seed: int
    created_at: str
    dataset_meta: Dict[str, Any] = field(default_factory=dict)
    timing_meta: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"                 # ok | error
    error: Optional[str] = None


@dataclass(frozen=True)
class InferenceRequest:
    model_id: str
    provider: str
    symbol: str
    interval: str = "1d"
    period: str = "5y"
    peer_provider: Optional[str] = None
    peer_symbol: Optional[str] = None


@dataclass
class Prediction:
    model_id: str
    experiment_id: str
    kind: str                          # e.g. "xgboost"
    direction: str                     # UP | DOWN | ABSTAIN
    probability_up: Optional[float]    # 0..1 or None
    confidence: float                  # 0..1
    horizon: int
    top_features: List[Dict[str, Any]] = field(default_factory=list)
    provider: str = ""
    symbol: str = ""
    as_of: str = ""


import numpy as np

def to_json_safe(obj: Any) -> Any:
    """Recursively serialise dataclasses / dicts / lists to JSON-safe."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_json_safe(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json_safe(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return float(obj) if np.isfinite(obj) else None
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj

"""TrainingPipeline — the single entry point that composes everything.

Given an ExperimentSpec + an OHLCV DataFrame, it:
  1. builds the Dataset,
  2. generates splits,
  3. per fold: instantiates a fresh model, fits on train, scores test,
  4. aggregates metrics, records top-features per fold,
  5. returns an ExperimentResult.

This file does NOT persist anything. Persistence is layered above by
`ExperimentTracker` + `ModelRegistry`.
"""
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from learning_system.contracts import (
    ExperimentResult, ExperimentSpec, FoldMetrics,
)
from learning_system.dataset.builder import build_dataset, Dataset
from learning_system.dataset.splits import generate_splits
from learning_system.models import instantiate
from learning_system.training.metrics import compute_metrics


@dataclass
class TrainingResult:
    experiment: ExperimentResult
    dataset: Dataset
    fitted_models: List[Any]     # per-fold BaseModel instances


class TrainingPipeline:
    def __init__(self, spec: ExperimentSpec):
        self.spec = spec

    def run(self, df: pd.DataFrame,
            context: Optional[Dict[str, pd.DataFrame]] = None,
            ) -> TrainingResult:
        t0 = time.time()
        exp_id = uuid.uuid4().hex
        ds = build_dataset(df, self.spec.dataset, context=context)

        # Generate splits.
        split_kwargs = {
            "n_folds": self.spec.split.n_folds,
            "embargo": self.spec.split.embargo,
            "train_size": self.spec.split.train_size,
            "step": self.spec.split.step,
            "horizon": self.spec.dataset.horizon,
        }
        folds = generate_splits(ds.n_rows, self.spec.split.kind, **split_kwargs)
        if not folds:
            return TrainingResult(
                experiment=ExperimentResult(
                    experiment_id=exp_id, spec=self.spec, folds=[],
                    aggregate={}, model_ids=[], duration_seconds=0.0,
                    seed=self.spec.model.seed,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    status="error", error="no folds could be generated",
                ),
                dataset=ds, fitted_models=[],
            )

        fold_metrics: List[FoldMetrics] = []
        fitted: List[Any] = []
        model_ids: List[str] = []
        for i, (tr, te) in enumerate(folds):
            Xtr, Xte = ds.X.iloc[tr], ds.X.iloc[te]
            ytr, yte = ds.y.iloc[tr].values, ds.y.iloc[te].values
            if len(np.unique(ytr)) < 2 or len(np.unique(yte)) < 2:
                # Degenerate fold — record and continue.
                fold_metrics.append(FoldMetrics(
                    fold=i, n_train=int(len(tr)), n_test=int(len(te)),
                    train_start=str(Xtr.index[0]) if len(Xtr) else "",
                    train_end=str(Xtr.index[-1]) if len(Xtr) else "",
                    test_start=str(Xte.index[0]) if len(Xte) else "",
                    test_end=str(Xte.index[-1]) if len(Xte) else "",
                    metrics={"error": "single_class_fold"},
                    top_features=[],
                ))
                continue

            model = instantiate(self.spec.model.kind,
                                 hyperparams=self.spec.model.hyperparams,
                                 seed=self.spec.model.seed)
            model.fit(Xtr, ytr)
            proba = model.predict_proba(Xte)
            y_prob = proba[:, 1]
            m = compute_metrics(yte, y_prob)
            imp = model.feature_importances()
            top = sorted(imp.items(), key=lambda kv: -kv[1])[:10]
            top_features = [{"id": k, "importance": round(float(v), 6)}
                              for k, v in top]
            model_ids.append(uuid.uuid4().hex)
            fitted.append(model)
            fold_metrics.append(FoldMetrics(
                fold=i, n_train=int(len(tr)), n_test=int(len(te)),
                train_start=str(Xtr.index[0]),
                train_end=str(Xtr.index[-1]),
                test_start=str(Xte.index[0]),
                test_end=str(Xte.index[-1]),
                metrics=m, top_features=top_features,
            ))

        aggregate = _aggregate(fold_metrics)
        result = ExperimentResult(
            experiment_id=exp_id,
            spec=self.spec,
            folds=fold_metrics,
            aggregate=aggregate,
            model_ids=model_ids,
            duration_seconds=round(time.time() - t0, 3),
            seed=self.spec.model.seed,
            created_at=datetime.now(timezone.utc).isoformat(),
            dataset_meta={
                "n_raw_rows": ds.n_raw_rows,
                "n_nan_dropped": ds.n_nan_dropped,
                "n_horizon_dropped": ds.n_horizon_dropped,
                "n_rows": ds.n_rows,
                "n_features": ds.n_features,
                "class_balance": ds.class_balance,
                "index_range": ds.index_range,
            },
            timing_meta={
                "start_time": datetime.fromtimestamp(t0, timezone.utc).isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(time.time() - t0, 3),
                "avg_fold_duration": round((time.time() - t0) / max(1, len(folds)), 3),
            },
        )
        return TrainingResult(experiment=result, dataset=ds,
                              fitted_models=fitted)


def _aggregate(folds: List[FoldMetrics]) -> Dict[str, float]:
    if not folds:
        return {}
    keys = set()
    for f in folds:
        for k, v in f.metrics.items():
            if isinstance(v, (int, float)) and k != "n_classes_in_test":
                keys.add(k)
    agg: Dict[str, float] = {}
    for k in keys:
        vals = [f.metrics[k] for f in folds
                 if k in f.metrics and isinstance(f.metrics[k], (int, float))]
        if vals:
            agg[f"{k}_mean"] = round(float(np.mean(vals)), 6)
            agg[f"{k}_std"] = round(float(np.std(vals)), 6)
    agg["n_folds"] = float(len([f for f in folds
                                  if "error" not in f.metrics]))
    return agg

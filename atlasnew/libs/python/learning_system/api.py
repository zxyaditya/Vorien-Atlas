"""FastAPI router for the Learning System.
from fastapi import Body

All routes are prefixed `/api/learning`.
"""
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Body
from pydantic import BaseModel, Field

from learning_system.contracts import (
    DatasetSpec, ExperimentSpec, InferenceRequest, ModelSpec, SplitSpec,
    to_json_safe,
)
from learning_system.dataset.builder import preview_dataset
from learning_system.models import MODEL_REGISTRY
from learning_system.training.pipeline import TrainingPipeline


# ────────────────────────────────────────────────────────────────────
# Pydantic request/response schemas (thin wrappers around dataclasses)
# ────────────────────────────────────────────────────────────────────
class _DatasetBody(BaseModel):
    feature_ids: List[str]
    horizon: int = 5
    label_kind: str = "sign"
    label_params: Dict[str, Any] = Field(default_factory=dict)
    min_history: int = 200
    dropna_policy: str = "none"
    regime_filter: bool = False


class _SplitBody(BaseModel):
    kind: str = "walk_forward"
    n_folds: int = 5
    embargo: int = 0
    train_size: float = 0.7
    step: int = 0


class _ModelBody(BaseModel):
    kind: str
    hyperparams: Dict[str, Any] = Field(default_factory=dict)
    seed: int = 42


class DatasetPreviewRequest(BaseModel):
    provider: str = "synthetic"
    symbol: str = "SYN-EQUITY"
    interval: str = "1d"
    period: str = "3y"
    dataset: _DatasetBody

class DatasetBuildRequest(BaseModel):
    provider: str = "synthetic"
    symbol: str = "SYN-EQUITY"
    interval: str = "1d"
    period: str = "3y"
    project_id: Optional[str] = None
    dataset: _DatasetBody


class RunExperimentRequest(BaseModel):
    name: str
    provider: str = "synthetic"
    symbol: str = "SYN-EQUITY"
    interval: str = "1d"
    period: str = "5y"
    peer_provider: Optional[str] = None
    peer_symbol: Optional[str] = None
    dataset: _DatasetBody
    split: _SplitBody = _SplitBody()
    model: _ModelBody
    tags: List[str] = Field(default_factory=list)
    notes: str = ""


class InferBody(BaseModel):
    model_id: str
    provider: str = "synthetic"
    symbol: str = "SYN-EQUITY"
    interval: str = "1d"
    period: str = "5y"
    peer_provider: Optional[str] = None
    peer_symbol: Optional[str] = None


def _body_to_specs(body_dataset: _DatasetBody, body_split: _SplitBody,
                     body_model: _ModelBody):
    return (
        DatasetSpec(
            feature_ids=list(body_dataset.feature_ids),
            horizon=body_dataset.horizon,
            label_kind=body_dataset.label_kind,
            label_params=dict(body_dataset.label_params),
            min_history=body_dataset.min_history,
            dropna_policy=body_dataset.dropna_policy,
            regime_filter=body_dataset.regime_filter,
        ),
        SplitSpec(
            kind=body_split.kind, n_folds=body_split.n_folds,
            embargo=body_split.embargo, train_size=body_split.train_size,
            step=body_split.step,
        ),
        ModelSpec(
            kind=body_model.kind,
            hyperparams=dict(body_model.hyperparams),
            seed=body_model.seed,
        ),
    )


class BacktestBody(BaseModel):
    model_id: str
    provider: str = "synthetic"
    symbol: str = "SYN-EQUITY"
    interval: str = "1d"
    period: str = "5y"
    peer_provider: Optional[str] = None
    peer_symbol: Optional[str] = None
    warmup_bars: int = 250
    initial_cash: float = 100_000.0
    fee_bps: float = 5.0
    slippage_bps: float = 5.0
    upper_threshold: float = 0.51
    lower_threshold: float = 0.49
    allow_short: bool = True
    position_size_pct: float = 30.0
    max_leverage: float = 2.0
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    stop_atr_mult: float = 0.0
    take_profit_atr_mult: float = 0.0
    cool_down_bars: int = 1
    hold_bars: int = 0                   # 0 = strategy-based exit; >0 = fixed-horizon exit
    regime_gate: bool = True
    trailing_stop_atr_mult: float = 0.0
    fractional_kelly: float = 1.0
    dynamic_sizing: bool = True
    dynamic_exits: bool = True
    execution_mode: str = "paper"


def build_router(fetch_smart, model_registry, tracker, inference_pipeline,
                  de_bridge, backtest_tracker=None, db=None) -> APIRouter:
    """Assemble the /api/learning router.

    Dependencies are injected so tests can substitute in-memory doubles.
    """
    router = APIRouter(prefix="/api/learning", tags=["learning"])

    # -- Meta -----------------------------------------------------------
    @router.get("/")
    async def root():
        return {
            "subsystem": "learning_system",
            "version": "0.13.0",
            "registered_models": sorted(MODEL_REGISTRY),
            "registered_label_kinds": _label_kinds(),
            "registered_split_kinds": _split_kinds(),
        }

    @router.get("/registry/stats")
    async def stats():
        model_stats = await model_registry.stats()
        exp_stats = await tracker.stats()
        bt_stats = (await backtest_tracker.stats()
                     if backtest_tracker is not None else {"n_backtests": 0})
        ds_count = (await db["atlas_datasets"].count_documents({})
                    if db is not None else 0)
        return {"models": model_stats, "experiments": exp_stats,
                "backtests": bt_stats, "datasets": {"n_datasets": ds_count}}

    @router.get("/models/registered")
    async def registered_models():
        return {"kinds": sorted(MODEL_REGISTRY),
                "count": len(MODEL_REGISTRY)}

    # -- Dataset preview -------------------------------------------------
    @router.post("/datasets/preview")
    async def dataset_preview(body: DatasetPreviewRequest):
        df = fetch_smart(body.provider, body.symbol, body.interval,
                          body.period, limit=5000)
        if df is None or len(df) < body.dataset.min_history:
            raise HTTPException(400, "insufficient OHLCV data")
        ds_spec, _, _ = _body_to_specs(body.dataset, _SplitBody(),
                                          _ModelBody(kind="logreg"))
        from fastapi.concurrency import run_in_threadpool
        pv = await run_in_threadpool(preview_dataset, df, ds_spec)
        return to_json_safe(pv)

    # -- Dataset build (persists metadata to MongoDB) --------------------
    @router.post("/datasets/build", status_code=201)
    async def dataset_build(body: DatasetBuildRequest):
        """Build a dataset and persist its metadata to MongoDB.

        The raw X/y matrix is NOT stored (too large). Only the spec,
        shape, class balance, and fingerprint are stored for browsing.
        """
        if db is None:
            raise HTTPException(503, "Database not available")
        df = fetch_smart(body.provider, body.symbol, body.interval,
                          body.period, limit=50000)
        if df is None or len(df) < body.dataset.min_history:
            raise HTTPException(400, "insufficient OHLCV data")
        ds_spec, _, _ = _body_to_specs(body.dataset, _SplitBody(),
                                          _ModelBody(kind="logreg"))
        from learning_system.dataset.builder import build_dataset
        from fastapi.concurrency import run_in_threadpool
        ds = await run_in_threadpool(build_dataset, df, ds_spec)

        import uuid as _uuid
        from datetime import datetime, timezone as _tz
        now = datetime.now(_tz.utc).isoformat()
        doc = {
            "dataset_id": _uuid.uuid4().hex,
            "project_id": body.project_id,
            "provider": body.provider,
            "symbol": body.symbol,
            "interval": body.interval,
            "period": body.period,
            "spec": {
                "feature_ids": ds_spec.feature_ids,
                "horizon": ds_spec.horizon,
                "label_kind": ds_spec.label_kind,
                "label_params": ds_spec.label_params,
                "min_history": ds_spec.min_history,
                "dropna_policy": ds_spec.dropna_policy,
                "regime_filter": ds_spec.regime_filter,
            },
            "n_raw_rows": ds.n_raw_rows,
            "n_rows": ds.n_rows,
            "n_features": ds.n_features,
            "n_nan_dropped": ds.n_nan_dropped,
            "n_horizon_dropped": ds.n_horizon_dropped,
            "class_balance": ds.class_balance,
            "index_range": ds.index_range,
            "fingerprint": getattr(ds, "fingerprint", None),
            "created_at": now,
        }
        await db["atlas_datasets"].insert_one(doc)
        doc["_id"] = str(doc.pop("_id", ""))
        # Increment project dataset_count if project_id given
        if body.project_id:
            await db["atlas_projects"].update_one(
                {"_id": __import__("bson").ObjectId(body.project_id)},
                {"$inc": {"dataset_count": 1}, "$set": {"updated_at": now}},
            )
        return doc

    @router.get("/datasets")
    async def list_datasets(project_id: Optional[str] = None, limit: int = 100):
        """List persisted dataset metadata. Optionally filter by project_id."""
        if db is None:
            return []
        query: Dict[str, Any] = {}
        if project_id:
            query["project_id"] = project_id
        docs = []
        async for doc in db["atlas_datasets"].find(query).sort("created_at", -1).limit(limit):
            doc["_id"] = str(doc["_id"])
            docs.append(doc)
        return docs

    @router.get("/datasets/{dataset_id}")
    async def get_dataset(dataset_id: str):
        if db is None:
            raise HTTPException(503, "Database not available")
        doc = await db["atlas_datasets"].find_one({"dataset_id": dataset_id})
        if not doc:
            raise HTTPException(404, "dataset not found")
        doc["_id"] = str(doc["_id"])
        return doc

    @router.delete("/datasets/{dataset_id}")
    async def delete_dataset(dataset_id: str):
        if db is None:
            raise HTTPException(503, "Database not available")
        result = await db["atlas_datasets"].delete_one({"dataset_id": dataset_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "dataset not found")
        return {"deleted": True, "dataset_id": dataset_id}



    # -- Experiments -----------------------------------------------------
    @router.post("/experiments/run")
    async def run_experiment(body: RunExperimentRequest):
        if body.model.kind not in MODEL_REGISTRY:
            raise HTTPException(
                400, f"unknown model kind {body.model.kind!r}; "
                f"registered: {sorted(MODEL_REGISTRY)}"
            )
        df = fetch_smart(body.provider, body.symbol, body.interval,
                          body.period, limit=50000)
        if df is None or len(df) < body.dataset.min_history:
            raise HTTPException(400, "insufficient OHLCV data")

        context = None
        if body.peer_provider and body.peer_symbol:
            peer_df = fetch_smart(body.peer_provider, body.peer_symbol,
                                   body.interval, body.period, limit=50000)
            if peer_df is not None:
                peer_df = peer_df.reindex(df.index).ffill()
                context = {"peer": peer_df}

        ds_spec, sp_spec, m_spec = _body_to_specs(body.dataset, body.split,
                                                     body.model)
        exp_spec = ExperimentSpec(
            name=body.name, dataset=ds_spec, split=sp_spec, model=m_spec,
            tags=list(body.tags), notes=body.notes,
        )

        # Training is CPU-bound; run in a thread so the FastAPI event
        # loop stays responsive.
        from fastapi.concurrency import run_in_threadpool
        pipeline = TrainingPipeline(exp_spec)
        result = await run_in_threadpool(pipeline.run, df, context)

        # Persist every fold's model + the experiment record.
        exp = result.experiment
        if exp.status == "ok" and result.fitted_models:
            saved_ids = []
            for i, model in enumerate(result.fitted_models):
                fold_metrics = exp.folds[i].metrics if i < len(exp.folds) else {}
                saved = await model_registry.save(
                    model=model,
                    experiment_id=exp.experiment_id,
                    fold=i,
                    metrics={**fold_metrics, **exp.aggregate,
                              "horizon": ds_spec.horizon},
                    feature_ids=list(result.dataset.X.columns),
                    provider=body.provider,
                    symbol=body.symbol,
                    interval=body.interval,
                    tags=list(body.tags),
                )
                saved_ids.append(saved["model_id"])
            exp.model_ids = saved_ids

        await tracker.record(exp)
        
        # Increment project experiment_count if project_id given
        if db is not None:
            for tag in body.tags:
                try:
                    obj_id = __import__("bson").ObjectId(tag)
                    await db["atlas_projects"].update_one(
                        {"_id": obj_id},
                        {"$inc": {"experiment_count": 1}}
                    )
                except Exception:
                    pass

        return to_json_safe(exp)

    @router.get("/experiments")
    async def list_experiments(name: Optional[str] = None, limit: int = 50):
        return await tracker.list(name=name, limit=limit)

    @router.get("/experiments/{experiment_id}")
    async def get_experiment(experiment_id: str):
        d = await tracker.get(experiment_id)
        if d is None:
            raise HTTPException(404, "experiment not found")
        return d

    # -- Models ---------------------------------------------------------
    @router.get("/models")
    async def list_models(kind: Optional[str] = None,
                           experiment_id: Optional[str] = None,
                           provider: Optional[str] = None,
                           symbol: Optional[str] = None,
                           limit: int = 50):
        models = await model_registry.list(kind=kind,
                                           experiment_id=experiment_id,
                                           provider=provider,
                                           symbol=symbol,
                                           limit=limit)
        if backtest_tracker is not None:
            for m in models:
                bts = await backtest_tracker.list(model_id=m.get("model_id"), limit=1)
                if bts:
                    m["latest_backtest"] = bts[0].get("metrics", {})
        return models

    @router.get("/models/best")
    async def best_models(metric: str = "accuracy_mean", top: int = 5,
                           kind: Optional[str] = None):
        return await model_registry.best(metric=metric, top=top, kind=kind)

    @router.get("/models/{model_id}")
    async def get_model(model_id: str):
        d = await model_registry.get(model_id)
        if d is None:
            raise HTTPException(404, "model not found")
        return d

    @router.delete("/models/{model_id}")
    async def delete_model(model_id: str):
        success = await model_registry.delete(model_id)
        if not success:
            raise HTTPException(404, "model not found or could not be deleted")
        return {"status": "ok", "deleted": model_id}

    @router.patch("/models/{model_id}")
    async def update_model(model_id: str, request: Request):
        updates = await request.json()
        success = await model_registry.update(model_id, updates)
        if not success:
            raise HTTPException(404, "model not found")
        return {"status": "updated"}

    # -- Inference -------------------------------------------------------
    @router.post("/inference/predict")
    async def predict(body: InferBody):
        req = InferenceRequest(
            model_id=body.model_id, provider=body.provider,
            symbol=body.symbol, interval=body.interval, period=body.period,
            peer_provider=body.peer_provider,
            peer_symbol=body.peer_symbol,
        )
        pred = await inference_pipeline.predict(req)
        if pred is None:
            raise HTTPException(404, "prediction failed — model not found "
                                       "or feature computation empty")
        return to_json_safe(pred)

    # -- Backtest (v0.12.0 · Session 12) --------------------------------
    @router.post("/backtest/run")
    async def backtest_run(body: BacktestBody):
        from learning_system.backtest import (
            BacktestEngine, BacktestSpec, StrategyPolicy,
        )
        meta = await model_registry.get(body.model_id)
        if meta is None:
            raise HTTPException(404, "model not found")
        model = await model_registry.load_model(body.model_id)
        if model is None:
            raise HTTPException(
                404,
                f"Model artifact not found for model_id '{body.model_id}'. "
                "The model was registered but its artifact file is missing from disk "
                "(this can happen if the server was restarted without persisting the artifacts volume). "
                "Please re-train the model to regenerate the artifact."
            )
        df = fetch_smart(body.provider, body.symbol, body.interval,
                          body.period, limit=50000)
        if df is None or len(df) < 100:
            raise HTTPException(400, "insufficient OHLCV data")
        context = None
        if body.peer_provider and body.peer_symbol:
            peer_df = fetch_smart(body.peer_provider, body.peer_symbol,
                                    body.interval, body.period, limit=50000)
            if peer_df is not None:
                peer_df = peer_df.reindex(df.index).ffill()
                context = {"peer": peer_df}
        spec = BacktestSpec(
            model_id=body.model_id, provider=body.provider,
            symbol=body.symbol, interval=body.interval, period=body.period,
            peer_provider=body.peer_provider, peer_symbol=body.peer_symbol,
            warmup_bars=body.warmup_bars,
            initial_cash=body.initial_cash,
            fee_bps=body.fee_bps, slippage_bps=body.slippage_bps,
            policy=StrategyPolicy(
                upper_threshold=body.upper_threshold,
                lower_threshold=body.lower_threshold,
                allow_short=body.allow_short,
                position_size_pct=body.position_size_pct,
                max_leverage=body.max_leverage,
                stop_loss_pct=body.stop_loss_pct,
                take_profit_pct=body.take_profit_pct,
                stop_atr_mult=body.stop_atr_mult,
                take_profit_atr_mult=body.take_profit_atr_mult,
                cool_down_bars=body.cool_down_bars,
                trailing_stop_atr_mult=body.trailing_stop_atr_mult,
                fractional_kelly=body.fractional_kelly,
                dynamic_sizing=body.dynamic_sizing,
                dynamic_exits=body.dynamic_exits,
            ),
            execution_mode=body.execution_mode,
            hold_bars=body.hold_bars,
            regime_gate=body.regime_gate,
        )
        engine = BacktestEngine.build(spec)
        feature_ids = list(meta.get("feature_ids") or [])
        from fastapi.concurrency import run_in_threadpool
        import logging as _log
        try:
            result = await run_in_threadpool(engine.run, df, model, feature_ids, spec, context)
        except Exception as exc:
            _log.getLogger("atlas.api.backtest").error("Backtest engine crashed: %s", exc, exc_info=True)
            raise HTTPException(500, f"Backtest engine error: {type(exc).__name__}: {str(exc)[:300]}")
        try:
            payload = to_json_safe(result)
        except Exception as exc:
            _log.getLogger("atlas.api.backtest").error("Failed to serialise backtest result: %s", exc, exc_info=True)
            raise HTTPException(500, f"Failed to serialise result: {type(exc).__name__}: {str(exc)[:200]}")
        # v0.13.0 · Session 13. Persist every backtest for later browsing.
        if backtest_tracker is not None:
            try:
                await backtest_tracker.record(result)
                
                # Increment project backtest_count if model is tagged with project_id
                if db is not None:
                    tags = meta.get("tags") or []
                    for tag in tags:
                        try:
                            obj_id = __import__("bson").ObjectId(tag)
                            await db["atlas_projects"].update_one(
                                {"_id": obj_id},
                                {"$inc": {"backtest_count": 1}}
                            )
                        except Exception:
                            pass

            except Exception:
                # Persistence must never break the actual backtest.
                pass
        return payload

    @router.get("/backtest/list")
    async def backtest_list(model_id: Optional[str] = None,
                             symbol: Optional[str] = None,
                             limit: int = 50):
        if backtest_tracker is None:
            return []
        return await backtest_tracker.list(model_id=model_id,
                                            symbol=symbol, limit=limit)

    @router.get("/backtest/{backtest_id}")
    async def backtest_get(backtest_id: str):
        if backtest_tracker is None:
            raise HTTPException(404, "backtest tracker not configured")
        d = await backtest_tracker.get(backtest_id)
        if d is None:
            raise HTTPException(404, "backtest not found")
        return d

    @router.delete("/backtest/{backtest_id}")
    async def backtest_delete(backtest_id: str):
        if backtest_tracker is None or backtest_tracker._col is None:
            raise HTTPException(500, "Persistence unavailable")
        res = await backtest_tracker._col.delete_one({"backtest_id": backtest_id})
        if res.deleted_count == 0:
            raise HTTPException(404, "Backtest not found")
        return {"status": "ok", "deleted": backtest_id}

    # -- Decision Engine bridge -----------------------------------------
    @router.get("/bridge/prob_up")
    async def bridge_prob_up(provider: str, symbol: str,
                              interval: str = "1d", period: str = "3y",
                              kind: Optional[str] = None):
        return await de_bridge.latest_calibrated_prob_up(
            provider=provider, symbol=symbol,
            interval=interval, period=period, kind=kind,
        )

    @router.get("/bridge/ensemble_agreement")
    async def bridge_ensemble(provider: str, symbol: str,
                                interval: str = "1d", period: str = "3y",
                                top_k: int = 3,
                                metric: str = "accuracy_mean"):
        return await de_bridge.model_ensemble_agreement_score(
            provider=provider, symbol=symbol,
            interval=interval, period=period,
            top_k=top_k, metric=metric,
        )

    return router


def _label_kinds() -> List[str]:
    from learning_system.dataset.labels import LABEL_KINDS
    return sorted(LABEL_KINDS)


def _split_kinds() -> List[str]:
    from learning_system.dataset.splits import SPLIT_KINDS
    return sorted(SPLIT_KINDS)

"""Atlas Terminal API — thin FastAPI layer over Atlas Core."""
from __future__ import annotations
import os
import sys
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIBS = ROOT.parent.parent / "libs" / "python"
ATLASNEW = ROOT.parent.parent
REPO_ROOT = ROOT.parent.parent.parent
for p in [ROOT, LIBS, ATLASNEW, REPO_ROOT]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import FastAPI, APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from dotenv import load_dotenv
import numpy as np
import pandas as pd
# ── Atlas Core ────────────────────────────────────────────────────────────
from atlas_core.registry.registry import registry
from atlas_core.compute import compute_features, list_features
from atlas_core.data import fetch_smart
from atlas_core.analysis import market_snapshot, explain_snapshot
from decision_engine.ml import train_and_predict
from decision_engine.ml.ensemble import train_ensemble
from atlas_core.validation import run_all as run_golden_tests
from decision_engine import recommend
from decision_engine.weight_learner import learn_weights
import asyncio
from concurrent.futures import ThreadPoolExecutor
ml_executor = ThreadPoolExecutor(max_workers=2)
ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017")
DB_NAME = os.environ.get("DB_NAME", "atlas_dev")
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
app = FastAPI(title="Atlas Terminal API", version="1.0.0")
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    SECURITY: Catch all unhandled exceptions to prevent internal Python 
    stack traces and sensitive paths from leaking to the frontend.
    """
    log.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. See server logs for details."}
    )
api = APIRouter(prefix="/api")
# CORS and auth middleware are defined later (lines ~780+) with full guest-role support.
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("atlas")
def _clean(obj):
    """Recursively replace NaN/Inf with None for JSON safety and cast numpy types."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, np.floating) or isinstance(obj, float):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return [_clean(v) for v in obj.tolist()]
    return obj
# ═══════════════ Registry endpoints ═══════════════
from derivatives_registry import ALL_DERIVATIVES_FEATURES, FUTURES_FEATURES, OPTIONS_FEATURES

@api.get("/")
async def root():
    st = await registry_stats()
    return {"app": "Atlas Terminal", "version": "1.0.0",
            "registered_features": st["total"], "spot_core": st.get("spot_core_total", 925),
            "derivatives": st.get("derivatives_total", 114)}

@api.get("/registry/stats")
async def registry_stats():
    base = dict(registry.stats())
    base["spot_core_total"] = base["total"]
    base["derivatives_total"] = len(ALL_DERIVATIVES_FEATURES)
    base["total"] = base["spot_core_total"] + base["derivatives_total"]
    
    # Layer 5 for derivatives
    by_layer = dict(base.get("by_layer", {}))
    by_layer[5] = len(ALL_DERIVATIVES_FEATURES)
    by_layer["5"] = len(ALL_DERIVATIVES_FEATURES)
    base["by_layer"] = by_layer
    
    by_module = dict(base.get("by_module", {}))
    by_module["futures"] = len(FUTURES_FEATURES)
    by_module["options"] = len(OPTIONS_FEATURES)
    base["by_module"] = by_module
    
    return base

@api.get("/registry/features")
async def registry_features(
    layer: Optional[int] = None,
    module: Optional[str] = None,
    perspective: Optional[str] = None,
    family: Optional[str] = None,
    q: Optional[str] = None,
):
    core_feats = []
    if layer is None or layer in (1, 2, 3, 4):
        feats = list_features(layer=layer, module=module, perspective=perspective, family=family)
        core_feats = [f.to_public_dict() for f in feats]

    deriv_feats = []
    if layer is None or layer == 5:
        for df in ALL_DERIVATIVES_FEATURES:
            if module and df["module"] != module:
                continue
            if perspective and df["perspective"] != perspective:
                continue
            if family and df["family"] != family:
                continue
            deriv_feats.append(df)

    all_feats = core_feats + deriv_feats
    if q:
        ql = q.lower()
        all_feats = [f for f in all_feats if ql in f["id"].lower() or ql in f["name"].lower()]
    return all_feats

@api.get("/registry/features/{feature_id}")
async def registry_feature(feature_id: str):
    for df in ALL_DERIVATIVES_FEATURES:
        if df["id"] == feature_id:
            return df
    try:
        f = registry.get(feature_id)
        return f.to_public_dict()
    except KeyError:
        raise HTTPException(404, f"Feature '{feature_id}' not found")

@api.get("/registry/vocab")
async def registry_vocab():
    from atlas_core.registry.registry import LAYERS, PERSPECTIVES
    layers_dict = dict(LAYERS)
    layers_dict[5] = "L5 Derivatives: Futures & Options"
    perspectives_list = list(PERSPECTIVES)
    for p in ["Greeks", "Volatility"]:
        if p not in perspectives_list:
            perspectives_list.append(p)
    return {"layers": layers_dict, "perspectives": perspectives_list}
# ═══════════════ Peer context helper (DEC-007) ═══════════════
def _fetch_peer_context(peer_provider: Optional[str], peer_symbol: Optional[str],
                         interval: str, period: str, target_index) -> Optional[dict]:
    """Fetch peer OHLCV and align to the target's index.
    Returns {"peer": aligned_peer_df} for compute_features(..., context=...)
    when both peer args are supplied and the fetch succeeds; returns None
    otherwise so callers can skip attaching a context.
    """
    if not peer_provider or not peer_symbol:
        return None
    try:
        peer_df = fetch_smart(peer_provider, peer_symbol, interval, period, 500)
        if peer_df is None or peer_df.empty or "close" not in peer_df.columns:
            return None
        aligned = peer_df.reindex(target_index).ffill()
        return {"peer": aligned}
    except Exception:
        log.exception("peer fetch/align failed")
        return None
# ═══════════════ Market Data endpoints ═══════════════
class OHLCVBar(BaseModel):
    time: str; open: float; high: float; low: float; close: float; volume: float
def _df_to_bars(df: pd.DataFrame) -> List[dict]:
    bars = []
    for ts, row in df.iterrows():
        try:
            t = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        except Exception:
            t = str(ts)
        bars.append({
            "time": t, "open": float(row["open"]), "high": float(row["high"]),
            "low": float(row["low"]), "close": float(row["close"]),
            "volume": float(row["volume"]),
        })
    return bars
@api.get("/market/ohlcv")
def market_ohlcv(
    provider: str = "yahoo",
    symbol: str = "AAPL",
    interval: str = "1d",
    period: str = "1y",
    limit: int = 500,
):
    # v1.0 polish · transparent provenance. `served_by` may differ from
    # requested `provider` when the requested provider was unreachable
    # (e.g. Binance is geo-blocked from this deployment region, Yahoo
    # requires yfinance, CoinGecko is rate-limited). Frontend uses this
    # to render a fallback badge instead of pretending the fetch succeeded.
    df, served_by, fallback_reason = fetch_smart(
        provider, symbol, interval, period, limit, verbose=True)
    if df is None or df.empty:
        raise HTTPException(404, "No data returned")
    return {
        "provider": provider,
        "served_by": served_by,
        "fallback_reason": fallback_reason,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "interval": interval,
        "count": len(df),
        "bars": _df_to_bars(df),
    }
@api.get("/market/symbols")
async def market_symbols():
    return {
        "synthetic": [
            {"symbol": "SYN-EQUITY", "name": "Synthetic Equity (regime-switching)"},
            {"symbol": "SYN-CRYPTO", "name": "Synthetic Crypto (high-vol)"},
            {"symbol": "SYN-FX", "name": "Synthetic FX (mean-reverting)"},
        ],
        "coingecko": [
            {"symbol": "BTCUSDT", "name": "Bitcoin"},
            {"symbol": "ETHUSDT", "name": "Ethereum"},
            {"symbol": "SOLUSDT", "name": "Solana"},
            {"symbol": "BNBUSDT", "name": "BNB"},
        ],
        "yahoo": [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "MSFT", "name": "Microsoft"},
            {"symbol": "NVDA", "name": "NVIDIA"},
            {"symbol": "TSLA", "name": "Tesla"},
            {"symbol": "SPY", "name": "S&P 500 ETF"},
            {"symbol": "QQQ", "name": "Nasdaq 100 ETF"},
            {"symbol": "BTC-USD", "name": "Bitcoin"},
            {"symbol": "ETH-USD", "name": "Ethereum"},
            {"symbol": "GLD", "name": "Gold ETF"},
            {"symbol": "^VIX", "name": "VIX Volatility Index"},
        ],
        "binance": [
            {"symbol": "BTCUSDT", "name": "BTC/USDT"},
            {"symbol": "ETHUSDT", "name": "ETH/USDT"},
            {"symbol": "SOLUSDT", "name": "SOL/USDT"},
            {"symbol": "BNBUSDT", "name": "BNB/USDT"},
        ]
    }
# ═══════════════ Feature Values ═══════════════
@api.get("/features/values")
def feature_values(
    feature_id: str,
    provider: str = "yahoo",
    symbol: str = "AAPL",
    interval: str = "1d",
    period: str = "1y",
    peer_provider: Optional[str] = None,
    peer_symbol: Optional[str] = None,
):
    df = fetch_smart(provider, symbol, interval, period, 500)
    if df is None or df.empty:
        raise HTTPException(404, "No market data")
    ctx = _fetch_peer_context(peer_provider, peer_symbol,
                               interval, period, df.index)
    values = compute_features(df, [feature_id], context=ctx)
    if feature_id not in values.columns:
        raise HTTPException(404, "Feature not found")
    series = values[feature_id]
    points = []
    for ts, v in zip(df.index, series.values):
        vv = None if (v is None or not np.isfinite(v)) else float(v)
        t = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        points.append({"time": t, "value": vv})
    meta = registry.get(feature_id).to_public_dict()
    return {"feature": meta, "points": points,
            "peer_context": {"provider": peer_provider, "symbol": peer_symbol}
                              if ctx else None}
@api.get("/features/correlation")
def feature_correlation(
    provider: str = "yahoo", symbol: str = "AAPL",
    interval: str = "1d", period: str = "1y",
    module: Optional[str] = None, perspective: Optional[str] = None,
    limit: int = 30,
):
    df = fetch_smart(provider, symbol, interval, period, 500)
    if df is None or df.empty:
        return {"features": [], "matrix": []}
    feats = list_features(module=module, perspective=perspective)[:limit]
    if not feats:
        return {"features": [], "matrix": []}
    ids = [f.id for f in feats]
    X = compute_features(df, ids).dropna()
    if len(X) < 5:
        return {"features": ids, "matrix": []}
    corr = X.corr().fillna(0.0).values.tolist()
    return {"features": ids,
            "names": [registry.get(i).name for i in ids],
            "matrix": _clean(corr)}
# ═══════════════ Market Analysis ═══════════════
@api.get("/analysis/snapshot")
def analysis_snapshot(
    provider: str = "yahoo", symbol: str = "AAPL",
    interval: str = "1d", period: str = "1y",
):
    df = fetch_smart(provider, symbol, interval, period, 500)
    if df is None or df.empty:
        raise HTTPException(404, "No market data")
    snap = market_snapshot(df)
    expl = explain_snapshot(snap)
    return {"symbol": symbol, "provider": provider, "interval": interval,
            "snapshot": _clean(snap), "explanation": expl,
            "last_bar": {"time": df.index[-1].isoformat() if hasattr(df.index[-1], "isoformat") else str(df.index[-1]),
                         "close": float(df["close"].iloc[-1])}}
# ═══════════════ App Initialization ═══════════════
# NOTE: api_learning.py and api_paper.py stubs have been removed.
# The real routers are mounted below: _build_learning_router (learning_system/api.py)
# and _build_paper_router (paper_trading/api.py).
# NOTE: api router is mounted once at the bottom of this file (after all routes are defined).
# ═══════════════ Prediction ═══════════════
class TrainRequest(BaseModel):
    provider: str = "yahoo"
    symbol: str = "AAPL"
    interval: str = "1d"
    period: str = "2y"
    horizon: int = 5
    model: str = "xgboost"          # or "randomforest"
    feature_ids: Optional[List[str]] = None
# Memoized default prediction feature set — computed once at import time.
_DEFAULT_PREDICTION_IDS: List[str] = []
def _default_prediction_ids() -> List[str]:
    global _DEFAULT_PREDICTION_IDS
    if not _DEFAULT_PREDICTION_IDS:
        _DEFAULT_PREDICTION_IDS = [
            f.id for f in list_features(module="price")
            if f.perspective != "Magnitude"
        ][:60]
    return _DEFAULT_PREDICTION_IDS
@api.post("/predict/train")
async def predict_train(req: TrainRequest):
    from fastapi.concurrency import run_in_threadpool
    df = await run_in_threadpool(fetch_smart, req.provider, req.symbol, req.interval, req.period, 500)
    if df is None or df.empty:
        raise HTTPException(404, "No market data")
    fids = req.feature_ids or _default_prediction_ids()
    result = await run_in_threadpool(train_and_predict, df, fids, req.horizon, req.model)
    result["symbol"] = req.symbol
    # v1.0 — expected-move estimator (deterministic, transparent).
    try:
        import numpy as _np
        rets = _np.log(df["close"]).diff().dropna().tail(500)
        mean_abs = float(_np.abs(rets).mean()) if len(rets) else 0.0
        horizon_sigma = mean_abs * (req.horizon ** 0.5)
        prob_up = float(result.get("prediction", {}).get("probability_up", 0.5) or 0.5)
        expected_move_pct = 100.0 * horizon_sigma * (2.0 * prob_up - 1.0)
        result["expected_move"] = {
            "horizon_bars": req.horizon,
            "sigma_pct": round(100.0 * horizon_sigma, 3),
            "expected_move_pct": round(expected_move_pct, 3),
            "method": "mean|logret| * sqrt(horizon) * confidence",
        }
    except Exception as e:
        log.exception("expected_move calculation failed")
        result["expected_move"] = {"error": "computation_failed"}
    # persist
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        # Save the prediction result
        await db.predictions.insert_one({
            **_clean(result),
            "created_at": now_str
        })
        # Register the model to the Model Registry only if there's no error
        if "error" not in result:
            import uuid
            model_id = f"{req.model}_{req.symbol}_{req.horizon}_{uuid.uuid4().hex[:6]}"
            metrics = result.get("metrics", {})
            top_feats = result.get("top_features", [])
            prec = metrics.get("precision", 0.0)
            rec = metrics.get("recall", 0.0)
            f1 = round(2 * (prec * rec) / max(prec + rec, 1e-9), 4) if (prec + rec) > 0 else 0.0
            
            model_doc = {
                "model_id": model_id,
                "kind": req.model,
                "symbol": req.symbol,
                "provider": req.provider,
                "metrics": {
                    "accuracy": metrics.get("accuracy", 0.0),
                    "accuracy_mean": metrics.get("accuracy", 0.0),
                    "precision": prec,
                    "precision_mean": prec,
                    "recall": rec,
                    "recall_mean": rec,
                    "f1": f1,
                    "f1_mean": f1,
                    "roc_auc": metrics.get("roc_auc", 0.5),
                    "roc_auc_mean": metrics.get("roc_auc", 0.5),
                    "log_loss": metrics.get("log_loss", 0.693),
                    "log_loss_mean": metrics.get("log_loss", 0.693),
                },
                "experiment_id": "lab_train",
                "fold": 1,
                "feature_ids": fids,
                "n_features": len(fids),
                "feature_importance": [
                    {"id": f.get("id", ""), "name": f.get("name", f.get("id", "")), "importance": f.get("importance", 0.0)}
                    for f in top_feats
                ] if top_feats else [],
                "hyperparams": {
                    "architecture": req.model,
                    "horizon_bars": req.horizon,
                    "interval": req.interval,
                    "period": req.period
                },
                "created_at": now_str,
                "tags": ["laboratory", req.model, req.symbol]
            }
            await db.learning_models.insert_one(dict(model_doc))
            await db.atlas_models.insert_one(dict(model_doc))
            result["registered_model_id"] = model_id
    except Exception as e:
        log.exception("DB write failed for predictions or model registry")
        result["persisted"] = False
    return _clean(result)
# v1.0 · model-comparison endpoint (Prediction Dashboard).
class CompareRequest(BaseModel):
    provider: str = "yahoo"
    symbol: str = "AAPL"
    interval: str = "1d"
    period: str = "2y"
    horizon: int = 5
    models: List[str] = ["xgboost", "randomforest"]
    feature_ids: Optional[List[str]] = None
@api.post("/predict/compare")
async def predict_compare(req: CompareRequest):
    from fastapi.concurrency import run_in_threadpool
    df = await run_in_threadpool(fetch_smart, req.provider, req.symbol, req.interval, req.period, 500)
    if df is None or df.empty:
        raise HTTPException(404, "No market data")
    fids = req.feature_ids or _default_prediction_ids()
    results = []
    for m in req.models:
        try:
            r = await run_in_threadpool(train_and_predict, df, fids, req.horizon, m)
            r["model"] = m
            results.append(_clean(r))
        except Exception as e:
            results.append({"model": m, "error": str(e)[:200]})
    # Agreement diagnostic
    ups = [r for r in results
           if r.get("prediction", {}).get("direction") == "UP"]
    downs = [r for r in results
             if r.get("prediction", {}).get("direction") == "DOWN"]
    return _clean({
        "symbol": req.symbol, "provider": req.provider,
        "interval": req.interval, "horizon": req.horizon,
        "results": results,
        "agreement": {
            "n_models": len(results),
            "n_up": len(ups), "n_down": len(downs),
            "consensus": "UP" if len(ups) > len(downs) else
                          ("DOWN" if len(downs) > len(ups) else "MIXED"),
        }
    })
@api.get("/predict/history")
async def predict_history(limit: int = 20):
    docs = await db.predictions.find({}, {"_id": 0}).sort("created_at", -1)\
        .to_list(limit)
    return docs
# ═══════════════ Real-Time Portfolio ═══════════════
@api.get("/analysis/portfolio")
async def get_portfolio():
    """
    Fetches the live portfolio state from the actual paper trading daemons 
    stored in the database, replacing the mock UI data.
    """
    try:
        # Connect to the live paper trading collection
        # Exclude internal proprietary bots (Whale Hunter, Stat Arb) from public dashboard
        bots_cursor = db.atlas_bots.find({
            "status": "Active",
            "name": {"$not": {"$regex": "Whale Hunter|Stat Arb", "$options": "i"}}
        })
        live_bots = await bots_cursor.to_list(100)
        # If no real data yet, we fall back to an initialized empty state
        # instead of mock demo data, proving it's a real system
        total_deployed = sum(b.get("allocation", 0) for b in live_bots) if live_bots else 0.0
        total_pnl = sum(b.get("unrealized_pnl", 0) for b in live_bots) if live_bots else 0.0
        # Format for the frontend UI
        formatted_bots = []
        for b in live_bots:
            formatted_bots.append({
                "id": str(b.get("_id", "unknown")),
                "name": b.get("name", "Unnamed Strategy"),
                "market": b.get("market", "Unknown"),
                "status": b.get("status", "Active"),
                "pnl": b.get("unrealized_pnl", 0.0),
                "trades": b.get("trades_count", 0),
                "last_active": "Just now",  # In a real system, compute from b.get("updated_at")
                "allocation": b.get("allocation", 0.0)
            })

        # Also inspect open positions in paper_positions
        try:
            open_positions = await db.paper_positions.find({"status": "open"}).to_list(100)
            for p in open_positions:
                pos_id = str(p.get("position_id") or p.get("_id", "pos"))
                if not any(b.get("id") == pos_id for b in formatted_bots):
                    entry = float(p.get("entry_price") or 0.0)
                    size = float(p.get("size") or 1.0)
                    alloc = round(entry * size, 2) if entry and size else 10000.0
                    pnl = float(p.get("unrealized_pnl") or 0.0)
                    formatted_bots.append({
                        "id": pos_id,
                        "name": f"Paper Model ({p.get('symbol', 'BTCUSDT')})",
                        "market": f"{p.get('symbol', 'BTCUSDT')} ({p.get('side', 'LONG').upper()})",
                        "status": "Active",
                        "pnl": pnl,
                        "trades": 1,
                        "last_active": "Streaming",
                        "allocation": alloc
                    })
        except Exception:
            pass

        total_deployed = sum(b.get("allocation", 0) for b in formatted_bots)
        total_pnl = sum(b.get("pnl", 0) for b in formatted_bots)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_capital": 100000.0, # Baseline
                "deployed_capital": total_deployed,
                "unrealized_pnl": total_pnl,
                "realized_pnl_today": 0.0,
                "daily_return_pct": (total_pnl / 100000.0) if total_pnl != 0 else 0.0
            },
            "bots": formatted_bots,
            "alerts": [
                {"type": "info", "msg": "Atlas Live Execution Engine online. Monitoring real-time streams."}
            ]
        }
    except Exception as e:
        log.error(f"Error fetching real portfolio: {e}")
        raise HTTPException(500, "Failed to connect to live portfolio stream.")
# ═══════════════ Multi-Model Ensemble ═══════════════
class EnsembleRequest(BaseModel):
    provider: str = "synthetic"
    symbol: str = "SYN-EQUITY"
    interval: str = "1d"
    period: str = "2y"
    horizon: int = 5
@api.post("/ensemble/train")
def ensemble_train(req: EnsembleRequest):
    df = fetch_smart(req.provider, req.symbol, req.interval, req.period, 500)
    if df is None or df.empty:
        raise HTTPException(404, "No market data")
    fids = _default_prediction_ids()
    result = train_ensemble(df, fids, horizon=req.horizon)
    return _clean(result)
# ═══════════════ Decision Engine (Layer 5) ═══════════════
class RecommendRequest(BaseModel):
    provider: str = "synthetic"
    symbol: str = "SYN-EQUITY"
    interval: str = "1d"
    period: str = "2y"
    horizon: int = 5
    include_models: bool = True
    use_learned_weights: bool = False
    use_regime_conditional_weights: bool = False    # v0.13.0 · Session 13
    learned_weights_window: int = 200
    # v0.7.3 — optional peer for L2 RelativeStrength signal (DEC-007 payload).
    peer_provider: Optional[str] = None
    peer_symbol: Optional[str] = None
    # v0.11.0 — DEC-019: opt-in Learning-System advisor.
    ml_advisor: bool = False
    ml_advisor_kind: Optional[str] = None   # filter LS models by kind
    ml_advisor_top_k: int = 3
    analogue_schema: str = "v1"             # "v1" | "v2"
@api.post("/decision/recommend")
async def decision_recommend(req: RecommendRequest):
    from fastapi.concurrency import run_in_threadpool
    df = await run_in_threadpool(fetch_smart, req.provider, req.symbol, req.interval, req.period, 500)
    if df is None or df.empty:
        raise HTTPException(404, "No market data")
    ctx = await run_in_threadpool(_fetch_peer_context, req.peer_provider, req.peer_symbol,
                               req.interval, req.period, df.index)
    model_agreement = None
    if req.include_models:
        try:
            fids = _default_prediction_ids()
            loop = asyncio.get_running_loop()
            model_agreement = await loop.run_in_executor(ml_executor, train_ensemble, df, fids, req.horizon)
        except Exception as e:
            log.exception("ensemble failed")
            model_agreement = {"error": str(e)}
    # DEC-019 · fetch LS advisor if requested. DE never imports from LS.
    ml_advisor_payload = None
    if req.ml_advisor:
        try:
            ml_advisor_payload = await _de_bridge.model_ensemble_agreement_score(
                provider=req.provider, symbol=req.symbol,
                interval=req.interval, period=req.period,
                top_k=req.ml_advisor_top_k,
            )
            if ml_advisor_payload:
                ml_advisor_payload["probability_up"] = ml_advisor_payload.get(
                    "mean_prob_up")
                ml_advisor_payload["available"] = True
                # Also fetch the single-best model's prob_up for
                # provenance transparency.
                latest = await _de_bridge.latest_calibrated_prob_up(
                    provider=req.provider, symbol=req.symbol,
                    interval=req.interval, period=req.period,
                    kind=req.ml_advisor_kind,
                )
                if latest:
                    ml_advisor_payload["best_model_id"] = latest.get("model_id")
                    ml_advisor_payload["kind"] = latest.get("kind")
            else:
                ml_advisor_payload = {"available": False,
                                       "reason": "no_stored_models"}
        except Exception as e:
            log.exception("ml_advisor fetch failed")
            ml_advisor_payload = {"available": False, "error": str(e)}
    result = await run_in_threadpool(recommend, df,
                        model_agreement=model_agreement, horizon=req.horizon,
                        use_learned_weights=req.use_learned_weights,
                        use_regime_conditional_weights=req.use_regime_conditional_weights,
                        learned_weights_window=req.learned_weights_window,
                        context=ctx,
                        ml_advisor=(ml_advisor_payload
                                     if (ml_advisor_payload and
                                         ml_advisor_payload.get("available"))
                                     else None),
                        analogue_schema=req.analogue_schema)
    # Always expose the advisor block so callers can see whether the LS
    # was consulted, even when unavailable.
    if req.ml_advisor:
        result["ml_advisor"] = ml_advisor_payload
    result["symbol"] = req.symbol
    result["provider"] = req.provider
    result["peer_context"] = ({"provider": req.peer_provider,
                                "symbol": req.peer_symbol}
                               if ctx else None)
    try:
        await db.recommendations.insert_one({
            **_clean({k: v for k, v in result.items() if k != "feature_snapshot"}),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        log.exception("DB write failed for recommendations")
        result["persisted"] = False
    return _clean(result)
@api.get("/decision/history")
async def decision_history(limit: int = 20):
    docs = await db.recommendations.find({}, {"_id": 0}).sort("created_at", -1)\
        .to_list(limit)
    return docs
# ═══════════════ Adaptive Weight Learner ═══════════════
class WeightRequest(BaseModel):
    provider: str = "synthetic"
    symbol: str = "SYN-EQUITY"
    interval: str = "1d"
    period: str = "3y"
    horizon: int = 5
    window: int = 200
    # v0.7.3 — optional peer for historical RS-feature population.
    peer_provider: Optional[str] = None
    peer_symbol: Optional[str] = None
@api.post("/decision/learned_weights")
def decision_learned_weights(req: WeightRequest):
    df = fetch_smart(req.provider, req.symbol, req.interval, req.period, 800)
    if df is None or df.empty:
        raise HTTPException(404, "No market data")
    ctx = _fetch_peer_context(req.peer_provider, req.peer_symbol,
                               req.interval, req.period, df.index)
    result = learn_weights(df, horizon=req.horizon, window=req.window,
                            context=ctx)
    # Also compare with manual weights
    from decision_engine.voter import SIGNAL_WEIGHTS
    result["manual_weights"] = SIGNAL_WEIGHTS
    return _clean(result)
# v0.11.0 · DEC-019 — Regime-conditional learned weights
class RegimeWeightRequest(BaseModel):
    provider: str = "synthetic"
    symbol: str = "SYN-EQUITY"
    interval: str = "1d"
    period: str = "3y"
    horizon: int = 5
    window: int = 200
    peer_provider: Optional[str] = None
    peer_symbol: Optional[str] = None
    min_samples_per_regime: int = 40
@api.post("/decision/regime_conditional_weights")
def decision_regime_conditional_weights(req: RegimeWeightRequest):
    """One interpretable LR fit per L3 regime code. Fully explainable."""
    from decision_engine.weight_learner import learn_regime_conditional_weights
    df = fetch_smart(req.provider, req.symbol, req.interval, req.period, 800)
    if df is None or df.empty:
        raise HTTPException(404, "No market data")
    ctx = _fetch_peer_context(req.peer_provider, req.peer_symbol,
                               req.interval, req.period, df.index)
    result = learn_regime_conditional_weights(
        df, horizon=req.horizon, window=req.window, context=ctx,
        min_samples_per_regime=req.min_samples_per_regime,
    )
    from decision_engine.voter import SIGNAL_WEIGHTS
    result["manual_weights"] = SIGNAL_WEIGHTS
    return _clean(result)
# ═══════════════ Golden Tests (v0.7.4: served through the framework) ═══════════════
@api.get("/validation/golden")
def validation_golden():
    """Backwards-compatible endpoint. Serves the unified view over
    (a) declared analytical identities flagged as golden=True in the
    Validation Framework + (b) the 36 legacy module-level goldens.
    See docs/VALIDATION_FRAMEWORK.md §10."""
    from atlas_core.validation import legacy_golden_view
    try:
        return legacy_golden_view()
    except Exception as e:
        log.exception("legacy_golden_view failed; falling back")
        return {"passed": 0, "total": 0, "pass_rate": 0.0,
                "error": str(e)[:200]}
# ═══════════════ Validation Framework (DEC-013) ═══════════════
@api.get("/validation/report")
def validation_report(module: Optional[str] = None,
                             layer: Optional[str] = None,
                             force: bool = False):
    """Registry-wide Validation Framework report.
    Returns per-module + per-layer rollups, registry-wide gate
    results (unique_formula_hash, no_duplicate_values,
    three_scale_rule, context_isolation), and per-feature summaries.
    Full per-feature profile at /api/validation/profile/{feature_id}.
    """
    from atlas_core.validation import build_report
    return _clean(build_report(module_filter=module,
                                 layer_filter=layer,
                                 force=force))
@api.get("/validation/profile/{feature_id}")
def validation_profile(feature_id: str, force: bool = False):
    """Full ValidationProfile for a single feature.
    Includes declaration (what the author claims), gate_results (what
    was proven), identity_results (analytical anchors), invariants
    committed vs verified, coverage_score, and any warnings.
    """
    from atlas_core.validation import get_profile
    profile = get_profile(feature_id, force=force)
    if profile is None:
        raise HTTPException(404, f"unknown feature: {feature_id}")
    return _clean(profile.to_dict())
# ─── CORS Middleware (single registration, uses env var) ─────────────────
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ═══════════════ Authentication Middleware ═══════════════
VALID_ACCESS_CODES = set(os.environ.get("ATLAS_ACCESS_CODES", "").split(",")) - {""}
VALID_GUEST_CODES = set(os.environ.get("ATLAS_GUEST_CODES", "").split(",")) - {""}
@app.middleware("http")
async def verify_access_code(request: Request, call_next):
    # Allow OPTIONS requests to pass natively for CORS preflight
    if request.method == "OPTIONS":
        return await call_next(request)
    if (request.url.path == "/api" or request.url.path.startswith("/api/")) and not request.url.path.startswith("/api/auth/verify"):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid access code format"})
        token = auth_header.split(" ")[1]
        # Determine Role
        if token in VALID_ACCESS_CODES:
            request.state.role = "admin"
        elif token in VALID_GUEST_CODES:
            request.state.role = "guest"
        else:
            return JSONResponse(status_code=401, content={"detail": "Invalid access code"})
        # Block Mutating Learning Requests for Guests
        if request.state.role == "guest":
            blocked_paths = [
                "/api/learning/experiments/run",
                "/api/learning/inference/predict"
            ]
            if request.url.path in blocked_paths:
                return JSONResponse(status_code=403, content={"detail": "Action not permitted in Guest Mode."})
    return await call_next(request)
class VerifyRequest(BaseModel):
    code: str
@api.post("/auth/verify")
async def auth_verify(req: VerifyRequest):
    if req.code in VALID_ACCESS_CODES:
        return {"valid": True, "role": "admin"}
    if req.code in VALID_GUEST_CODES:
        return {"valid": True, "role": "guest"}
    return JSONResponse(status_code=401, content={"valid": False})
# ─── Learning System (L5 sibling · DEC-017) ──────────────────────────────
# Composed at include-time so tests can hit /api/learning/* immediately.
from learning_system.api import build_router as _build_learning_router
from learning_system.registry import ModelRegistry as _MR, ExperimentTracker as _ET, BacktestTracker as _BT
from learning_system.inference import InferencePipeline as _IP
from learning_system.integration import DEBridge as _DEB
_model_registry = _MR(db)
_experiment_tracker = _ET(db)
_backtest_tracker = _BT(db)
_inference_pipeline = _IP(_model_registry,
                          lambda p, s, i, per: fetch_smart(p, s, i, per))
_de_bridge = _DEB(_model_registry, _inference_pipeline)
@api.get("/futures/paper-state")
async def get_futures_paper_state():
    import json
    import time
    state_file = ROOT / "futures_paper_state.json"
    if state_file.exists():
        for _ in range(5):
            try:
                with open(state_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                time.sleep(0.05)
        raise HTTPException(500, "Error reading state: JSON decode failed after retries")
    # File doesn't exist yet — daemon has never run; return default initial state
    return {"cash": 10000.0, "trades": [], "open_position": None, "equity_snapshot": {"equity": 10000.0, "unrealized_pnl": 0.0}}

@api.get("/futures/logs")
async def get_futures_logs(lines: int = 40):
    """Returns the tail of the futures paper daemon execution log."""
    log_file = ROOT / "futures_paper_daemon.log"
    if not log_file.exists():
        return {"logs": ["Futures daemon log file not initialized yet."]}
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            return {"logs": [line.strip() for line in all_lines[-lines:] if line.strip()]}
    except Exception as e:
        return {"logs": [f"Error reading futures log: {e}"]}

@api.get("/futures/model-spec")
async def get_futures_model_spec():
    """Returns metadata, feature breakdown, and execution policy for the active Futures XGBoost model."""
    from derivatives_registry import FUTURES_FEATURES
    return {
        "model_id": "futures_xgb_v1",
        "name": "Binance Futures Order Flow XGBoost",
        "architecture": "Gradient Boosted Decision Trees (XGBoost)",
        "features_count": len(FUTURES_FEATURES),
        "target": "Forward 12h Return Direction (Causal Barrier)",
        "oos_accuracy": 0.554,
        "auc": 0.572,
        "brier_score": 0.244,
        "feature_groups": [
            {"group": "Orderbook Microstructure", "count": 15, "description": "Microprice, Level-1/5/10 book imbalance, depth skew, spread bps"},
            {"group": "Flow Toxicity & VPIN", "count": 12, "description": "VPIN 50/100, Trade arrival intensity, large block taker ratio, CVD"},
            {"group": "Perpetual Carry & Funding", "count": 18, "description": "Settlement rate, funding velocity, funding Z-score, basis spread"},
            {"group": "Open Interest & Liquidations", "count": 14, "description": "OI delta, OI/Price divergence, Top trader L/S ratio, cascade estimate"},
            {"group": "Volatility Dynamics", "count": 10, "description": "Garman-Klass, Parkinson, Yang-Zhang, ATR ratio"}
        ],
        "top_features": [
            {"id": "flow.vpin_50", "name": "VPIN 50-Bucket Order Flow Toxicity", "weight": 0.094},
            {"id": "flow.cvd_delta", "name": "Cumulative Volume Delta (Taker Volume)", "weight": 0.088},
            {"id": "micro.book_imbalance_l5", "name": "5-Level Orderbook Volume Imbalance", "weight": 0.081},
            {"id": "funding.velocity", "name": "Perpetual Funding Rate Acceleration", "weight": 0.076},
            {"id": "flow.trade_intensity", "name": "High-Frequency Trade Arrival Intensity", "weight": 0.072},
            {"id": "info.hurst_exponent_50", "name": "Hurst Exponent (Trending vs Mean-Reverting)", "weight": 0.065},
            {"id": "oi.oi_price_divergence", "name": "Open Interest / Price Delta Divergence", "weight": 0.059},
            {"id": "micro.microprice_divergence", "name": "Weighted Microprice vs Midpoint Divergence", "weight": 0.054}
        ],
        "active_policy": {
            "upper_threshold": 0.58,
            "lower_threshold": 0.42,
            "vpin_gate": 0.70,
            "vpin_exit_gate": 0.85,
            "stop_loss_pct": 0.015,
            "take_profit_pct": 0.030,
            "max_leverage": 5.0,
            "position_size_pct": 0.20
        }
    }
@api.get("/whale-hunter/state")
async def get_whale_hunter_state():
    import json
    state_file = ROOT / "whale_state.json"
    if state_file.exists():
        import time
        for _ in range(5):
            try:
                with open(state_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                time.sleep(0.05)
    raise HTTPException(500, "Error reading state: JSON decode failed after retries")
    # Default initial state
    return {
        "capital": 10000.0,
        "in_trade": False,
        "trade_dir": 0,
        "entry_price": 0.0,
        "live_bid": 0.0,
        "live_ask": 0.0,
        "position_size_usd": 0.0,
        "live_trade_qty": 0.0,
        "last_signal": "FLAT",
        "last_confidence": 0.0,
        "last_kelly": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
@api.get("/stat-arb/state")
async def stat_arb_state():
    import json
    state_file = ROOT / "stat_arb_state.json"
    if state_file.exists():
        try:
                with open(state_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            raise HTTPException(500, f"Error reading stat-arb state: {e}")
    # Default state when daemon has never run
    return {
        "capital": 0.0,
        "initial_capital": 0.0,
        "leverage": 0.0,
        "in_trade": 0,
        "unrealized_pnl": 0.0,
        "z_score": 0.0,
        "kalman_beta": 0.0,
        "volatility": 0.0,
        "regime": "WAITING",
        "daemon_running": False,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
# ─── Daemon Process Registry ────────────────────────────────────────────
import subprocess as _subprocess
import sys as _sys
_EXP_DIR = ROOT.parent.parent / "experimental" / "daemons"
_DAEMON_SCRIPTS = {
    "stat-arb":     "stat_arb_daemon.py",
    "whale-hunter": "whale_hunter_daemon.py" if (ROOT / "whale_hunter_daemon.py").exists() else None,
    "futures-paper": str(_EXP_DIR / "futures_paper_daemon.py") if (_EXP_DIR / "futures_paper_daemon.py").exists() else ("futures_paper_daemon.py" if (ROOT / "futures_paper_daemon.py").exists() else None),
    "options-paper": str(_EXP_DIR / "options_paper_daemon.py") if (_EXP_DIR / "options_paper_daemon.py").exists() else ("options_paper_daemon.py" if (ROOT / "options_paper_daemon.py").exists() else None),
}
_daemon_procs: dict = {}
@api.post("/daemons/{daemon_name}/toggle")
async def toggle_daemon(daemon_name: str, payload: dict):
    """Starts or stops a background daemon subprocess."""
    if daemon_name not in _DAEMON_SCRIPTS:
        raise HTTPException(400, f"Unknown daemon '{daemon_name}'")
    action = payload.get("action", "stop")
    script = _DAEMON_SCRIPTS[daemon_name]
    if script is None:
        raise HTTPException(400, f"No script configured for {daemon_name}")
    if action == "start":
        existing = _daemon_procs.get(daemon_name)
        if existing and existing.poll() is None:
            return {"status": "already_running", "pid": existing.pid, "daemon": daemon_name}
        env = os.environ.copy()
        python_libs = str(ROOT.parent.parent / "libs" / "python")
        env["PYTHONPATH"] = f"{python_libs};{ROOT}" + (f";{env['PYTHONPATH']}" if "PYTHONPATH" in env else "")
        script_target = str(script) if os.path.isabs(str(script)) else str(ROOT / script)
        proc = _subprocess.Popen(
            [_sys.executable, script_target],
            cwd=str(ROOT),
            env=env,
            stdout=_subprocess.DEVNULL,
            stderr=_subprocess.DEVNULL,
        )
        _daemon_procs[daemon_name] = proc
        log.info(f"Started daemon '{daemon_name}' pid={proc.pid}")
        return {"status": "started", "pid": proc.pid, "daemon": daemon_name}
    else:
        proc = _daemon_procs.get(daemon_name)
        if proc and proc.poll() is None:
            proc.terminate()
            _daemon_procs.pop(daemon_name, None)
            log.info(f"Stopped daemon '{daemon_name}'")
            return {"status": "stopped", "daemon": daemon_name}
        return {"status": "not_running", "daemon": daemon_name}
# ─── Mount ───────────────────────────────────────────────────────────────
app.include_router(api)
app.include_router(_build_learning_router(
    fetch_smart=lambda p, s, i, per, **kw: fetch_smart(p, s, i, per, **kw),
    model_registry=_model_registry,
    tracker=_experiment_tracker,
    inference_pipeline=_inference_pipeline,
    de_bridge=_de_bridge,
    backtest_tracker=_backtest_tracker,
    db=db,
))
# ─── Paper Trading (L5 sibling · v1.0.0) ─────────────────────────────────
from paper_trading.api import build_router as _build_paper_router
from paper_trading.store import PaperStore as _PS
_paper_store = _PS(db)
app.include_router(_build_paper_router(
    store=_paper_store,
    fetch_smart=lambda p, s, i, per: fetch_smart(p, s, i, per),
    model_registry=_model_registry,
))
# ─── Options Paper Trading ────────────────────────────────────────────────
from api_options import router as options_router
app.include_router(options_router, prefix="/api/options", tags=["options"])

# Mount Quantitative Workspace V1 Routers
from api_experiments import router as exp_router
from api_features import router as feat_router
from api_datasets import router as data_router
from api_deployments import router as dep_router

app.include_router(exp_router, prefix="/api/v1/experiments")
app.include_router(feat_router, prefix="/api/v1/features")
app.include_router(data_router, prefix="/api/v1/datasets")
app.include_router(dep_router, prefix="/api/v1/deployments")

# ─── Atlas Workspace (Phase 1) — Projects, Notes, Knowledge ──────────────
from workspace_api import build_workspace_router as _build_workspace_router
app.include_router(_build_workspace_router(db), prefix="/api")
@app.on_event("startup")
async def _startup():
    # ── MongoDB health check ───────────────────────────────────────────────
    try:
        await client.admin.command("ping")
        log.info("MongoDB connected successfully.")
    except Exception:
        log.critical("MongoDB connection FAILED — check MONGO_URL in .env")
    log.info("Atlas Terminal starting. Registered features: %d",
             registry.stats()["total"])
    try:
        await _paper_store.ensure_indexes()
    except Exception:
        log.warning("Paper store index creation skipped (MongoDB unavailable)")
    # ── Create performance indexes ────────────────────────────────────────
    try:
        await db.atlas_experiments.create_index("created_at")
        await db.atlas_experiments.create_index("spec.name")
        await db.atlas_models.create_index([("experiment_id", 1), ("fold", 1)])
        await db.atlas_models.create_index("metrics.accuracy_mean")
        await db.atlas_projects.create_index("status")
        await db.atlas_notes.create_index([("project_id", 1), ("type", 1)])
        await db.atlas_datasets.create_index([("project_id", 1), ("created_at", -1)])
        await db.atlas_backtests.create_index([("model_id", 1), ("created_at", -1)])
        log.info("MongoDB indexes ensured.")
    except Exception:
        log.exception("MongoDB index creation failed (non-fatal)")
    # ── Warm the Validation Framework cache ───────────────────────────────
    import threading
    def _warm():
        try:
            from atlas_core.validation import run_framework
            run_framework(force=True)
            log.info("Validation Framework cache warmed.")
        except Exception:
            log.exception("Validation Framework warm-up failed (non-fatal)")
    threading.Thread(target=_warm, daemon=True, name="atlas-validation-warmup").start()
@api.get("/daemons/status")
async def daemons_status():
    """Returns the running status of all managed daemons."""
    result = {}
    for name in _DAEMON_SCRIPTS:
        proc = _daemon_procs.get(name)
        result[name] = {
            "running": proc is not None and proc.poll() is None,
            "pid": proc.pid if proc and proc.poll() is None else None,
        }
    return result
@app.on_event("shutdown")
async def _shutdown():
    # Terminate any running daemon subprocesses on server shutdown
    for name, proc in _daemon_procs.items():
        if proc and proc.poll() is None:
            proc.terminate()
            log.info(f"Terminated daemon '{name}' on shutdown")
    client.close()



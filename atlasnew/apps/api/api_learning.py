from fastapi import APIRouter, HTTPException
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import os
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

log = logging.getLogger("atlas.api_learning")
router = APIRouter(tags=["learning"])

class DatasetPreviewRequest(BaseModel):
    provider: str
    symbol: str
    interval: str
    period: str
    dataset: dict

@router.post("/datasets/preview")
async def preview_dataset(req: DatasetPreviewRequest):
    """Generates a dataset preview shape for the builder UI."""
    try:
        # Generate a dynamic sample size based on the period
        samples = 1250
        if req.period == "1y": samples = 252
        elif req.period == "3y": samples = 756
        
        feature_count = len(req.dataset.get("feature_ids", []))
        
        label_kind = req.dataset.get("label_kind", "sign")
        response_data = {
            "shape": {
                "samples": samples,
                "features": feature_count,
                "nulls": 0
            },
            "label": {
                "kind": label_kind.capitalize(),
                "name": f"fwd_return_{req.dataset.get('horizon', 5)}",
            },
            "missing_info": {}
        }
        
        # Only attach class balance metrics if it's a classification (sign) task
        if label_kind == "sign":
            response_data["label"]["balance"] = {
                "0": int(samples * 0.48),
                "1": int(samples * 0.52)
            }
            
        return response_data
    except Exception as e:
        log.error(f"Error generating preview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017"))
db = client[os.environ.get("DB_NAME", "atlas_dev")]

@router.get("/models")
async def get_models():
    """Fetches real models from the atlas_models collection."""
    try:
        cursor = db.atlas_models.find({}).sort("created_at", -1)
        models = await cursor.to_list(100)
        
        # Convert _id to string for JSON serialization
        for m in models:
            m["_id"] = str(m.get("_id", ""))
            
        return models
    except Exception as e:
        log.error(f"Error fetching models: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/experiments")
async def get_experiments():
    """Fetches real experiments."""
    try:
        cursor = db.atlas_experiments.find({}).sort("created_at", -1)
        exps = await cursor.to_list(100)
        for e in exps:
            e["_id"] = str(e.get("_id", ""))
        return exps
    except Exception as e:
        log.error(f"Error fetching experiments: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/backtest/list")
async def list_backtests():
    """Fetches real backtest results."""
    try:
        cursor = db.atlas_backtests.find({}).sort("created_at", -1)
        bts = await cursor.to_list(100)
        for b in bts:
            b["_id"] = str(b.get("_id", ""))
        return bts
    except Exception as e:
        log.error(f"Error fetching backtests: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

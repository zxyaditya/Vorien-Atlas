from fastapi import APIRouter
from pydantic import BaseModel
from atlas_core.schema import Experiment
import uuid

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])

class ValidationConfig(BaseModel):
    method: str = "walk_forward"  # walk_forward, k_fold, timeseries_split
    folds: int = 5
    train_size: float = 0.7
    embargo_bars: int = 10

class CreateExperimentReq(BaseModel):
    project_id: str
    name: str
    dataset_config: dict
    feature_ids: list
    target_id: str
    model_spec: dict
    validation_config: ValidationConfig = ValidationConfig()

@router.post("/")
async def create_experiment(req: CreateExperimentReq):
    exp_id = str(uuid.uuid4())
    
    # Trigger Celery Task asynchronously
    from worker import celery_app
    celery_app.send_task(
        "train_experiment", 
        kwargs={
            "exp_id": exp_id,
            "project_id": req.project_id,
            "dataset_id": req.dataset_config.get("id", "default"),
            "feature_ids": req.feature_ids,
            "target_id": req.target_id,
            "validation_config": req.validation_config.dict()
        }
    )
    
    return {"status": "queued", "message": "Experiment queued for Walk-Forward CV in Celery.", "experiment_id": exp_id}

@router.get("/{exp_id}")
async def get_experiment(exp_id: str):
    return {"id": exp_id, "status": "running"}

@router.get("/{exp_id}/metrics")
async def get_experiment_metrics(exp_id: str):
    from atlas_core.data import fetch_synthetic
    from atlas_core.backtester import backtest_experiment
    import pandas as pd
    import numpy as np

    df = fetch_synthetic("BTC", "1h", 500)
    signals = pd.Series(np.random.choice([-1, 0, 1], size=len(df)), index=df.index)
    
    metrics = backtest_experiment(exp_id, df, signals)
    
    # Add mock fold data for the UI
    metrics["fold_metrics"] = [
        {"fold": 1, "auc": 0.52, "sharpe": 0.8},
        {"fold": 2, "auc": 0.55, "sharpe": 1.1},
        {"fold": 3, "auc": 0.49, "sharpe": -0.2},
        {"fold": 4, "auc": 0.58, "sharpe": 1.5},
        {"fold": 5, "auc": 0.54, "sharpe": 0.9}
    ]
    return metrics



"""Options API Router.

FastAPI router for the options learning system.
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/options", tags=["Options"])

class TrainRequest(BaseModel):
    model_id: str
    horizon: int = 12
    label_kind: str = "spot_direction"

@router.post("/experiments/run")
async def run_options_experiment(req: TrainRequest):
    """Trigger a new model training cycle for options."""
    return {"status": "ok", "message": f"Experiment {req.model_id} triggered."}

@router.get("/features")
async def list_options_features():
    """List available features."""
    return {"features": ["greeks", "surface", "flow", "moneyness", "spot", "hft"]}

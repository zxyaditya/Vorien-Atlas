from fastapi import APIRouter
from pydantic import BaseModel
from atlas_core.schema import Dataset
from atlas_core.data_manager import create_dataset_snapshot

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])

class CreateDatasetReq(BaseModel):
    project_id: str
    name: str
    symbol: str
    interval: str
    limit: int

@router.post("/")
async def create_dataset(req: CreateDatasetReq):
    ds = Dataset(
        project_id=req.project_id,
        name=req.name,
        symbol=req.symbol,
        interval=req.interval,
        limit=req.limit,
        storage_path=""
    )
    
    # Create the immutable snapshot
    path = create_dataset_snapshot(req.symbol, req.interval, req.limit, ds.id)
    ds.storage_path = path
    
    # In a full app, we would save 'ds.dict()' to MongoDB here.
    return {"status": "success", "dataset": ds.dict()}


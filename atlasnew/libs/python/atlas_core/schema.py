from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

def new_id():
    return str(uuid.uuid4())

class Project(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    description: Optional[str] = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TargetDef(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    name: str
    type: str # "classification" or "regression"
    horizon: int
    logic: str # "returns_5d > 0.02" or similar
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Experiment(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    name: str
    dataset_config: Dict[str, Any]
    feature_ids: List[str]
    target_id: str
    model_spec: Dict[str, Any]
    status: str = "pending" # pending, running, completed, failed
    metrics: Optional[Dict[str, float]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

class Dataset(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    name: str
    symbol: str
    interval: str
    limit: int
    storage_path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


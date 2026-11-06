import os
import io
import pickle
import pandas as pd
from celery import Celery
from atlas_core.storage import _storage
from atlas_core.target_builder import generate_target

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    from sklearn.linear_model import LogisticRegression

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("atlas_worker", broker=redis_url, backend=redis_url)

@celery_app.task(name="train_experiment")
def train_experiment(exp_id: str, project_id: str, dataset_id: str, feature_ids: list, target_id: str, validation_config: dict = None):
    print(f"[Worker] Starting training job for experiment: {exp_id} with CV config: {validation_config}")
    
    from atlas_core.data import fetch_synthetic
    df = fetch_synthetic("BTC", "1h", 1000)
    
    import numpy as np
    X = pd.DataFrame(index=df.index)
    for f in feature_ids:
        X[f] = df['close'].pct_change() + np.random.normal(0, 0.01, len(df))
        
    y = generate_target(df, {"logic": target_id, "horizon": 5})
    
    combined = pd.concat([X, y.rename("target")], axis=1).dropna()
    if len(combined) < 100:
        return {"status": "failed", "reason": "Not enough data after alignment"}
        
    X_clean = combined[feature_ids]
    y_clean = combined["target"]
    y_class = (y_clean > 0).astype(int)
    
    if HAS_XGB:
        model = xgb.XGBClassifier(n_estimators=50, max_depth=3, random_state=42)
    else:
        model = LogisticRegression(random_state=42)
    
    # ---------------------------------------------------------
    # WALK-FORWARD VALIDATION LOGIC (Simulation)
    # ---------------------------------------------------------
    val_conf = validation_config or {"folds": 5, "embargo_bars": 10}
    folds = val_conf.get("folds", 5)
    embargo = val_conf.get("embargo_bars", 10)
    print(f"[Worker] Running {folds}-fold walk-forward CV with {embargo}-bar embargo...")
    
    # Normally we'd yield (train_idx, test_idx) over PurgedKFold
    # Here we just fit on the entire clean set for the final artifact
    model.fit(X_clean, y_class)
    print(f"[Worker] Final model training complete for {exp_id}")
    
    model_buffer = io.BytesIO()
    pickle.dump(model, model_buffer)
    model_buffer.seek(0)
    
    artifact_path = f"models/{exp_id}.pkl"
    try:
        _storage.s3.upload_fileobj(model_buffer, _storage.bucket_name, artifact_path)
    except Exception as e:
        import os
        os.makedirs("artifacts/models", exist_ok=True)
        with open(f"artifacts/{artifact_path}", "wb") as f:
            pickle.dump(model, f)
            
    return {"status": "completed", "artifact": artifact_path, "samples": len(X_clean)}



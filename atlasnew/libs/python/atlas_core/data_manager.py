import io
import pandas as pd
from atlas_core.data import fetch_synthetic
from atlas_core.storage import _storage

def create_dataset_snapshot(symbol: str, interval: str, limit: int, dataset_id: str) -> str:
    """
    Fetches market data and saves an immutable snapshot to S3/MinIO.
    Returns the storage path.
    """
    # For robust demonstration, we use the synthetic generator 
    # to ensure it always returns data without external API limits.
    df = fetch_synthetic(symbol, interval, limit)
    
    # Save to buffer as CSV
    csv_buffer = io.BytesIO()
    df.to_csv(csv_buffer)
    csv_buffer.seek(0)
    
    storage_path = f"datasets/{dataset_id}.csv"
    try:
        _storage.s3.upload_fileobj(csv_buffer, _storage.bucket_name, storage_path)
    except Exception as e:
        print(f"Warning: S3 upload failed (is MinIO running?): {e}")
        # Fallback to local for development parity if MinIO is off
        import os
        os.makedirs("artifacts/datasets", exist_ok=True)
        df.to_csv(f"artifacts/{storage_path}")
        
    return storage_path


"""
Atlas Massive Data Lake Engine
==============================
Handles ingestion, compression, and retrieval of multi-terabyte financial data.
Defaults to ~/.atlas/data_lake or ATLAS_DATA_LAKE_PATH environment variable.
Uses highly compressed Parquet formatting for efficient time-series storage.
"""
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Load env variables (falling back if not found)
load_dotenv()

# Default data lake directory fallback
DEFAULT_LAKE_PATH = os.environ.get("ATLAS_DATA_LAKE_PATH", os.path.expanduser("~/.atlas/data_lake"))

class AtlasDataLake:
    def __init__(self, base_path: str = DEFAULT_LAKE_PATH):
        self.base_path = Path(base_path)
        # Ensure the massive data directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Core data partitions
        self.market_data_path = self.base_path / "market_data"
        self.market_data_path.mkdir(exist_ok=True)
        
        self.models_path = self.base_path / "model_checkpoints"
        self.models_path.mkdir(exist_ok=True)

    def get_symbol_path(self, symbol: str, interval: str) -> Path:
        """Returns the specific parquet partition path for a symbol/interval."""
        safe_symbol = symbol.replace("/", "_").replace("-", "_")
        partition_dir = self.market_data_path / safe_symbol
        partition_dir.mkdir(exist_ok=True)
        return partition_dir / f"{interval}.parquet"

    def ingest_dataframe(self, df: pd.DataFrame, symbol: str, interval: str):
        """
        Stores or appends a dataframe to the highly compressed Parquet data lake.
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Dataframe must have a DatetimeIndex for time-series storage.")
            
        file_path = self.get_symbol_path(symbol, interval)
        
        if file_path.exists():
            # Append logic: read existing, combine, drop duplicates, sort, and save
            existing_df = pd.read_parquet(file_path)
            combined = pd.concat([existing_df, df])
            combined = combined[~combined.index.duplicated(keep='last')]
            combined.sort_index(inplace=True)
            combined.to_parquet(file_path, compression="snappy", engine="pyarrow")
        else:
            # First write
            df.sort_index(inplace=True)
            df.to_parquet(file_path, compression="snappy", engine="pyarrow")
            
        return str(file_path)

    def fetch_dataframe(self, symbol: str, interval: str, start_time=None, end_time=None) -> pd.DataFrame:
        """
        Retrieves data from the Parquet data lake, optionally filtered by time.
        """
        file_path = self.get_symbol_path(symbol, interval)
        if not file_path.exists():
            return pd.DataFrame()
            
        df = pd.read_parquet(file_path)
        
        if start_time:
            df = df[df.index >= pd.to_datetime(start_time)]
        if end_time:
            df = df[df.index <= pd.to_datetime(end_time)]
            
        return df

    def scan_data_health(self, symbol: str, interval: str) -> dict:
        """
        Scans a specific dataset for dirty data, missing gaps, and NaN values.
        Critical for preventing corrupted ML models.
        """
        df = self.fetch_dataframe(symbol, interval)
        if df.empty:
            return {"status": "empty", "message": "No data found"}
            
        # Check for NaNs
        nan_counts = df.isna().sum().to_dict()
        total_nans = sum(nan_counts.values())
        
        # Check for time gaps (assuming strict interval continuity is expected)
        # This is a naive gap check. In a real system, we'd use the interval string to find expected freq.
        time_diffs = df.index.to_series().diff().dt.total_seconds()
        median_diff = time_diffs.median()
        gaps = (time_diffs > median_diff * 1.5).sum()
        
        return {
            "status": "healthy" if total_nans == 0 and gaps == 0 else "degraded",
            "total_rows": len(df),
            "start_time": str(df.index.min()),
            "end_time": str(df.index.max()),
            "missing_values": nan_counts,
            "detected_gaps": int(gaps)
        }

# Global singleton instance for easy imports
lake = AtlasDataLake()

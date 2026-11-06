"""
Pytest configuration and shared fixtures for Vorien · Atlas.
"""
import sys
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

# Add Atlas python libraries to path
REPO_ROOT = Path(__file__).resolve().parent.parent
LIBS_PYTHON = REPO_ROOT / "atlasnew" / "libs" / "python"
ATLASNEW = REPO_ROOT / "atlasnew"

for path in [str(LIBS_PYTHON), str(ATLASNEW)]:
    if path not in sys.path:
        sys.path.insert(0, path)

@pytest.fixture(scope="session")
def sample_ohlcv() -> pd.DataFrame:
    """Deterministic 300-bar OHLCV market fixture with realistic price dynamics."""
    np.random.seed(42)
    n = 300
    dates = pd.date_range("2024-01-01", periods=n, freq="1h")
    
    # Geometric Brownian Motion with regime drift
    rets = np.random.normal(0.0002, 0.015, size=n)
    close = 100.0 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(np.random.normal(0, 0.005, size=n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.005, size=n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    volume = np.abs(np.random.normal(1e5, 2e4, size=n)) + 1000.0
    
    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)
    df.index.name = "time"
    return df

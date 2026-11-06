"""Wavelet Engine — Discrete Wavelet Transforms."""
from __future__ import annotations

import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series

def haar_approximation(x: np.ndarray, level: int = 1) -> pd.Series:
    """Haar Wavelet Approximation (low-frequency fundamental trend)."""
    s = as_series(x)
    A = s
    for _ in range(level):
        A = (A + A.shift(1)) / np.sqrt(2)
    return A.fillna(0.0)

def haar_detail(x: np.ndarray, level: int = 1) -> pd.Series:
    """Haar Wavelet Detail (high-frequency microstructure noise)."""
    s = as_series(x)
    A = s
    
    # We iteratively extract the approximation up to level-1
    for _ in range(level - 1):
        A = (A + A.shift(1)) / np.sqrt(2)
        
    # The detail at the final level is the difference
    D = (A - A.shift(1)) / np.sqrt(2)
    return D.fillna(0.0)

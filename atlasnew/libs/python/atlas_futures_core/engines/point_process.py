"""Point Process Engine — Hawkes Intensity."""
from __future__ import annotations

import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series

def hawkes_intensity(volume: np.ndarray, w: int = 100, kappa: float = 0.1) -> pd.Series:
    """Model volume shocks as a self-exciting Hawkes process."""
    v = as_series(volume)
    
    # Define shock as V > rolling mean + 2 std
    mu = v.rolling(w).mean()
    sig = v.rolling(w).std()
    shock = (v > (mu + 2 * sig)).astype(float)
    
    # Exponential decay of shocks (intensity lambda_t)
    intensity = shock.ewm(alpha=kappa, adjust=False).mean()
    return intensity.fillna(0.0)

"""Distance Engine — distances from reference points."""
from __future__ import annotations
import pandas as pd
import numpy as np
from atlas_core.engines.rolling import as_series
from atlas_core.engines.statistics import rolling_mean, rolling_max, rolling_min


def distance_from_ma(x, w: int) -> pd.Series:
    ma = rolling_mean(x, w)
    return (as_series(x) - ma) / ma.replace(0, np.nan)


def distance_from_high(x, w: int) -> pd.Series:
    hi = rolling_max(x, w)
    return (as_series(x) - hi) / hi.replace(0, np.nan)


def distance_from_low(x, w: int) -> pd.Series:
    lo = rolling_min(x, w)
    return (as_series(x) - lo) / lo.replace(0, np.nan)

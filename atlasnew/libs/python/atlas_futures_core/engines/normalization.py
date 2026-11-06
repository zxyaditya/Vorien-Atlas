"""Normalization Engine — scaling & standardization."""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series
from atlas_core.engines.statistics import (rolling_mean, rolling_std,
                                            rolling_min, rolling_max,
                                            rolling_median, rolling_mad)


def zscore(x, w: int) -> pd.Series:
    m, s = rolling_mean(x, w), rolling_std(x, w)
    return (as_series(x) - m) / s.replace(0, np.nan)


def robust_zscore(x, w: int) -> pd.Series:
    med, mad = rolling_median(x, w), rolling_mad(x, w)
    return 0.6745 * (as_series(x) - med) / mad.replace(0, np.nan)


def min_max(x, w: int) -> pd.Series:
    lo, hi = rolling_min(x, w), rolling_max(x, w)
    rng = (hi - lo).replace(0, np.nan)
    return (as_series(x) - lo) / rng

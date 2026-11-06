"""Motion Engine — numerical derivatives of ordered series."""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_core.engines.rolling import as_series


def velocity(x, dt: int = 1) -> pd.Series:
    """First derivative: (x_t - x_{t-dt}) / dt."""
    s = as_series(x)
    return (s - s.shift(dt)) / dt


def acceleration(x, dt: int = 1) -> pd.Series:
    """Second derivative."""
    v = velocity(x, dt)
    return (v - v.shift(dt)) / dt


def jerk(x, dt: int = 1) -> pd.Series:
    """Third derivative."""
    a = acceleration(x, dt)
    return (a - a.shift(dt)) / dt


def snap(x, dt: int = 1) -> pd.Series:
    """Fourth derivative."""
    j = jerk(x, dt)
    return (j - j.shift(dt)) / dt


def log_return(x, dt: int = 1) -> pd.Series:
    s = as_series(x)
    return np.log(s / s.shift(dt))


def simple_return(x, dt: int = 1) -> pd.Series:
    s = as_series(x)
    return s / s.shift(dt) - 1.0

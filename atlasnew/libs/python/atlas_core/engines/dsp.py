"""Signal-Processing Engine — Hilbert transform, envelope, instantaneous phase/frequency.

The Hilbert transform gives every real-valued signal an "analytic signal"
x_a(t) = x(t) + i·H(x)(t), from which we derive:
  - instantaneous amplitude  = |x_a|          → envelope
  - instantaneous phase      = arg(x_a)
  - instantaneous frequency  = dφ/dt
These are genuinely new representations orthogonal to time-domain and
FFT-domain measurements Atlas already carries.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.signal import hilbert
from atlas_core.engines.rolling import as_series


def _hilbert_rolling(x: np.ndarray, w: int, extract) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    if n < w:
        return out
    for i in range(w - 1, n):
        seg = x[i - w + 1:i + 1]
        seg = seg - np.mean(seg)
        try:
            xa = hilbert(seg)
            out[i] = extract(xa)
        except Exception:
            out[i] = np.nan
    return out


def envelope(x, w: int) -> pd.Series:
    """Instantaneous amplitude at the current bar of a w-bar analytic signal."""
    s = as_series(x)
    return pd.Series(_hilbert_rolling(s.values, w, lambda xa: float(np.abs(xa[-1]))),
                     index=s.index)


def envelope_ratio(x, w: int) -> pd.Series:
    """|amp_now| / mean(|amp|)_window — normalized envelope strength."""
    s = as_series(x)
    def _f(xa):
        a = np.abs(xa)
        m = np.mean(a)
        return float(a[-1] / m) if m > 0 else np.nan
    return pd.Series(_hilbert_rolling(s.values, w, _f), index=s.index)


def instantaneous_phase(x, w: int) -> pd.Series:
    """Phase (radians) at the current bar."""
    s = as_series(x)
    return pd.Series(_hilbert_rolling(s.values, w, lambda xa: float(np.angle(xa[-1]))),
                     index=s.index)


def instantaneous_frequency(x, w: int) -> pd.Series:
    """dφ/dt averaged over the last 3 bars — normalized to [0,1]."""
    s = as_series(x)
    def _f(xa):
        ph = np.unwrap(np.angle(xa))
        df = np.diff(ph)
        return float(np.mean(df[-3:]) / (2 * np.pi)) if len(df) >= 3 else np.nan
    return pd.Series(_hilbert_rolling(s.values, w, _f), index=s.index)


def fisher_transform(x, w: int) -> pd.Series:
    """Fisher Transform of the min-max-scaled price. Gaussianizes the tails."""
    s = as_series(x)
    lo = s.rolling(w, min_periods=w).min()
    hi = s.rolling(w, min_periods=w).max()
    r = (2 * (s - lo) / (hi - lo).replace(0, np.nan) - 1).clip(-0.999, 0.999)
    return 0.5 * np.log((1 + r) / (1 - r))

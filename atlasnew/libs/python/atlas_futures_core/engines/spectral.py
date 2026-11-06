"""Spectral Engine — frequency-domain properties via FFT."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.signal import hilbert
from atlas_core.engines.rolling import as_series


def _psd(x: np.ndarray) -> np.ndarray:
    """One-sided power spectral density (Hann-windowed periodogram)."""
    n = len(x)
    win = np.hanning(n)
    xw = (x - np.mean(x)) * win
    F = np.fft.rfft(xw)
    p = (np.abs(F) ** 2) / (np.sum(win ** 2) + 1e-12)
    return p


def dominant_frequency(x, w: int) -> pd.Series:
    """Bin index (∈ [0, w/2]) of the peak power. Higher = faster oscillation."""
    s = as_series(x)
    def _f(a):
        p = _psd(a)
        if len(p) < 2:
            return np.nan
        return float(np.argmax(p[1:]) + 1) / len(p)  # normalized ∈ (0,1]
    return s.rolling(w, min_periods=w).apply(_f, raw=True)


def spectral_centroid(x, w: int) -> pd.Series:
    """Center of mass of the PSD (normalized frequency ∈ [0,1])."""
    s = as_series(x)
    def _c(a):
        p = _psd(a)
        if p.sum() == 0:
            return np.nan
        f = np.arange(len(p)) / max(len(p) - 1, 1)
        return float(np.sum(f * p) / p.sum())
    return s.rolling(w, min_periods=w).apply(_c, raw=True)


def spectral_entropy(x, w: int) -> pd.Series:
    """Shannon entropy of the normalized PSD ∈ [0,1] (log2 basis)."""
    s = as_series(x)
    def _e(a):
        p = _psd(a)
        ps = p.sum()
        if ps == 0:
            return np.nan
        q = p / ps
        q = q[q > 0]
        H = -np.sum(q * np.log2(q))
        return float(H / np.log2(len(q)) if len(q) > 1 else 0.0)
    return s.rolling(w, min_periods=w).apply(_e, raw=True)


def spectral_flatness(x, w: int) -> pd.Series:
    """Geometric mean / arithmetic mean of the PSD ∈ [0,1]. 1 = white noise."""
    s = as_series(x)
    def _f(a):
        p = _psd(a) + 1e-12
        return float(np.exp(np.mean(np.log(p))) / np.mean(p))
    return s.rolling(w, min_periods=w).apply(_f, raw=True)


def spectral_rolloff(x, w: int, pct: float = 0.85) -> pd.Series:
    """Frequency (normalized) below which `pct` of spectral energy lies."""
    s = as_series(x)
    def _r(a):
        p = _psd(a)
        if p.sum() == 0:
            return np.nan
        c = np.cumsum(p) / p.sum()
        idx = int(np.argmax(c >= pct))
        return float(idx / max(len(p) - 1, 1))
    return s.rolling(w, min_periods=w).apply(_r, raw=True)


def band_power_ratio(x, w: int, low_end: float = 0.25) -> pd.Series:
    """Low-frequency power fraction. `low_end` splits normalized band [0,1]."""
    s = as_series(x)
    def _b(a):
        p = _psd(a)
        if p.sum() == 0:
            return np.nan
        cut = max(1, int(low_end * len(p)))
        return float(p[:cut].sum() / p.sum())
    return s.rolling(w, min_periods=w).apply(_b, raw=True)


def hilbert_phase(x, w: int) -> pd.Series:
    """Instantaneous phase of the analytic signal ∈ [-π, +π]."""
    s = as_series(x)
    def _h(a):
        # We need at least a few points to compute a meaningful Hilbert transform
        if len(a) < 4:
            return np.nan
        # Demean
        a = a - np.mean(a)
        # Compute analytic signal
        z = hilbert(a)
        # Instantaneous phase of the LAST point
        return float(np.angle(z[-1]))
    return s.rolling(w, min_periods=w).apply(_h, raw=True)


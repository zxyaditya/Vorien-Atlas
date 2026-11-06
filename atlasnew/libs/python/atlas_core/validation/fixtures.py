"""Atlas Validation Framework — Canonical input fixtures.

Deterministic (fixed random seed) OHLCV DataFrames used by every gate.
All fixtures share the same DateTimeIndex length so cross-fixture
similarity tests are meaningful.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

_SEED = 20260706
_N = 500
_START = "2023-01-02"


def _index(n: int = _N) -> pd.DatetimeIndex:
    return pd.bdate_range(_START, periods=n, freq="B")


def _ohlc_from_close(close: np.ndarray) -> pd.DataFrame:
    idx = _index(len(close))
    # Deterministic pseudo-OHLC around close.
    rng = np.random.default_rng(_SEED + 1)
    noise_hi = rng.uniform(0.0, 0.003, size=len(close))
    noise_lo = rng.uniform(0.0, 0.003, size=len(close))
    open_ = np.roll(close, 1); open_[0] = close[0]
    high = np.maximum(close, open_) * (1 + noise_hi)
    low  = np.minimum(close, open_) * (1 - noise_lo)
    volume = (rng.uniform(1e5, 2e5, size=len(close))).astype(float)
    df = pd.DataFrame({"open": open_, "high": high, "low": low,
                       "close": close, "volume": volume}, index=idx)
    return df


def brownian(mu: float = 0.0, sigma: float = 0.02, s0: float = 100.0,
             n: int = _N, seed_offset: int = 0) -> pd.DataFrame:
    """Geometric Brownian motion — the reference stochastic input."""
    rng = np.random.default_rng(_SEED + seed_offset)
    ret = rng.normal(mu, sigma, size=n)
    close = s0 * np.exp(np.cumsum(ret))
    return _ohlc_from_close(close)


def trending(drift: float = 0.001, sigma: float = 0.015, s0: float = 100.0,
             n: int = _N) -> pd.DataFrame:
    """Positive-drift Brownian — for monotonicity + directional gates."""
    return brownian(mu=drift, sigma=sigma, s0=s0, n=n, seed_offset=100)


def mean_reverting(kappa: float = 0.05, mu_price: float = 100.0,
                    sigma: float = 0.02, n: int = _N) -> pd.DataFrame:
    """AR(1)-style mean-reverting price series."""
    rng = np.random.default_rng(_SEED + 200)
    close = np.empty(n); close[0] = mu_price
    for t in range(1, n):
        close[t] = close[t-1] + kappa * (mu_price - close[t-1]) + \
                    sigma * mu_price * rng.normal()
    return _ohlc_from_close(close)


def constant(price: float = 100.0, n: int = _N) -> pd.DataFrame:
    """All-equal input — degenerate-input tests."""
    close = np.full(n, price)
    return _ohlc_from_close(close)


def nan_infested(fraction: float = 0.05, n: int = _N) -> pd.DataFrame:
    """Brownian with a fraction of NaN-injected closes."""
    df = brownian(n=n, seed_offset=300).copy()
    rng = np.random.default_rng(_SEED + 300)
    mask = rng.uniform(size=n) < fraction
    df.loc[df.index[mask], "close"] = np.nan
    return df


def two_pairs() -> tuple:
    """Two independent Brownians aligned on the same DateTimeIndex.

    Suitable for multi-symbol context tests (peer / future basket).
    Returned as (target_df, peer_df).
    """
    a = brownian(seed_offset=10)
    b = brownian(seed_offset=20)
    return a, b


# Canonical fixture registry — used by the runner.
CANONICAL_FIXTURES: dict = {
    "brownian": brownian,
    "trending": trending,
    "mean_reverting": mean_reverting,
    "constant": constant,
    "nan_infested": nan_infested,
}

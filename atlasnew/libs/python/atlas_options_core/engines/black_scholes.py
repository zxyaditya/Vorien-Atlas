"""Black-Scholes Pricing Engine.

Full analytical pricing, implied volatility inversion via Newton-Raphson,
and the complete first-order Greeks chain.

All functions are pure math — no I/O, no state, no interpretation.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from typing import Union


# ─────────────────────────────────────────────────────────────────────
# Normal distribution helpers
# ─────────────────────────────────────────────────────────────────────
def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """d1 parameter of the Black-Scholes formula."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))


def _d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """d2 = d1 - sigma * sqrt(T)."""
    return _d1(S, K, T, r, sigma) - sigma * math.sqrt(T)


def _N(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _n(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x ** 2) / math.sqrt(2.0 * math.pi)


# ─────────────────────────────────────────────────────────────────────
# Option Price
# ─────────────────────────────────────────────────────────────────────
def bs_price(S: float, K: float, T: float, r: float, sigma: float,
             option_type: str = "call") -> float:
    """Black-Scholes theoretical option price.

    Args:
        S: Spot price of underlying.
        K: Strike price.
        T: Time to expiration in years.
        r: Risk-free interest rate (annualised, continuously compounded).
        sigma: Implied volatility (annualised).
        option_type: "call" or "put".

    Returns:
        Theoretical option price (float).
    """
    if T <= 0:
        # At expiry: intrinsic value only
        if option_type == "call":
            return max(0.0, S - K)
        return max(0.0, K - S)

    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    disc = math.exp(-r * T)

    if option_type == "call":
        return S * _N(d1) - K * disc * _N(d2)
    elif option_type == "put":
        return K * disc * _N(-d2) - S * _N(-d1)
    raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")


# ─────────────────────────────────────────────────────────────────────
# Implied Volatility (Newton-Raphson)
# ─────────────────────────────────────────────────────────────────────
def bs_iv(market_price: float, S: float, K: float, T: float, r: float,
          option_type: str = "call", max_iter: int = 200,
          tol: float = 1e-7) -> float:
    """Invert BS formula to find Implied Volatility via Newton-Raphson.

    Returns NaN if convergence fails (e.g., deeply ITM/OTM options with
    negligible extrinsic value).
    """
    if T <= 0 or market_price <= 0:
        return float("nan")

    # Initial guess: simple approximation
    sigma = math.sqrt(2 * abs(math.log(S / K)) / T) if S != K else 0.5

    for _ in range(max_iter):
        price = bs_price(S, K, T, r, sigma, option_type)
        vega = bs_vega(S, K, T, r, sigma)
        diff = price - market_price
        if abs(diff) < tol:
            return sigma
        if abs(vega) < 1e-12:
            return float("nan")
        sigma -= diff / vega
        if sigma <= 0:
            sigma = 1e-6

    return float("nan")


# ─────────────────────────────────────────────────────────────────────
# First-Order Greeks
# ─────────────────────────────────────────────────────────────────────
def bs_delta(S: float, K: float, T: float, r: float, sigma: float,
             option_type: str = "call") -> float:
    """Delta: dPrice/dS — directional exposure to underlying movement."""
    if T <= 0:
        if option_type == "call":
            return 1.0 if S > K else 0.0
        return -1.0 if S < K else 0.0
    d1 = _d1(S, K, T, r, sigma)
    if option_type == "call":
        return _N(d1)
    return _N(d1) - 1.0


def bs_gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Gamma: d²Price/dS² — rate of change of delta.

    Gamma is the same for calls and puts (put-call parity).
    """
    if T <= 0 or S <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    return _n(d1) / (S * sigma * math.sqrt(T))


def bs_theta(S: float, K: float, T: float, r: float, sigma: float,
             option_type: str = "call") -> float:
    """Theta: dPrice/dT — time decay per year.

    Divide by 365 for per-calendar-day decay.
    """
    if T <= 0 or S <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    disc = math.exp(-r * T)
    first = -(S * _n(d1) * sigma) / (2 * math.sqrt(T))
    if option_type == "call":
        second = -r * K * disc * _N(d2)
        return first + second
    second = r * K * disc * _N(-d2)
    return first + second


def bs_vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Vega: dPrice/dSigma — sensitivity to 1-unit change in vol.

    Same for calls and puts.
    """
    if T <= 0 or S <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    return S * _n(d1) * math.sqrt(T)


def bs_rho(S: float, K: float, T: float, r: float, sigma: float,
           option_type: str = "call") -> float:
    """Rho: dPrice/dr — sensitivity to interest rate changes."""
    if T <= 0:
        return 0.0
    d2 = _d2(S, K, T, r, sigma)
    disc = math.exp(-r * T)
    if option_type == "call":
        return K * T * disc * _N(d2)
    return -K * T * disc * _N(-d2)


# ─────────────────────────────────────────────────────────────────────
# Vectorised wrappers for DataFrame-level computation
# ─────────────────────────────────────────────────────────────────────
def compute_greeks_df(df: pd.DataFrame, r: float = 0.0) -> pd.DataFrame:
    """Compute all first-order Greeks for a DataFrame of option rows.

    Expected columns: spot, strike, dte (days), iv, option_type.
    Returns: same DataFrame with added columns delta, gamma, theta, vega, rho.
    """
    out = df.copy()
    T = (out["dte"] / 365.0).clip(lower=1e-6)

    def _apply(fn, *cols, **kw):
        return [fn(row["spot"], row["strike"], row["T"],
                   r, row["iv"], **kw)
                for _, row in out.assign(T=T).iterrows()]

    out["delta"] = [bs_delta(row.spot, row.strike, t, r, row.iv, row.option_type)
                    for (_, row), t in zip(out.iterrows(), T)]
    out["gamma"] = [bs_gamma(row.spot, row.strike, t, r, row.iv)
                    for (_, row), t in zip(out.iterrows(), T)]
    out["theta"] = [bs_theta(row.spot, row.strike, t, r, row.iv, row.option_type) / 365.0
                    for (_, row), t in zip(out.iterrows(), T)]
    out["vega"]  = [bs_vega(row.spot, row.strike, t, r, row.iv)
                    for (_, row), t in zip(out.iterrows(), T)]
    out["rho"]   = [bs_rho(row.spot, row.strike, t, r, row.iv, row.option_type)
                    for (_, row), t in zip(out.iterrows(), T)]
    return out

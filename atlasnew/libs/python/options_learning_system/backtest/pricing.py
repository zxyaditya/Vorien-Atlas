"""Options Mark-to-Market Pricing.

Real-time Black-Scholes pricing for the execution engine to mark portfolio value.
"""
from __future__ import annotations
from typing import Dict, Any
from atlas_options_core.engines.black_scholes import bs_price, bs_delta, bs_gamma, bs_theta, bs_vega
from atlas_options_core.engines.greeks import vanna, charm


def mark_to_market(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> Dict[str, float]:
    """Reprice a single option contract given new spot, time, and IV."""
    if T <= 0:
        # Expired
        if option_type == "call":
            price = max(0.0, S - K)
        else:
            price = max(0.0, K - S)
        return {
            "price": price,
            "delta": 1.0 if (option_type == "call" and S > K) else (-1.0 if (option_type == "put" and S < K) else 0.0),
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "vanna": 0.0,
            "charm": 0.0
        }
    
    price = bs_price(S, K, T, r, sigma, option_type)
    delta = bs_delta(S, K, T, r, sigma, option_type)
    gamma = bs_gamma(S, K, T, r, sigma)
    theta = bs_theta(S, K, T, r, sigma, option_type) / 365.0
    vega = bs_vega(S, K, T, r, sigma)
    
    # Higher order
    _vanna = vanna(S, K, T, r, sigma)
    _charm = charm(S, K, T, r, sigma, option_type)
    
    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "vanna": _vanna,
        "charm": _charm
    }

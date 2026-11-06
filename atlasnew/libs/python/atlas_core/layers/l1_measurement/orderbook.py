"""Orderbook Module — Layer 1.

Implements rigorous microstructure features derived from Level 2 (L2) Orderbook data,
assuming flattened inputs (best_bid, best_ask, best_bid_qty, best_ask_qty, etc).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition

MODULE = "orderbook"

def _reg(id_, name, perspective, family, definition, formula, interp, fn, inputs,
         params=None, complexity="O(1)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs,
        params=params or {}, complexity=complexity, fn=fn
    ))

def _bid_ask_spread(df):
    """Raw spread between top of book."""
    return (df['best_ask'] - df['best_bid']).fillna(0.0)

def _spread_bps(df):
    """Relative spread in basis points."""
    mid = (df['best_bid'] + df['best_ask']) / 2.0
    spread = df['best_ask'] - df['best_bid']
    return ((spread / mid.replace(0, 1e-8)) * 10000.0).fillna(0.0)

def _mid_price(df):
    """Standard midpoint price."""
    return ((df['best_bid'] + df['best_ask']) / 2.0).fillna(0.0)

def _weighted_mid(df):
    """Weighted mid skewed by top-of-book resting liquidity."""
    tot_qty = df['best_bid_qty'] + df['best_ask_qty']
    tot_qty = tot_qty.replace(0, 1e-8)
    w_mid = (df['best_bid'] * df['best_ask_qty'] + df['best_ask'] * df['best_bid_qty']) / tot_qty
    return w_mid.fillna(0.0)

def _microprice(df):
    """Microprice: Volume-weighted average price across the bid-ask spread."""
    tot_qty = df['best_bid_qty'] + df['best_ask_qty']
    tot_qty = tot_qty.replace(0, 1e-8)
    mw = df['best_ask_qty'] / tot_qty
    m_price = df['best_bid'] * mw + df['best_ask'] * (1 - mw)
    return m_price.fillna(0.0)

def _book_imbalance(df):
    """Top-of-Book Imbalance: (Bid Qty - Ask Qty) / Total Qty."""
    tot_qty = df['best_bid_qty'] + df['best_ask_qty']
    imb = (df['best_bid_qty'] - df['best_ask_qty']) / tot_qty.replace(0, 1e-8)
    return imb.fillna(0.0)

def _depth_ratio_5(df):
    """Ratio of bid depth to ask depth at 5 levels."""
    bids = df['bid_depth_5'].fillna(0)
    asks = df['ask_depth_5'].replace(0, 1e-8)
    return (bids / asks).fillna(1.0)

def _depth_ratio_10(df):
    """Ratio of bid depth to ask depth at 10 levels."""
    bids = df['bid_depth_10'].fillna(0)
    asks = df['ask_depth_10'].replace(0, 1e-8)
    return (bids / asks).fillna(1.0)

def _depth_imbalance_gradient(df):
    """Gradient of depth imbalance from L5 to L10."""
    r5 = _depth_ratio_5(df)
    r10 = _depth_ratio_10(df)
    return (r10 - r5).fillna(0.0)

def _cumulative_depth_delta(df):
    """Net cumulative difference between deep bid and deep ask volumes."""
    bids = df['bid_depth_10'].fillna(0)
    asks = df['ask_depth_10'].fillna(0)
    return (bids - asks).fillna(0.0)

# ══════════════════════════════════════════════════════════════════════
# FEATURE REGISTRATIONS
# ══════════════════════════════════════════════════════════════════════

# Spread & Midpoint Mechanics
_inputs_l1 = ["best_bid", "best_ask", "best_bid_qty", "best_ask_qty"]

_reg("orderbook.spread.raw", "Bid-Ask Spread (Raw)", "Magnitude",
     "liquidity", "Absolute distance between the highest buyer and lowest seller.", "Ask - Bid",
     "High values = Slippage risk. Low values = Tight, liquid market.", _bid_ask_spread, _inputs_l1)

_reg("orderbook.spread.bps", "Bid-Ask Spread (BPS)", "Relative",
     "liquidity", "The true cost of market-order execution in Basis Points.", "(Spread / Mid) * 10000",
     "Standardized liquidity cost. If this spikes, market makers are pulling liquidity.", _spread_bps, _inputs_l1)

_reg("orderbook.mid.raw", "Mid Price (Standard)", "Position",
     "price", "Simple midpoint of the L1 spread.", "(Bid + Ask) / 2",
     "Baseline fair price before factoring in volume weight.", _mid_price, _inputs_l1)

_reg("orderbook.mid.weighted", "Resting Liquidity Mid Price", "Position",
     "price", "Fair price that pushes away from heavy resting institutional limit orders.", "(Bid*AskQ + Ask*BidQ) / (BidQ+AskQ)",
     "Price tends to drift towards the side with less resistance.", _weighted_mid, _inputs_l1)

_reg("orderbook.mid.microprice", "L1 Microprice", "Position",
     "price", "Volume-weighted average price across the Bid-Ask spread.", "Bid*W + Ask*(1-W)",
     "Extremely responsive short-term fair value estimate used by HFT bots.", _microprice, _inputs_l1)

_reg("orderbook.imbalance.l1", "Top-of-Book Imbalance (L1)", "Relative",
     "flow", "Calculates immediate buying vs selling intent at the front of the line.", "(BidQ - AskQ) / (BidQ + AskQ)",
     "Values > 0 = Buyers dominating L1. Values < 0 = Sellers dominating.", _book_imbalance, _inputs_l1)


# Depth Mechanics
_inputs_l5 = ["bid_depth_5", "ask_depth_5"]
_inputs_l10 = ["bid_depth_10", "ask_depth_10", "bid_depth_5", "ask_depth_5"]

_reg("orderbook.depth.ratio_5", "Depth Support Ratio (L5)", "Relative",
     "liquidity", "Compares buying support vs selling pressure across the top 5 price levels.", "BidD5 / AskD5",
     "Values > 1 indicate hidden buying support. Values < 1 indicate heavy selling overhead.", _depth_ratio_5, _inputs_l5)

_reg("orderbook.depth.ratio_10", "Depth Support Ratio (L10)", "Relative",
     "liquidity", "Compares deeper structural buying support vs selling pressure (10 levels).", "BidD10 / AskD10",
     "Identifies medium-term structural support or resistance walls.", _depth_ratio_10, _inputs_l10)

_reg("orderbook.depth.gradient", "Liquidity Spoofing Gradient", "Motion",
     "flow", "The delta between L10 and L5 depth ratios.", "Ratio10 - Ratio5",
     "High values indicate institutions are layering fake liquidity deep in the book to manipulate price.", _depth_imbalance_gradient, _inputs_l10)

_reg("orderbook.depth.cumulative_delta", "Net Liquidity Overhang (L10)", "Magnitude",
     "flow", "The total raw difference between L10 buyers and sellers.", "BidD10 - AskD10",
     "Positive values = massive net buying wall. Negative = massive net selling wall.", _cumulative_depth_delta, _inputs_l10)

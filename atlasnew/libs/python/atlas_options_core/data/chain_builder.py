"""Options Chain Builder.

Converts raw Deribit trade/OHLCV data into structured OptionsChain objects.
These are the fundamental data structures consumed by the feature pipeline.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from atlas_options_core.engines.black_scholes import bs_iv, bs_delta, bs_gamma, bs_theta, bs_vega


# ─────────────────────────────────────────────────────────────────────
# Core Data Contracts
# ─────────────────────────────────────────────────────────────────────

@dataclass
class OptionsContract:
    """A single option contract at a point in time."""
    instrument_name: str
    underlying: str          # "ETH" or "BTC"
    option_type: str         # "call" or "put"
    strike: float
    expiry: str              # "2026-06-30"
    dte: int                 # days to expiration
    spot: float              # underlying price at this snapshot
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0
    volume: float = 0.0
    open_interest: float = 0.0

    # Computed fields (filled by build_contract)
    mid: float = 0.0
    iv: float = 0.0
    moneyness: float = 1.0   # spot / strike
    intrinsic: float = 0.0
    extrinsic: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0       # per calendar day
    vega: float = 0.0

    @property
    def is_call(self) -> bool:
        return self.option_type == "call"

    @property
    def is_otm(self) -> bool:
        if self.is_call:
            return self.spot < self.strike
        return self.spot > self.strike

    @property
    def spread_pct(self) -> float:
        mid = (self.bid + self.ask) / 2.0
        if mid > 0:
            return (self.ask - self.bid) / mid
        return 0.0


@dataclass
class OptionsChain:
    """A full cross-section of options at one timestamp."""
    timestamp: str
    underlying: str
    spot: float
    contracts: List[OptionsContract] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        if not self.contracts:
            return pd.DataFrame()
        rows = []
        for c in self.contracts:
            rows.append({
                "instrument_name": c.instrument_name,
                "option_type": c.option_type,
                "strike": c.strike,
                "expiry": c.expiry,
                "dte": c.dte,
                "spot": c.spot,
                "bid": c.bid,
                "ask": c.ask,
                "mid": c.mid,
                "last_price": c.last_price,
                "volume": c.volume,
                "open_interest": c.open_interest,
                "iv": c.iv,
                "moneyness": c.moneyness,
                "intrinsic": c.intrinsic,
                "extrinsic": c.extrinsic,
                "delta": c.delta,
                "gamma": c.gamma,
                "theta": c.theta,
                "vega": c.vega,
            })
        return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────
# Builders
# ─────────────────────────────────────────────────────────────────────

def build_contract(row: pd.Series, spot: float, r: float = 0.0) -> OptionsContract:
    """Build an OptionsContract from a raw Deribit instrument row + spot price."""
    dte = max(0, int(row.get("dte", row.get("days_to_expiry", 0))))
    T = max(dte / 365.0, 1e-6)

    bid = float(row.get("bid", row.get("best_bid_price", 0.0)) or 0.0)
    ask = float(row.get("ask", row.get("best_ask_price", 0.0)) or 0.0)
    last = float(row.get("last_price", row.get("last", 0.0)) or 0.0)
    vol = float(row.get("volume", 0.0) or 0.0)
    oi = float(row.get("open_interest", 0.0) or 0.0)
    strike = float(row.get("strike", 0.0) or 0.0)
    option_type = str(row.get("option_type", "call")).lower()
    mid = (bid + ask) / 2.0 if (bid > 0 or ask > 0) else last

    # Implied Volatility
    price_for_iv = mid if mid > 0 else last
    if price_for_iv > 0 and spot > 0 and strike > 0 and dte > 0:
        iv = bs_iv(price_for_iv, spot, strike, T, r, option_type)
    else:
        iv = float(row.get("mark_iv", row.get("iv", 0.0)) or 0.0) / 100.0

    if math.isnan(iv) or iv <= 0:
        iv = 0.0

    # Greeks
    delta = bs_delta(spot, strike, T, r, iv, option_type) if iv > 0 else 0.0
    gamma = bs_gamma(spot, strike, T, r, iv) if iv > 0 else 0.0
    theta = bs_theta(spot, strike, T, r, iv, option_type) / 365.0 if iv > 0 else 0.0
    vega = bs_vega(spot, strike, T, r, iv) if iv > 0 else 0.0

    # Intrinsic / Extrinsic
    if option_type == "call":
        intrinsic = max(0.0, spot - strike)
    else:
        intrinsic = max(0.0, strike - spot)
    extrinsic = max(0.0, mid - intrinsic)

    return OptionsContract(
        instrument_name=str(row.get("instrument_name", "")),
        underlying=str(row.get("currency", "ETH")),
        option_type=option_type,
        strike=strike,
        expiry=str(row.get("expiry", "")),
        dte=dte,
        spot=spot,
        bid=bid,
        ask=ask,
        last_price=last,
        volume=vol,
        open_interest=oi,
        mid=mid,
        iv=iv,
        moneyness=spot / strike if strike > 0 else 1.0,
        intrinsic=intrinsic,
        extrinsic=extrinsic,
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
    )


def build_chain_from_df(instruments_df: pd.DataFrame, spot: float,
                          timestamp: str, r: float = 0.0) -> OptionsChain:
    """Build a full OptionsChain from a DataFrame of instrument rows."""
    contracts = []
    ts_dt = pd.to_datetime(timestamp, utc=True)
    
    for _, row in instruments_df.iterrows():
        try:
            row_copy = row.copy()
            if "expiration_timestamp" in row_copy and pd.notnull(row_copy["expiration_timestamp"]):
                expiry_ts = pd.to_datetime(row_copy["expiration_timestamp"], unit="ms", utc=True)
                row_copy["dte"] = max(1, (expiry_ts - ts_dt).days)
                
            c = build_contract(row_copy, spot, r)
            if c.strike > 0:
                contracts.append(c)
        except Exception:
            continue
    return OptionsChain(timestamp=timestamp, underlying="ETH",
                         spot=spot, contracts=contracts)


def build_chain_timeseries(instruments_df: pd.DataFrame,
                             spot_ohlcv: pd.DataFrame,
                             r: float = 0.0) -> List[OptionsChain]:
    """Build a list of OptionsChain objects — one per bar in spot_ohlcv.

    The instruments_df must have a 'timestamp' column.
    """
    chains = []
    for ts, spot_row in spot_ohlcv.iterrows():
        spot = float(spot_row["close"])
        ts_str = str(ts)
        # Filter instruments active at this timestamp
        if "timestamp" in instruments_df.columns:
            snap = instruments_df[instruments_df["timestamp"] == ts]
        else:
            snap = instruments_df

        if snap.empty:
            continue

        chain = build_chain_from_df(snap, spot, ts_str, r)
        chains.append(chain)

    return chains

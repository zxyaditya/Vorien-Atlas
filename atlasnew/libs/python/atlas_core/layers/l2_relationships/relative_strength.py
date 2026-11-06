"""Relative Strength — Layer 2 (minimum viable).

Book 1 places Relative Strength explicitly in Layer 2. This module is
the MINIMUM needed to support pairwise-vs-peer comparison. A full multi-
peer Cross-Asset framework belongs to Layer 4 and is not built here.

Data contract: peers arrive via df.attrs['_atlas_context'] — the compute
orchestrator attaches this dict when the caller supplies one. If the
context is missing or contains no peer, features return NaN gracefully.
Such soft failure is required because L1/L2 pipelines run over single
symbols without peers by default.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.engines import crossasset as ca
from atlas_core.layers.l2_relationships._l1_bridge import l1_series

MODULE = "relative_strength"


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=2, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["L1:price.magnitude.close", "context:peer_close"],
        params=params or {}, complexity=complexity, fn=fn,
    ))


def _peer_close(df) -> pd.Series:
    """Return the peer close series aligned to df.index, or an empty NaN series."""
    ctx = df.attrs.get("_atlas_context") if hasattr(df, "attrs") else None
    if not ctx:
        return pd.Series(np.nan, index=df.index)
    peer_df = ctx.get("peer")
    if peer_df is None or "close" not in peer_df.columns:
        return pd.Series(np.nan, index=df.index)
    return peer_df["close"].reindex(df.index).astype(float)


def _target_close(df) -> pd.Series:
    return l1_series(df, "price.magnitude.close")


for w in [20, 50, 100]:
    def _rs(df, w_=w):
        return ca.relative_strength(_target_close(df), _peer_close(df), w_)
    _reg(f"relative_strength.magnitude.rs_{w}",
         f"Relative Strength vs Peer ({w})", "Magnitude", "relative_return",
         f"(a_t/a_{{t-{w}}}) / (b_t/b_{{t-{w}}}) — target return divided by peer return.",
         f"R_a({w}) / R_b({w})",
         "Multiplicative outperformance vs peer over the window.",
         (lambda w_: (lambda df: _rs(df, w_)))(w), params={"window": w})

# Log spread — no window parameter, register once
_reg("relative_strength.geometry.log_spread",
     "Log Spread vs Peer", "Geometry", "log_spread",
     "ln(a) - ln(b) — log-price spread.",
     "ln P_a - ln P_b", "Log difference of price levels.",
     lambda df: ca.log_spread(_target_close(df), _peer_close(df)),
     params={})


for w in [20, 50]:
    def _corr(df, w_=w):
        ra = _target_close(df).pct_change(fill_method=None)
        rb = _peer_close(df).pct_change(fill_method=None)
        return ca.rolling_corr(ra, rb, w_)
    _reg(f"relative_strength.statistics.corr_{w}",
         f"Rolling Correlation vs Peer ({w})", "Statistics", "correlation",
         f"Rolling {w}-bar correlation of target and peer returns.",
         f"corr(r_a, r_b, w={w})",
         "Co-movement measurement — a relationship, not a decision.",
         (lambda w_: (lambda df: _corr(df, w_)))(w), params={"window": w})

    def _beta(df, w_=w):
        ra = _target_close(df).pct_change(fill_method=None)
        rb = _peer_close(df).pct_change(fill_method=None)
        return ca.rolling_beta(ra, rb, w_)
    _reg(f"relative_strength.relative.beta_{w}",
         f"Rolling Beta vs Peer ({w})", "Relative", "beta",
         f"cov(r_a, r_b) / var(r_b) over {w} bars.",
         f"β = cov/var",
         "Linear sensitivity of target returns to peer returns.",
         (lambda w_: (lambda df: _beta(df, w_)))(w), params={"window": w})

    def _relvol(df, w_=w):
        ra = _target_close(df).pct_change(fill_method=None)
        rb = _peer_close(df).pct_change(fill_method=None)
        return ca.relative_volatility(ra, rb, w_)
    _reg(f"relative_strength.expansion.relvol_{w}",
         f"Relative Volatility vs Peer ({w})", "Expansion", "vol_ratio",
         f"σ_target / σ_peer over {w} bars.",
         "σ_a / σ_b",
         "Which side is currently more volatile.",
         (lambda w_: (lambda df: _relvol(df, w_)))(w), params={"window": w})


_reg("relative_strength.motion.leadership_50",
     "Leadership (±3-bar argmax |corr|, w=50)", "Motion", "leadership",
     "argmax over lag ∈ {-3..+3} of |corr(target, peer.shift(lag))| in a 50-bar window.",
     "argmax_L |corr(a_t, b_{t-L})|",
     ">0 means target tends to lead peer; <0 means peer leads.",
     lambda df: ca.leadership(_target_close(df), _peer_close(df), 50),
     params={"window": 50, "lags": "±3"})

_reg("relative_strength.entropy.cointegration_resid_std_100",
     "Cointegration Residual Std (w=100)", "Entropy", "cointegration_residual",
     "Rolling std of OLS residual of ln(a) ~ ln(b) over 100 bars.",
     "std(resid(ln a ~ ln b, w=100))",
     "Low value → tight pair; high → divergence.",
     lambda df: ca.cointegration_residual_std(_target_close(df),
                                               _peer_close(df), 100),
     params={"window": 100})

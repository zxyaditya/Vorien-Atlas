"""Momentum of Trend — Layer 2 (Book 1 Ch. 5 example).

Full mathematical specification: /app/docs/L2_SPECS/MOMENTUM_OF_TREND.md

Purpose
-------
Study how an already-measured L1 *trend property* — a slope, a directional
strength, an oscillator — evolves over time.  This is NOT price momentum
(that is L1).  It is the temporal relationship of a trend measurement to
itself: how fast is the trend changing, is that change stable, is the trend
strengthening or weakening, and do multiple trend representations agree on
the direction of that change?

The module consumes L1 through the Registry only (`_l1_bridge.l1_series`),
never re-implements L1 math (Invariant 6.4), and produces exclusively
relationship-form features (Invariant 6.3).

Registered features (32 total, 5 Perspectives)
---------------------------------------------
For each source S in {price.motion.lr_slope_20, price.regime.adx_14,
price.regime.aroon_osc_14} and each derivative window w in {10, 20}:

  motion.<src>_velocity_{w}         : v_w(S)     = (S(t) − S(t−w)) / w
  motion.<src>_acceleration_{w}     : v_w(v_w(S))
  statistics.<src>_velocity_std_{w} : rolling std of v_w(S) over w
  regime.<src>_direction_persistence_{w} : consecutive bars sign(v_w) unchanged, cap w
  position.<src>_velocity_abs_rank_{w} : percentile rank of |v_w| over w

Plus two Relative-perspective cross-source alignment features at w=20.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l2_relationships._l1_bridge import l1_series

MODULE = "momentum_of_trend"

# Sources: three orthogonal L1 trend measurements.
SOURCES = [
    # short_id           registered_id                     human name
    ("lr_slope_20",      "price.motion.lr_slope_20",       "LR slope(20)"),
    ("adx_14",           "price.regime.adx_14",            "ADX(14)"),
    ("aroon_osc_14",     "price.regime.aroon_osc_14",      "Aroon Osc(14)"),
]
WINDOWS = [10, 20]


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         inputs, params=None, complexity="O(n)"):
    """Book-1-compliant registration helper.  `inputs` lists the exact L1
    feature IDs consumed — no wildcards.  This preserves Registry
    traceability required by Invariants 6.4 and 6.7."""
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=2, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=params or {}, complexity=complexity, fn=fn,
    ))


# ── Core derivative kernels ────────────────────────────────────────────────

def _velocity(s: pd.Series, w: int) -> pd.Series:
    """v_w(t) = (S(t) − S(t−w)) / w — first difference over w bars,
    normalised by window length so units are S/bar."""
    return (s - s.shift(w)) / float(w)


def _direction_persistence(v: pd.Series, w: int) -> pd.Series:
    """Consecutive-bar count of bars whose velocity sign matches the
    velocity sign at t, capped at w.  Ignores zero-sign runs (treated as
    breaks) so persistence measures 'directed' motion only."""
    sign = np.sign(v.fillna(0.0)).astype(int)
    n = len(sign)
    out = np.zeros(n, dtype=float)
    run = 0
    last = 0
    for i in range(n):
        cur = int(sign.iloc[i])
        if cur == 0:
            run = 0
        elif cur == last:
            run += 1
        else:
            run = 1
        last = cur
        out[i] = min(run, w)
    return pd.Series(out, index=v.index)


def _rank_abs(v: pd.Series, w: int) -> pd.Series:
    """Rolling percentile rank of |v| over w bars."""
    return v.abs().rolling(w, min_periods=max(2, w // 2)).rank(pct=True)


# ── Per-source features (motion / statistics / regime / position) ──────────

def _make_velocity_fn(fid, w):
    return lambda df: _velocity(l1_series(df, fid), w)


def _make_accel_fn(fid, w):
    def _fn(df):
        v = _velocity(l1_series(df, fid), w)
        return _velocity(v, w)
    return _fn


def _make_vel_std_fn(fid, w):
    def _fn(df):
        v = _velocity(l1_series(df, fid), w)
        return v.rolling(w, min_periods=max(2, w // 2)).std()
    return _fn


def _make_persistence_fn(fid, w):
    def _fn(df):
        v = _velocity(l1_series(df, fid), w)
        return _direction_persistence(v, w)
    return _fn


def _make_abs_rank_fn(fid, w):
    def _fn(df):
        v = _velocity(l1_series(df, fid), w)
        return _rank_abs(v, w)
    return _fn


for short, fid, human in SOURCES:
    for w in WINDOWS:
        _reg(
            f"{MODULE}.motion.{short}_velocity_{w}",
            f"Velocity of {human} — {w}",
            "Motion", "velocity_of_trend",
            f"First difference of {human} over {w} bars, normalised by window.",
            f"(T(t) − T(t−{w})) / {w}, T={fid}",
            "Positive = trend property is strengthening; negative = weakening.",
            _make_velocity_fn(fid, w),
            inputs=[f"L1:{fid}"], params={"source": fid, "window": w},
        )
        _reg(
            f"{MODULE}.motion.{short}_acceleration_{w}",
            f"Acceleration of {human} — {w}",
            "Motion", "acceleration_of_trend",
            f"Velocity of the velocity of {human} at window {w}.",
            f"v_{w}(v_{w}(T)), T={fid}",
            "Positive = velocity of trend is itself accelerating.",
            _make_accel_fn(fid, w),
            inputs=[f"L1:{fid}"], params={"source": fid, "window": w},
        )
        _reg(
            f"{MODULE}.statistics.{short}_velocity_std_{w}",
            f"σ of {human} Velocity — {w}",
            "Statistics", "velocity_stability",
            f"Rolling standard deviation of the {w}-bar velocity of {human}.",
            f"std_{{k={w}}}(v_{w}(T)), T={fid}",
            "High = trend evolves noisily; low = trend evolves smoothly.",
            _make_vel_std_fn(fid, w),
            inputs=[f"L1:{fid}"], params={"source": fid, "window": w},
        )
        _reg(
            f"{MODULE}.regime.{short}_direction_persistence_{w}",
            f"Direction Persistence of {human} — {w}",
            "Regime", "direction_persistence",
            f"Consecutive bars whose sign(v_{w}({human})) matches the current bar, capped at {w}.",
            f"cap(runlen(sign(v_{w}(T))), {w}), T={fid}",
            "High = trend has been strengthening (or weakening) uninterruptedly.",
            _make_persistence_fn(fid, w),
            inputs=[f"L1:{fid}"], params={"source": fid, "window": w},
        )
        _reg(
            f"{MODULE}.position.{short}_velocity_abs_rank_{w}",
            f"|Velocity| Percentile Rank of {human} — {w}",
            "Position", "velocity_rank",
            f"Percentile rank of |v_{w}({human})| over the last {w} bars.",
            f"rank_pct(|v_{w}(T)|, {w}), T={fid}",
            "How unusually fast is the trend evolving right now, in its own units.",
            _make_abs_rank_fn(fid, w),
            inputs=[f"L1:{fid}"], params={"source": fid, "window": w},
        )


# ── Relative-perspective: cross-source velocity agreement (w=20) ──────────

_AGREEMENT_W = 20


def _velocity_sign_agreement(df) -> pd.Series:
    """Fraction of sources whose sign(v_20) matches the modal sign, per bar.
    Returns a value in [0, 1] (1 = perfect agreement across sources)."""
    sers = []
    for _, fid, _ in SOURCES:
        v = _velocity(l1_series(df, fid), _AGREEMENT_W)
        sers.append(np.sign(v.fillna(0.0)))
    if not sers:
        return pd.Series(index=df.index, dtype=float)
    S = pd.concat(sers, axis=1)                                    # (n, 3)
    # Mode-sign per row (majority; ties → 0). Compute mean then round to
    # {-1, 0, +1}; then measure agreement.
    modal = S.apply(lambda r: (1 if (r > 0).sum() > (r < 0).sum()
                               else (-1 if (r < 0).sum() > (r > 0).sum() else 0)),
                    axis=1)
    match = S.eq(modal, axis=0).sum(axis=1) / max(1, S.shape[1])
    return match


def _velocity_agreement_slope_adx(df) -> pd.Series:
    """Pairwise sign agreement between slope_20 velocity and ADX_14 velocity
    at w=20.  Output ∈ {-1, 0, +1}.  +1 = both trend representations agree
    the trend is strengthening (or both weakening); -1 = disagreement."""
    v1 = _velocity(l1_series(df, "price.motion.lr_slope_20"), _AGREEMENT_W)
    v2 = _velocity(l1_series(df, "price.regime.adx_14"), _AGREEMENT_W)
    s1 = np.sign(v1.fillna(0.0))
    s2 = np.sign(v2.fillna(0.0))
    prod = s1 * s2
    return prod


_reg(
    f"{MODULE}.relative.velocity_sign_agreement_{_AGREEMENT_W}",
    f"Cross-Source Velocity-Sign Agreement — {_AGREEMENT_W}",
    "Relative", "cross_source_agreement",
    f"Fraction of the three trend sources whose sign(v_{_AGREEMENT_W}) matches the modal sign at bar t.",
    "mean_{S in sources}(1[sign(v(S)) == mode]) ∈ [0, 1]",
    "1 = all three trend representations agree on the direction of trend change; ≤ 0.33 = full disagreement.",
    _velocity_sign_agreement,
    inputs=[f"L1:{fid}" for _, fid, _ in SOURCES],
    params={"window": _AGREEMENT_W, "sources": [fid for _, fid, _ in SOURCES]},
    complexity="O(n·k)",
)

_reg(
    f"{MODULE}.relative.velocity_agreement_slope_adx_{_AGREEMENT_W}",
    f"Slope↔ADX Velocity Agreement — {_AGREEMENT_W}",
    "Relative", "pairwise_agreement",
    f"sign(v_{_AGREEMENT_W}(lr_slope_20)) × sign(v_{_AGREEMENT_W}(ADX_14)).",
    "sign(v(slope_20)) · sign(v(ADX_14)) ∈ {-1, 0, +1}",
    "+1 = both agree trend is strengthening (or both weakening); -1 = they disagree.",
    _velocity_agreement_slope_adx,
    inputs=["L1:price.motion.lr_slope_20", "L1:price.regime.adx_14"],
    params={"window": _AGREEMENT_W},
)

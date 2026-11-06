"""Trend State — Layer 3 (Market Understanding).

Book 1 Ch. 5 exemplar family: trend_continuation / trend_exhaustion /
trend_reversal. See docs/L3_MARKET_UNDERSTANDING.md §6.1 for the
mathematical composition.

All inputs are drawn via the L3 layer bridge (DEC-014). No direct OHLCV
access. No engine or module below L2 is touched directly.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l3_market_understanding._layer_bridge import l1_series, l2_series
from atlas_core.layers.l3_market_understanding._state_kernel import (
    weighted_score, hysteresis_flag, duration, transition,
    agreement_confidence, winner_take_all,
)

MODULE = "trend_state"

# Priority order for winner-take-all ties (Book 1 Ch. 5: continuation
# is the "least surprising" state, followed by exhaustion, then reversal).
STATES = ("trend_continuation", "trend_exhaustion", "trend_reversal")
HYST_ON, HYST_OFF = 0.60, 0.40


def _reg(id_, name, perspective, family, definition, formula, interp,
         fn, inputs, params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=3, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=params or {}, complexity=complexity, fn=fn,
    ))


# ── Evidence composition (single pass; heavy work cached by layer_bridge) ──
def _evidence(df: pd.DataFrame):
    consensus = l2_series(df, "trend_relationships.regime.directional_consensus_score_20")
    cascade   = l2_series(df, "trend_relationships.geometry.ema_cascade_score_10_20_50_100")
    vel_slope = l2_series(df, "momentum_of_trend.motion.lr_slope_20_velocity_20")
    vel_adx   = l2_series(df, "momentum_of_trend.motion.adx_14_velocity_20")
    hurst     = l1_series(df, "price.geometry.hurst_64")
    dc_sign   = l2_series(df, "trend_relationships.regime.directional_consensus_sign_20")
    return {
        "consensus": consensus, "cascade": cascade,
        "vel_slope": vel_slope, "vel_adx": vel_adx,
        "hurst": hurst, "dc_sign": dc_sign,
    }


def _scores(df: pd.DataFrame):
    ev = _evidence(df)
    # Continuation: high consensus + accelerating + persistent Hurst.
    cont = weighted_score({
        "consensus": ev["consensus"].abs(),
        "cascade": ev["cascade"].abs(),
        "vel_slope": ev["vel_slope"].abs() * np.sign(ev["vel_slope"] * ev["dc_sign"]).clip(0, 1),
        "hurst": (ev["hurst"] - 0.5).clip(0.0, 0.5) * 2.0,
    }, {"consensus": 0.35, "cascade": 0.25, "vel_slope": 0.25, "hurst": 0.15})

    # Exhaustion: high consensus BUT decelerating and Hurst reverting.
    dec = (-ev["vel_slope"] * ev["dc_sign"]).clip(lower=0.0)
    exh = weighted_score({
        "consensus": ev["consensus"].abs(),
        "decel": dec,
        "hurst_reversion": (0.55 - ev["hurst"]).clip(0.0, 0.2) * 5.0,
    }, {"consensus": 0.4, "decel": 0.4, "hurst_reversion": 0.2})

    # Reversal: consensus sign flipping in a short window.
    dc = ev["dc_sign"]
    flip = (dc * dc.shift(1) < 0).astype(float)
    rev = weighted_score({
        "flip": flip.rolling(3, min_periods=1).sum().clip(0, 1),
        "vel_flip": (ev["vel_slope"] * ev["vel_slope"].shift(1) < 0).astype(float).rolling(3, min_periods=1).sum().clip(0, 1),
    }, {"flip": 0.7, "vel_flip": 0.3})

    return {"trend_continuation": cont, "trend_exhaustion": exh, "trend_reversal": rev}, ev


def _wta(df: pd.DataFrame):
    scores, ev = _scores(df)
    wta = winner_take_all(scores, priority=STATES)
    return scores, wta, ev


# ─── SCORES (Position) ───
for state in STATES:
    def _score_fn(df, s=state):
        return _scores(df)[0][s]
    _reg(f"{MODULE}.position.{state}_score",
         f"Trend state · {state.replace('_', ' ')} score",
         "Position", "score",
         f"Continuous strength of the {state} state at bar t (weighted "
         f"aggregation of L2 evidence, mapped to [0, 1]).",
         "weighted_score(evidence, weights)",
         f"{state.replace('_', ' ').capitalize()} strength in [0, 1].",
         _score_fn,
         inputs=["L2:trend_relationships.*", "L2:momentum_of_trend.*",
                 "L1:price.geometry.hurst_64"],
         params={"state": state})

# ─── FLAGS (Regime) ───
for state in STATES:
    def _flag_fn(df, s=state):
        scores, wta, _ = _wta(df)
        return wta[f"{s}_flag"]
    _reg(f"{MODULE}.regime.{state}_flag",
         f"Trend state · {state.replace('_', ' ')} flag",
         "Regime", "flag",
         f"Winner-take-all flag for the {state} state (0/1); mutually "
         f"exclusive with the other states in this family.",
         "winner_take_all(scores, priority)",
         f"1 when {state} is the active trend state; 0 otherwise.",
         _flag_fn,
         inputs=["L3:trend_state.position.*"],
         params={"state": state, "priority": list(STATES)})

# ─── DURATION (Motion) ───
for state in STATES:
    def _dur_fn(df, s=state):
        return duration(_wta(df)[1][f"{s}_flag"])
    _reg(f"{MODULE}.motion.{state}_duration",
         f"Trend state · {state.replace('_', ' ')} duration",
         "Motion", "duration",
         f"Consecutive bars the {state} flag has been on.",
         "duration(flag)",
         f"How long the market has remained in the {state} state.",
         _dur_fn,
         inputs=[f"L3:{MODULE}.regime.{state}_flag"],
         params={"state": state})

# ─── TRANSITION (Motion) ───
for state in STATES:
    def _trn_fn(df, s=state):
        return transition(_wta(df)[1][f"{s}_flag"])
    _reg(f"{MODULE}.motion.{state}_transition",
         f"Trend state · {state.replace('_', ' ')} transition",
         "Motion", "transition",
         f"+1 on entry bar; -1 on exit bar; 0 otherwise for {state}.",
         "transition(flag)",
         f"Marks the bar where the {state} state entered or exited.",
         _trn_fn,
         inputs=[f"L3:{MODULE}.regime.{state}_flag"],
         params={"state": state})

# ─── CONFIDENCE (Statistics) ───
for state in STATES:
    def _conf_fn(df, s=state):
        scores, wta, ev = _wta(df)
        # Confidence: agreement of the state's evidence signs, gated by score being > 0.
        if s == "trend_continuation":
            signs = [ev["dc_sign"], np.sign(ev["vel_slope"] * ev["dc_sign"]).astype(float), np.sign(ev["hurst"] - 0.5)]
        elif s == "trend_exhaustion":
            signs = [ev["dc_sign"], -np.sign(ev["vel_slope"] * ev["dc_sign"]).astype(float)]
        else:  # trend_reversal
            signs = [np.sign(ev["dc_sign"] - ev["dc_sign"].shift(1)).astype(float)]
        signs = [pd.Series(x, index=ev["consensus"].index).replace([np.inf, -np.inf], np.nan)
                 for x in signs]
        agree = agreement_confidence(signs)
        return (scores[s] * agree).clip(0.0, 1.0)
    _reg(f"{MODULE}.statistics.{state}_confidence",
         f"Trend state · {state.replace('_', ' ')} confidence",
         "Statistics", "confidence",
         f"Agreement-adjusted confidence in the {state} classification.",
         "score * |mean(sign(evidence))|",
         f"How confident the framework is that {state} is truly active.",
         _conf_fn,
         inputs=[f"L3:{MODULE}.position.{state}_score"],
         params={"state": state})

# ─── MODULE-LEVEL ACTIVE STATE (Regime + Statistics) ───
def _active_code_fn(df):
    return _wta(df)[1]["active_code"]
_reg(f"{MODULE}.regime.active_state_code",
     "Trend state · active state code",
     "Regime", "active_state",
     "Integer code identifying the winning trend state at bar t: "
     "0=none, 1=trend_continuation, 2=trend_exhaustion, 3=trend_reversal.",
     "winner_take_all(scores, priority).active_code",
     "The single trend state that best describes the current bar.",
     _active_code_fn,
     inputs=[f"L3:{MODULE}.position.*"],
     params={"codes": {"0": "none", "1": "trend_continuation",
                        "2": "trend_exhaustion", "3": "trend_reversal"}})


def _active_conf_fn(df):
    scores, wta, _ = _wta(df)
    code = wta["active_code"].values.astype(int)
    # Confidence of the winning state at each bar.
    conf_series = {i + 1: scores[STATES[i]] for i in range(len(STATES))}
    out = np.zeros(len(code), dtype=float)
    for i, c in enumerate(code):
        if c == 0:
            out[i] = 0.0
        else:
            v = conf_series[c].iloc[i] if hasattr(conf_series[c], "iloc") else conf_series[c][i]
            out[i] = float(v) if np.isfinite(v) else 0.0
    return pd.Series(np.clip(out, 0.0, 1.0), index=wta["active_code"].index)
_reg(f"{MODULE}.statistics.active_state_confidence",
     "Trend state · active state confidence",
     "Statistics", "active_state",
     "Score of the currently active trend state; 0.0 when no state is active.",
     "score_of(active_code)",
     "How confidently the winning trend state is held.",
     _active_conf_fn,
     inputs=[f"L3:{MODULE}.regime.active_state_code",
             f"L3:{MODULE}.position.*"])

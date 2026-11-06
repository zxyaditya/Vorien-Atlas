"""Range State — Layer 3 (Market Understanding).

Book 1 Ch. 5 exemplar family: range_formation / breakout_environment /
range_expansion. Direction-neutral by design.

See docs/L3_MARKET_UNDERSTANDING.md §6.2.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l3_market_understanding._layer_bridge import l1_series, l2_series
from atlas_core.layers.l3_market_understanding._state_kernel import (
    weighted_score, duration, transition, winner_take_all,
)

MODULE = "range_state"
STATES = ("range_formation", "breakout_environment", "range_expansion")


def _reg(id_, name, perspective, family, definition, formula, interp,
         fn, inputs, params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=3, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=params or {}, complexity=complexity, fn=fn,
    ))


def _evidence(df: pd.DataFrame):
    vol_ratio  = l2_series(df, "compression_expansion.expansion.vol_ratio_10_50")
    squeeze    = l2_series(df, "compression_expansion.regime.squeeze_flag")
    straight   = l1_series(df, "price.geometry.straightness_50")
    choppy     = l1_series(df, "price.regime.choppiness_14")
    structure  = l2_series(df, "market_structure.regime.structure_regime_k5")
    bos        = l2_series(df, "market_structure.motion.bos_k5")
    return {"vol_ratio": vol_ratio, "squeeze": squeeze,
            "straight": straight, "choppy": choppy,
            "structure": structure, "bos": bos}


def _scores(df: pd.DataFrame):
    ev = _evidence(df)
    # Range formation: low expansion, low straightness, high choppiness, zero structure.
    formation = weighted_score({
        "low_expansion": (1.0 / (1.0 + ev["vol_ratio"].clip(lower=0.0))),
        "low_straight": (1.0 - ev["straight"].clip(0.0, 1.0)),
        "choppy": (ev["choppy"] / 100.0).clip(0.0, 1.0),
        "no_structure": (ev["structure"] == 0).astype(float),
    }, {"low_expansion": 0.3, "low_straight": 0.25, "choppy": 0.25, "no_structure": 0.2})

    # Breakout environment: squeeze active + recent BOS.
    bos_recent = ev["bos"].abs().rolling(3, min_periods=1).max().clip(0.0, 1.0)
    breakout = weighted_score({
        "squeeze": ev["squeeze"].clip(0.0, 1.0),
        "bos_recent": bos_recent,
        "structure_change": (ev["structure"].abs()).clip(0.0, 1.0),
    }, {"squeeze": 0.4, "bos_recent": 0.4, "structure_change": 0.2})

    # Range expansion: expansion ratio > 1 with still-low straightness.
    expansion = weighted_score({
        "expansion": (ev["vol_ratio"] - 1.0).clip(lower=0.0),
        "still_choppy": (ev["choppy"] / 100.0).clip(0.0, 1.0),
        "low_straight": (1.0 - ev["straight"].clip(0.0, 1.0)),
    }, {"expansion": 0.5, "still_choppy": 0.25, "low_straight": 0.25})

    return {"range_formation": formation,
            "breakout_environment": breakout,
            "range_expansion": expansion}, ev


def _wta(df: pd.DataFrame):
    scores, ev = _scores(df)
    wta = winner_take_all(scores, priority=STATES)
    return scores, wta, ev


# Uniform registrations across the 5 shapes.
for state in STATES:
    def _score_fn(df, s=state):
        return _scores(df)[0][s]
    _reg(f"{MODULE}.position.{state}_score",
         f"Range state · {state.replace('_', ' ')} score", "Position", "score",
         f"Continuous strength of the {state} state.",
         "weighted_score(evidence, weights)",
         f"{state.replace('_', ' ').capitalize()} strength in [0, 1].",
         _score_fn,
         inputs=["L2:compression_expansion.*", "L2:market_structure.*",
                 "L1:price.geometry.straightness_50", "L1:price.regime.choppiness_14"],
         params={"state": state})

for state in STATES:
    def _flag_fn(df, s=state):
        return _wta(df)[1][f"{s}_flag"]
    _reg(f"{MODULE}.regime.{state}_flag",
         f"Range state · {state.replace('_', ' ')} flag", "Regime", "flag",
         f"Winner-take-all 0/1 flag for {state}.",
         "winner_take_all(scores, priority)",
         f"1 when {state} wins the family; 0 otherwise.",
         _flag_fn,
         inputs=[f"L3:{MODULE}.position.*"],
         params={"state": state, "priority": list(STATES)})

for state in STATES:
    def _dur_fn(df, s=state):
        return duration(_wta(df)[1][f"{s}_flag"])
    _reg(f"{MODULE}.motion.{state}_duration",
         f"Range state · {state.replace('_', ' ')} duration", "Motion", "duration",
         f"Consecutive bars {state} has been on.", "duration(flag)",
         f"Persistence of the {state} state.",
         _dur_fn,
         inputs=[f"L3:{MODULE}.regime.{state}_flag"], params={"state": state})

for state in STATES:
    def _trn_fn(df, s=state):
        return transition(_wta(df)[1][f"{s}_flag"])
    _reg(f"{MODULE}.motion.{state}_transition",
         f"Range state · {state.replace('_', ' ')} transition", "Motion", "transition",
         f"+1/-1/0 entry/exit marker for {state}.", "transition(flag)",
         f"Entry/exit event for the {state} state.",
         _trn_fn,
         inputs=[f"L3:{MODULE}.regime.{state}_flag"], params={"state": state})

for state in STATES:
    def _conf_fn(df, s=state):
        scores, wta, _ = _wta(df)
        # Confidence approximation: winner-margin at each bar times score.
        M = np.column_stack([scores[n].values.astype(float) for n in STATES])
        idx = STATES.index(s)
        top = np.nanmax(M, axis=1)
        second_mask = np.ones(M.shape[1], dtype=bool); second_mask[idx] = False
        second = np.where(M.shape[1] > 1, np.nanmax(M[:, second_mask], axis=1), 0.0)
        margin = np.clip(top - second, 0.0, 1.0)
        c = (scores[s].values.astype(float) * margin)
        c = np.clip(np.where(np.isfinite(c), c, 0.0), 0.0, 1.0)
        return pd.Series(c, index=scores[s].index, dtype=float)
    _reg(f"{MODULE}.statistics.{state}_confidence",
         f"Range state · {state.replace('_', ' ')} confidence", "Statistics", "confidence",
         f"Winner-margin-weighted confidence in the {state} classification.",
         "score * (top - second_best_score)",
         f"How separated {state} is from the runner-up state.",
         _conf_fn,
         inputs=[f"L3:{MODULE}.position.*"], params={"state": state})

def _active_code_fn(df):
    return _wta(df)[1]["active_code"]
_reg(f"{MODULE}.regime.active_state_code",
     "Range state · active state code", "Regime", "active_state",
     "0=none, 1=range_formation, 2=breakout_environment, 3=range_expansion.",
     "winner_take_all(scores, priority).active_code",
     "The dominant range-family state at bar t.",
     _active_code_fn,
     inputs=[f"L3:{MODULE}.position.*"],
     params={"codes": {"0": "none", "1": "range_formation",
                        "2": "breakout_environment", "3": "range_expansion"}})

def _active_conf_fn(df):
    scores, wta, _ = _wta(df)
    code = wta["active_code"].values.astype(int)
    out = np.zeros(len(code), dtype=float)
    for i, c in enumerate(code):
        if c == 0:
            out[i] = 0.0
        else:
            v = scores[STATES[c - 1]].iloc[i]
            out[i] = float(v) if np.isfinite(v) else 0.0
    return pd.Series(np.clip(out, 0.0, 1.0), index=wta["active_code"].index)
_reg(f"{MODULE}.statistics.active_state_confidence",
     "Range state · active state confidence", "Statistics", "active_state",
     "Score of the winning range-family state; 0 when none.",
     "score_of(active_code)",
     "How strongly the winning range state is held.",
     _active_conf_fn,
     inputs=[f"L3:{MODULE}.regime.active_state_code", f"L3:{MODULE}.position.*"])

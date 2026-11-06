"""Liquidity State — Layer 3 (Market Understanding).

Book 1 Ch. 5 exemplar: Liquidity Sweeps. Family: sweep_up / sweep_down /
liquidity_neutral. See docs/L3_MARKET_UNDERSTANDING.md §6.4.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l3_market_understanding._layer_bridge import l1_series, l2_series
from atlas_core.layers.l3_market_understanding._state_kernel import (
    weighted_score, duration, transition, winner_take_all,
)

MODULE = "liquidity_state"
STATES = ("sweep_up", "sweep_down", "liquidity_neutral")


def _reg(id_, name, perspective, family, definition, formula, interp,
         fn, inputs, params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=3, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=params or {}, complexity=complexity, fn=fn,
    ))


def _evidence(df: pd.DataFrame):
    bos      = l2_series(df, "market_structure.motion.bos_k5")
    choch    = l2_series(df, "market_structure.regime.choch_flag_k5")
    exec_imb = l1_series(df, "microstructure.expansion.execution_imbalance_20")
    wick_rat = l1_series(df, "microstructure.geometry.wick_difference_ratio")
    struct_r = l2_series(df, "market_structure.regime.structure_regime_k5")
    return {"bos": bos, "choch": choch, "exec_imb": exec_imb,
            "wick_rat": wick_rat, "struct_r": struct_r}


def _scores(df: pd.DataFrame):
    ev = _evidence(df)
    # Sweep up: recent BOS positive with upper-wick dominant AND executed imbalance negative
    # (sweep and reject): a bullish break followed by rejection.
    bos_up_recent = (ev["bos"].clip(lower=0.0)).rolling(3, min_periods=1).max()
    up = weighted_score({
        "bos_up": bos_up_recent.clip(0.0, 1.0),
        "upper_wick": (ev["wick_rat"] * -1.0).clip(0.0, 1.0),
        "neg_exec_imb": (-ev["exec_imb"]).clip(lower=0.0).clip(0.0, 1.0),
        "choch": ev["choch"].abs().clip(0.0, 1.0),
    }, {"bos_up": 0.35, "upper_wick": 0.30, "neg_exec_imb": 0.20, "choch": 0.15})

    bos_dn_recent = ((-ev["bos"]).clip(lower=0.0)).rolling(3, min_periods=1).max()
    down = weighted_score({
        "bos_dn": bos_dn_recent.clip(0.0, 1.0),
        "lower_wick": ev["wick_rat"].clip(0.0, 1.0),
        "pos_exec_imb": ev["exec_imb"].clip(lower=0.0).clip(0.0, 1.0),
        "choch": ev["choch"].abs().clip(0.0, 1.0),
    }, {"bos_dn": 0.35, "lower_wick": 0.30, "pos_exec_imb": 0.20, "choch": 0.15})

    # Neutral: complement — low sweep evidence.
    neutral = pd.Series((1.0 - np.maximum(up.values, down.values)).clip(0.0, 1.0),
                        index=up.index)
    return {"sweep_up": up, "sweep_down": down, "liquidity_neutral": neutral}, ev


def _wta(df: pd.DataFrame):
    scores, ev = _scores(df)
    wta = winner_take_all(scores, priority=STATES)
    return scores, wta, ev


for state in STATES:
    def _score_fn(df, s=state):
        return _scores(df)[0][s]
    _reg(f"{MODULE}.position.{state}_score",
         f"Liquidity state · {state.replace('_', ' ')} score", "Position", "score",
         f"Continuous strength of the {state} state.",
         "weighted_score(evidence, weights)",
         f"{state.replace('_', ' ').capitalize()} strength in [0, 1].",
         _score_fn,
         inputs=["L2:market_structure.*", "L1:microstructure.*"],
         params={"state": state})

for state in STATES:
    def _flag_fn(df, s=state):
        return _wta(df)[1][f"{s}_flag"]
    _reg(f"{MODULE}.regime.{state}_flag",
         f"Liquidity state · {state.replace('_', ' ')} flag", "Regime", "flag",
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
         f"Liquidity state · {state.replace('_', ' ')} duration", "Motion", "duration",
         f"Consecutive bars {state} has been on.", "duration(flag)",
         f"Persistence of the {state} state.",
         _dur_fn,
         inputs=[f"L3:{MODULE}.regime.{state}_flag"], params={"state": state})

for state in STATES:
    def _trn_fn(df, s=state):
        return transition(_wta(df)[1][f"{s}_flag"])
    _reg(f"{MODULE}.motion.{state}_transition",
         f"Liquidity state · {state.replace('_', ' ')} transition", "Motion", "transition",
         f"+1/-1/0 entry/exit marker for {state}.", "transition(flag)",
         f"Entry/exit event for the {state} state.",
         _trn_fn,
         inputs=[f"L3:{MODULE}.regime.{state}_flag"], params={"state": state})

for state in STATES:
    def _conf_fn(df, s=state):
        scores, wta, _ = _wta(df)
        M = np.column_stack([scores[n].values.astype(float) for n in STATES])
        idx = STATES.index(s)
        top = np.nanmax(M, axis=1)
        second_mask = np.ones(M.shape[1], dtype=bool); second_mask[idx] = False
        second = np.nanmax(M[:, second_mask], axis=1)
        margin = np.clip(top - second, 0.0, 1.0)
        c = np.clip((scores[s].values.astype(float) * margin), 0.0, 1.0)
        c = np.where(np.isfinite(c), c, 0.0)
        return pd.Series(c, index=scores[s].index, dtype=float)
    _reg(f"{MODULE}.statistics.{state}_confidence",
         f"Liquidity state · {state.replace('_', ' ')} confidence",
         "Statistics", "confidence",
         f"Winner-margin-weighted confidence in the {state} classification.",
         "score * (top - second_best_score)",
         f"How separated {state} is from the runner-up state.",
         _conf_fn,
         inputs=[f"L3:{MODULE}.position.*"], params={"state": state})

def _active_code_fn(df):
    return _wta(df)[1]["active_code"]
_reg(f"{MODULE}.regime.active_state_code",
     "Liquidity state · active state code", "Regime", "active_state",
     "0=none, 1=sweep_up, 2=sweep_down, 3=liquidity_neutral.",
     "winner_take_all(scores, priority).active_code",
     "The dominant liquidity-family state at bar t.",
     _active_code_fn,
     inputs=[f"L3:{MODULE}.position.*"],
     params={"codes": {"0": "none", "1": "sweep_up", "2": "sweep_down",
                        "3": "liquidity_neutral"}})

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
     "Liquidity state · active state confidence", "Statistics", "active_state",
     "Score of the winning liquidity-family state.",
     "score_of(active_code)",
     "How strongly the winning liquidity state is held.",
     _active_conf_fn,
     inputs=[f"L3:{MODULE}.regime.active_state_code", f"L3:{MODULE}.position.*"])

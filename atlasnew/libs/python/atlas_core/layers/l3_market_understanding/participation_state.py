"""Participation State — Layer 3 (Market Understanding).

Book 1 Ch. 5 exemplar family: accumulation / distribution /
mean_reversion. See docs/L3_MARKET_UNDERSTANDING.md §6.3.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l3_market_understanding._layer_bridge import l1_series, l2_series
from atlas_core.layers.l3_market_understanding._state_kernel import (
    weighted_score, duration, transition, winner_take_all,
)

MODULE = "participation_state"
STATES = ("accumulation", "distribution", "mean_reversion")


def _reg(id_, name, perspective, family, definition, formula, interp,
         fn, inputs, params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=3, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=params or {}, complexity=complexity, fn=fn,
    ))


def _evidence(df: pd.DataFrame):
    pvc     = l1_series(df, "volume.regime.pv_confirmation_20")
    vsigned = l1_series(df, "volume.regime.signed_ema_20")
    bos     = l2_series(df, "market_structure.motion.bos_k5")
    velp    = l2_series(df, "momentum_of_trend.motion.lr_slope_20_velocity_20")
    vrank   = l1_series(df, "volume.position.pct_rank_100")
    zscore  = l1_series(df, "price.statistics.zscore_20")
    return {"pvc": pvc, "vsigned": vsigned, "bos": bos,
            "velp": velp, "vrank": vrank, "zscore": zscore}


def _scores(df: pd.DataFrame):
    ev = _evidence(df)
    # Accumulation: rising volume rank, positive PV confirmation, non-negative velocity,
    # non-negative BOS bias.
    acc = weighted_score({
        "pvc_pos": ev["pvc"].clip(lower=0.0),
        "vsigned_pos": ev["vsigned"].clip(lower=0.0),
        "vrank": ev["vrank"].clip(0.0, 1.0),
        "velp_ok": (ev["velp"].fillna(0.0) >= 0.0).astype(float) * 0.5
                   + (ev["velp"].clip(lower=0.0)).clip(0.0, 1.0) * 0.5,
        "bos_pos": (ev["bos"] > 0).astype(float),
    }, {"pvc_pos": 0.30, "vsigned_pos": 0.20, "vrank": 0.20,
        "velp_ok": 0.15, "bos_pos": 0.15})

    # Distribution: mirror of accumulation.
    dis = weighted_score({
        "pvc_neg": (-ev["pvc"]).clip(lower=0.0),
        "vsigned_neg": (-ev["vsigned"]).clip(lower=0.0),
        "vrank": ev["vrank"].clip(0.0, 1.0),
        "velp_ok": (ev["velp"].fillna(0.0) <= 0.0).astype(float) * 0.5
                   + ((-ev["velp"]).clip(lower=0.0)).clip(0.0, 1.0) * 0.5,
        "bos_neg": (ev["bos"] < 0).astype(float),
    }, {"pvc_neg": 0.30, "vsigned_neg": 0.20, "vrank": 0.20,
        "velp_ok": 0.15, "bos_neg": 0.15})

    # Mean reversion: |zscore| extreme AND weak PV confirmation (fade-worthy).
    z = ev["zscore"].abs().clip(0.0, 3.0) / 3.0
    weak_pv = 1.0 - ev["pvc"].abs().clip(0.0, 1.0)
    mr = weighted_score({
        "extreme_z": z,
        "weak_pv": weak_pv,
    }, {"extreme_z": 0.6, "weak_pv": 0.4})

    return {"accumulation": acc, "distribution": dis, "mean_reversion": mr}, ev


def _wta(df: pd.DataFrame):
    scores, ev = _scores(df)
    wta = winner_take_all(scores, priority=STATES)
    return scores, wta, ev


for state in STATES:
    def _score_fn(df, s=state):
        return _scores(df)[0][s]
    _reg(f"{MODULE}.position.{state}_score",
         f"Participation state · {state.replace('_', ' ')} score",
         "Position", "score",
         f"Continuous strength of the {state} state.",
         "weighted_score(evidence, weights)",
         f"{state.replace('_', ' ').capitalize()} strength in [0, 1].",
         _score_fn,
         inputs=["L1:volume.*", "L1:price.statistics.zscore_20",
                 "L2:market_structure.motion.bos_k5",
                 "L2:momentum_of_trend.motion.lr_slope_20_velocity_20"],
         params={"state": state})

for state in STATES:
    def _flag_fn(df, s=state):
        return _wta(df)[1][f"{s}_flag"]
    _reg(f"{MODULE}.regime.{state}_flag",
         f"Participation state · {state.replace('_', ' ')} flag",
         "Regime", "flag",
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
         f"Participation state · {state.replace('_', ' ')} duration",
         "Motion", "duration",
         f"Consecutive bars the {state} flag has been on.",
         "duration(flag)",
         f"Persistence of the {state} state.",
         _dur_fn,
         inputs=[f"L3:{MODULE}.regime.{state}_flag"], params={"state": state})

for state in STATES:
    def _trn_fn(df, s=state):
        return transition(_wta(df)[1][f"{s}_flag"])
    _reg(f"{MODULE}.motion.{state}_transition",
         f"Participation state · {state.replace('_', ' ')} transition",
         "Motion", "transition",
         f"+1/-1/0 entry/exit marker for {state}.",
         "transition(flag)",
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
         f"Participation state · {state.replace('_', ' ')} confidence",
         "Statistics", "confidence",
         f"Winner-margin-weighted confidence in the {state} classification.",
         "score * (top - second_best_score)",
         f"How separated {state} is from the runner-up state.",
         _conf_fn,
         inputs=[f"L3:{MODULE}.position.*"], params={"state": state})

def _active_code_fn(df):
    return _wta(df)[1]["active_code"]
_reg(f"{MODULE}.regime.active_state_code",
     "Participation state · active state code", "Regime", "active_state",
     "0=none, 1=accumulation, 2=distribution, 3=mean_reversion.",
     "winner_take_all(scores, priority).active_code",
     "The dominant participation-family state at bar t.",
     _active_code_fn,
     inputs=[f"L3:{MODULE}.position.*"],
     params={"codes": {"0": "none", "1": "accumulation",
                        "2": "distribution", "3": "mean_reversion"}})

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
     "Participation state · active state confidence", "Statistics", "active_state",
     "Score of the winning participation-family state; 0 when none.",
     "score_of(active_code)",
     "How strongly the winning participation state is held.",
     _active_conf_fn,
     inputs=[f"L3:{MODULE}.regime.active_state_code", f"L3:{MODULE}.position.*"])

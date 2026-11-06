"""Market Regime — Layer 3 (Market Understanding).

Book 1 Ch. 5 exemplar: Market Regimes. Four-way winner-take-all
regime classification (trending × ranging) × (quiet × volatile).
See docs/L3_MARKET_UNDERSTANDING.md §6.5.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition
from atlas_core.layers.l3_market_understanding._layer_bridge import l1_series, l2_series
from atlas_core.layers.l3_market_understanding._state_kernel import (
    weighted_score, duration, transition, winner_take_all,
)

MODULE = "market_regime"
STATES = ("trending_quiet", "trending_volatile", "ranging_quiet", "ranging_volatile")


def _reg(id_, name, perspective, family, definition, formula, interp,
         fn, inputs, params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=3, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=inputs, params=params or {}, complexity=complexity, fn=fn,
    ))


def _evidence(df: pd.DataFrame):
    adx    = l1_series(df, "price.regime.adx_14")
    choppy = l1_series(df, "price.regime.choppiness_14")
    tercile= l1_series(df, "volatility.regime.tercile_200")
    consensus = l2_series(df, "trend_relationships.regime.directional_consensus_score_20")
    return {"adx": adx, "choppy": choppy, "tercile": tercile, "consensus": consensus}


def _scores(df: pd.DataFrame):
    ev = _evidence(df)
    # Normalisers.
    adx_n     = (ev["adx"] / 60.0).clip(0.0, 1.0)          # ADX high → trending
    choppy_n  = ((ev["choppy"] - 38.2) / (61.8 - 38.2)).clip(0.0, 1.0)  # 38.2..61.8 canonical band
    quiet_n   = (2.0 - ev["tercile"].clip(1.0, 3.0)) / 2.0  # 1 → 0.5, 2 → 0, 3 → -0.5 → clipped
    quiet_n   = quiet_n.clip(0.0, 1.0)
    vol_n     = ((ev["tercile"] - 1.0) / 2.0).clip(0.0, 1.0)
    consensus_n = ev["consensus"].abs().clip(0.0, 1.0)

    # Trending strength (shared) & ranging strength (shared).
    trending = weighted_score({
        "adx": adx_n, "consensus": consensus_n,
        "low_chop": (1.0 - choppy_n),
    }, {"adx": 0.5, "consensus": 0.3, "low_chop": 0.2})
    ranging = weighted_score({
        "high_chop": choppy_n, "low_adx": (1.0 - adx_n),
        "low_consensus": (1.0 - consensus_n),
    }, {"high_chop": 0.4, "low_adx": 0.3, "low_consensus": 0.3})

    # Compose the four regimes.
    tq = weighted_score({"trending": trending, "quiet": quiet_n}, {"trending": 0.6, "quiet": 0.4})
    tv = weighted_score({"trending": trending, "volatile": vol_n}, {"trending": 0.6, "volatile": 0.4})
    rq = weighted_score({"ranging": ranging, "quiet": quiet_n}, {"ranging": 0.6, "quiet": 0.4})
    rv = weighted_score({"ranging": ranging, "volatile": vol_n}, {"ranging": 0.6, "volatile": 0.4})

    return {"trending_quiet": tq, "trending_volatile": tv,
            "ranging_quiet": rq, "ranging_volatile": rv}, ev


def _wta(df: pd.DataFrame):
    scores, ev = _scores(df)
    wta = winner_take_all(scores, priority=STATES)
    return scores, wta, ev


for state in STATES:
    def _score_fn(df, s=state):
        return _scores(df)[0][s]
    _reg(f"{MODULE}.position.{state}_score",
         f"Market regime · {state.replace('_', ' ')} score", "Position", "score",
         f"Continuous strength of the {state} regime.",
         "weighted_score(evidence, weights)",
         f"{state.replace('_', ' ').capitalize()} strength in [0, 1].",
         _score_fn,
         inputs=["L1:price.regime.adx_14", "L1:price.regime.choppiness_14",
                 "L1:volatility.regime.tercile_200",
                 "L2:trend_relationships.regime.directional_consensus_score_20"],
         params={"state": state})

for state in STATES:
    def _flag_fn(df, s=state):
        return _wta(df)[1][f"{s}_flag"]
    _reg(f"{MODULE}.regime.{state}_flag",
         f"Market regime · {state.replace('_', ' ')} flag", "Regime", "flag",
         f"Winner-take-all 0/1 flag for the {state} regime.",
         "winner_take_all(scores, priority)",
         f"1 when {state} wins the four-way regime classification.",
         _flag_fn,
         inputs=[f"L3:{MODULE}.position.*"],
         params={"state": state, "priority": list(STATES)})

for state in STATES:
    def _dur_fn(df, s=state):
        return duration(_wta(df)[1][f"{s}_flag"])
    _reg(f"{MODULE}.motion.{state}_duration",
         f"Market regime · {state.replace('_', ' ')} duration", "Motion", "duration",
         f"Consecutive bars {state} has been on.", "duration(flag)",
         f"Persistence of the {state} regime.",
         _dur_fn,
         inputs=[f"L3:{MODULE}.regime.{state}_flag"], params={"state": state})

for state in STATES:
    def _trn_fn(df, s=state):
        return transition(_wta(df)[1][f"{s}_flag"])
    _reg(f"{MODULE}.motion.{state}_transition",
         f"Market regime · {state.replace('_', ' ')} transition", "Motion", "transition",
         f"+1/-1/0 entry/exit marker for {state}.", "transition(flag)",
         f"Entry/exit event for the {state} regime.",
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
         f"Market regime · {state.replace('_', ' ')} confidence",
         "Statistics", "confidence",
         f"Winner-margin-weighted confidence in the {state} regime.",
         "score * (top - second_best_score)",
         f"How separated {state} is from the runner-up regime.",
         _conf_fn,
         inputs=[f"L3:{MODULE}.position.*"], params={"state": state})

def _active_code_fn(df):
    return _wta(df)[1]["active_code"]
_reg(f"{MODULE}.regime.active_state_code",
     "Market regime · active state code", "Regime", "active_state",
     "0=none, 1=trending_quiet, 2=trending_volatile, 3=ranging_quiet, 4=ranging_volatile.",
     "winner_take_all(scores, priority).active_code",
     "The dominant market regime at bar t.",
     _active_code_fn,
     inputs=[f"L3:{MODULE}.position.*"],
     params={"codes": {"0": "none", "1": "trending_quiet",
                        "2": "trending_volatile", "3": "ranging_quiet",
                        "4": "ranging_volatile"}})

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
     "Market regime · active state confidence", "Statistics", "active_state",
     "Score of the winning market regime; 0 when none.",
     "score_of(active_code)",
     "How strongly the winning market regime is held.",
     _active_conf_fn,
     inputs=[f"L3:{MODULE}.regime.active_state_code", f"L3:{MODULE}.position.*"])

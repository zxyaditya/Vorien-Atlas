"""Adaptive Weight Learner — interpretable, rolling-window logistic fit.

Learns weights for each Decision Engine signal based on how well its
directional votes have predicted realized forward-return signs over the
most recent K bars.

Every weight is an explainable statistic:
  - normalized |coefficient| from a rolling LogisticRegression
  - reported alongside a "coverage" score (share of samples where the
    signal was directional, not neutral)
  - and the model's rolling in-sample accuracy for context.

Never a neural network. Never opaque. Interpretability is the point.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, List

from atlas_core.compute import compute_features
from decision_engine.signals import (SIGNAL_FUNCS, SIGNAL_FEATURE_IDS,
                                      compute_all_signals)


def _historical_signal_matrix(df: pd.DataFrame, min_history: int = 120,
                              context: Dict[str, "pd.DataFrame"] = None,
                              sigs: pd.DataFrame = None) -> pd.DataFrame:
    """Rebuild the (direction*strength) matrix for every historical row.

    context: DEC-007 multi-symbol payload forwarded to compute_features so
    L2 cross-symbol features (relative_strength.*) populate against the
    chosen peer. Without a peer, those features stay NaN and their
    consumer signals report direction=0, strength=0.
    """
    if sigs is not None and not sigs.empty:
        return sigs

    X = compute_features(df, SIGNAL_FEATURE_IDS, context=context)
    if len(X) < min_history:
        return pd.DataFrame()

    names = [n for n, _ in SIGNAL_FUNCS]
    cols = {n: np.zeros(len(X)) for n in names}
    X_dicts = X.to_dict(orient="records")

    for i, row in enumerate(X_dicts):
        for n, fn in SIGNAL_FUNCS:
            try:
                s = fn(row)
                cols[n][i] = s["direction"] * s["strength"]
            except Exception:
                pass
    return pd.DataFrame(cols, index=X.index)


def learn_weights(df: pd.DataFrame, horizon: int = 5,
                  window: int = 200,
                  context: Dict[str, "pd.DataFrame"] = None,
                  sigs: pd.DataFrame = None) -> Dict[str, Any]:
    """Fit LR on the most recent `window` bars → interpretable weights.

    context: optional DEC-007 multi-symbol payload. When supplied, L2
    cross-symbol features participate in the historical matrix; when
    absent, they contribute a zero-variance column (β ≈ 0) — an honest
    signal that no directional information can be extracted without a
    peer.
    """
    sigs = _historical_signal_matrix(df, context=context, sigs=sigs)
    if sigs.empty:
        return {"error": "not enough history", "n": int(len(df))}

    close = df["close"].astype(float).values
    fwd = np.log(np.roll(close, -horizon) / close)
    fwd[-horizon:] = np.nan
    y = np.where(np.isnan(fwd), np.nan, (fwd > 0).astype(float))

    # Take last `window` rows with known outcomes.
    end = len(sigs) - horizon
    start = max(0, end - window)
    Xw = sigs.iloc[start:end].values
    yw = y[start:end]
    mask = np.isfinite(Xw).all(axis=1) & np.isfinite(yw)
    if mask.sum() < 60:
        return {"error": "not enough clean samples", "n": int(mask.sum())}
    Xf = Xw[mask]
    yf = yw[mask]

    # Guard: all-one-class target
    if len(np.unique(yf)) < 2:
        return {"error": "target has one class",
                "note": "market too monotonic in this window"}

    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    Xs = scaler.fit_transform(Xf)
    clf = LogisticRegression(max_iter=500, C=1.0, random_state=42)
    clf.fit(Xs, yf)
    coefs = np.abs(clf.coef_[0])
    acc = float(clf.score(Xs, yf))

    names = [n for n, _ in SIGNAL_FUNCS]
    total = float(coefs.sum())
    if total == 0:
        learned = {n: 0.0 for n in names}
    else:
        learned = {n: float(c / total) for n, c in zip(names, coefs)}

    # Coverage: how often each signal was directional (non-zero)
    coverage = {n: float((sigs[n].iloc[start:end] != 0).mean())
                for n in names}

    return {
        "window": int(len(Xf)),
        "horizon": horizon,
        "in_sample_accuracy": round(acc, 3),
        "learned_weights": {k: round(v, 4) for k, v in learned.items()},
        "raw_abs_coefficients": {n: round(float(c), 4)
                                 for n, c in zip(names, coefs)},
        "coverage": {k: round(v, 3) for k, v in coverage.items()},
        "explanation": (
            "Weights = normalized |β_i| from a logistic regression of "
            "signal_direction × signal_strength on the sign of the "
            f"{horizon}-bar forward log-return. Coverage = fraction of "
            "bars where the signal was directional. In-sample accuracy "
            "is reported for context, not extrapolation."
        ),
    }



# ═══════════════════════════════════════════════════════════════════════
# Session 11 · v0.11.0 — Regime-conditional adaptive weight learner
# ═══════════════════════════════════════════════════════════════════════
def learn_regime_conditional_weights(
    df, horizon: int = 5, window: int = 200,
    context: Dict[str, "pd.DataFrame"] = None,
    regime_feature_id: str = "market_regime.regime.active_state_code",
    min_samples_per_regime: int = 40,
) -> Dict[str, Any]:
    """Learn ONE weight vector per Layer-3 regime code.

    DEC-019. Extends `learn_weights` by partitioning the historical
    signal matrix by the L3 `market_regime.regime.active_state_code`
    feature (0..3, four regimes). Each partition receives its own
    interpretable LR fit; the returned dict maps `regime_code → weight
    vector`. Fully explainable; every weight is a normalised `|β|`.

    Falls back to a single global vector for any regime where fewer than
    `min_samples_per_regime` clean samples are available; that regime's
    entry is annotated `fallback = "global"` so callers can see why.
    """
    # Compute matrix ONCE here, and pass it to global learn_weights
    sigs = _historical_signal_matrix(df, context=context)
    if sigs.empty:
        global_result = {"error": "empty historical matrix", "n": int(len(df))}
    else:
        global_result = learn_weights(df, horizon=horizon, window=window,
                                      context=context, sigs=sigs)
        
    if "error" in global_result:
        return {
            "regime_feature_id": regime_feature_id,
            "regimes": {},
            "global_fallback": global_result,
            "error": global_result["error"],
        }

    from atlas_core.compute import compute_features
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    # Fetch the regime code as a Series indexed like sigs.
    try:
        reg = compute_features(df, [regime_feature_id], context=context)
        reg = reg[regime_feature_id]
    except Exception as e:  # pragma: no cover
        return {
            "regime_feature_id": regime_feature_id,
            "regimes": {},
            "global_fallback": global_result,
            "error": f"regime feature unavailable: {e}",
        }
    reg = reg.reindex(sigs.index)

    close = df["close"].astype(float).values
    fwd = np.log(np.roll(close, -horizon) / close)
    fwd[-horizon:] = np.nan
    y = np.where(np.isnan(fwd), np.nan, (fwd > 0).astype(float))

    end = len(sigs) - horizon
    start = max(0, end - window)
    idx = np.arange(start, end)
    Xw = sigs.iloc[start:end].values
    yw = y[start:end]
    rw = reg.iloc[start:end].values

    names = [n for n, _ in SIGNAL_FUNCS]
    regimes_out: Dict[str, Any] = {}
    regime_codes = sorted(
        {int(v) for v in rw if v == v and np.isfinite(v)}
    )
    for code in regime_codes:
        m = (rw == code) & np.isfinite(Xw).all(axis=1) & np.isfinite(yw)
        n_m = int(m.sum())
        if n_m < min_samples_per_regime or len(np.unique(yw[m])) < 2:
            regimes_out[str(int(code))] = {
                "n_samples": n_m,
                "fallback": "global",
                "learned_weights": global_result["learned_weights"],
            }
            continue
        scaler = StandardScaler()
        Xs = scaler.fit_transform(Xw[m])
        clf = LogisticRegression(max_iter=500, C=1.0, random_state=42)
        clf.fit(Xs, yw[m])
        coefs = np.abs(clf.coef_[0])
        total = float(coefs.sum())
        weights = ({n: float(c / total) for n, c in zip(names, coefs)}
                    if total > 0
                    else {n: 0.0 for n in names})
        acc = float(clf.score(Xs, yw[m]))
        regimes_out[str(int(code))] = {
            "n_samples": n_m,
            "in_sample_accuracy": round(acc, 3),
            "learned_weights": {k: round(v, 4) for k, v in weights.items()},
        }

    return {
        "regime_feature_id": regime_feature_id,
        "horizon": horizon,
        "window": window,
        "regimes": regimes_out,
        "global_fallback": global_result,
        "explanation": (
            "One interpretable LR fit per Layer-3 regime code. Weights = "
            "normalised |β_i|. Regimes with fewer than "
            f"{min_samples_per_regime} clean samples fall back to the "
            "global weight vector; that entry is annotated "
            "`fallback=\"global\"`."
        ),
    }

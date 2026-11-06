"""Multi-model ensemble — 4 real models vote independently.

XGBoost, RandomForest, GradientBoosting, LogisticRegression — all
scikit-compatible, no extra deps. Each produces a probability; meta-vote
counts them as directional votes plus a confidence.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, List

from atlas_core.compute import compute_features
from atlas_core.registry.registry import registry


def _build(df: pd.DataFrame, feature_ids: List[str], horizon: int = 5):
    if len(df) > 2000:
        df = df.iloc[-2000:].copy()
    X = compute_features(df, feature_ids)
    close = df["close"].astype(float).values
    fwd = np.log(np.roll(close, -horizon) / close)
    fwd[-horizon:] = np.nan
    y = (fwd > 0).astype(int)
    mask = np.isfinite(X.values).all(axis=1) & np.isfinite(fwd)
    return X.loc[mask], y[mask]


def train_ensemble(df: pd.DataFrame, feature_ids: List[str],
                   horizon: int = 5) -> Dict[str, Any]:
    X, y = _build(df, feature_ids, horizon)
    if len(X) < 80:
        return {"error": "not enough data", "n": int(len(X))}

    n = len(X)
    cut = int(n * 0.75)
    Xtr, Xte = X.iloc[:cut], X.iloc[cut:]
    ytr, yte = y[:cut], y[cut:]
    x_last = X.iloc[[-1]]

    from sklearn.ensemble import (RandomForestClassifier,
                                   GradientBoostingClassifier)
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from xgboost import XGBClassifier

    models = {
        "XGBoost": XGBClassifier(n_estimators=150, max_depth=4,
                                  learning_rate=0.06, subsample=0.9,
                                  colsample_bytree=0.8, eval_metric="logloss",
                                  random_state=42, n_jobs=-1),
        "RandomForest": RandomForestClassifier(n_estimators=200, max_depth=8,
                                                random_state=42, n_jobs=-1),
        "GradientBoost": GradientBoostingClassifier(n_estimators=120, max_depth=3,
                                                     random_state=42),
        "LogisticReg": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=500, random_state=42))
        ]),
    }

    per_model = []
    votes_long = 0; votes_short = 0; abstain = 0
    prob_ups = []
    accs = []
    top_features_all = {}

    for name, clf in models.items():
        try:
            clf.fit(Xtr, ytr)
            acc = float(clf.score(Xte, yte))
            proba = float(clf.predict_proba(x_last)[0, 1])
            accs.append(acc)
            prob_ups.append(proba)
            # Vote thresholds: >0.55 LONG, <0.45 SHORT, else abstain
            if proba > 0.55:
                vote = "LONG"; votes_long += 1
            elif proba < 0.45:
                vote = "SHORT"; votes_short += 1
            else:
                vote = "ABSTAIN"; abstain += 1
            # Feature importance
            imp = getattr(clf, "feature_importances_", None)
            if imp is None and hasattr(clf, "named_steps"):
                logreg = clf.named_steps.get("clf")
                if logreg is not None:
                    imp = np.abs(logreg.coef_[0])
            top = []
            if imp is not None:
                idx = np.argsort(imp)[-10:][::-1]
                for j in idx:
                    fid = X.columns[j]
                    top.append({"id": fid,
                                "name": (registry.get(fid).name
                                          if registry.contains(fid) else fid),
                                "importance": float(imp[j])})
                    top_features_all[fid] = top_features_all.get(fid, 0.0) + float(imp[j])
            per_model.append({
                "name": name, "test_accuracy": round(acc, 3),
                "prob_up": round(proba, 3), "vote": vote,
                "top_features": top,
            })
        except Exception as e:
            per_model.append({"name": name, "error": str(e)})

    mean_proba = float(np.mean(prob_ups)) if prob_ups else 0.5
    n_models = len(prob_ups)
    agreement = (max(votes_long, votes_short) / n_models) if n_models else 0.0

    if votes_long > votes_short and votes_long >= 2:
        meta = "LONG"
    elif votes_short > votes_long and votes_short >= 2:
        meta = "SHORT"
    else:
        meta = "ABSTAIN"

    # Aggregate top features across models
    agg = sorted(top_features_all.items(), key=lambda kv: -kv[1])[:15]
    aggregate_top = [{"id": fid, "name": (registry.get(fid).name
                                            if registry.contains(fid) else fid),
                      "importance": round(v, 4)} for fid, v in agg]

    return {
        "n_features_used": int(X.shape[1]),
        "n_train": int(cut), "n_test": int(n - cut),
        "mean_test_accuracy": round(float(np.mean(accs)), 3) if accs else None,
        "mean_prob_up": round(mean_proba, 3),
        "consensus_direction": meta,
        "votes": {"LONG": votes_long, "SHORT": votes_short,
                  "ABSTAIN": abstain},
        "agreement": round(agreement, 3),
        "per_model": per_model,
        "aggregate_top_features": aggregate_top,
    }

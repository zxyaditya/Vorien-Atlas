"""ML pipeline — v0.1: RandomForest + XGBoost with SHAP."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, List
from atlas_core.compute import compute_features
from atlas_core.registry.registry import registry


def build_dataset(df: pd.DataFrame, feature_ids: List[str],
                  horizon: int = 5) -> tuple:
    """Compute features + build classification target: sign of forward log-return."""
    X = compute_features(df, feature_ids)
    close = df["close"].astype(float).values
    fwd = np.log(np.roll(close, -horizon) / close)
    fwd[-horizon:] = np.nan
    y = np.sign(fwd)
    y[y == 0] = 1  # break ties positive
    mask = np.isfinite(X.values).all(axis=1) & np.isfinite(y)
    return X.loc[mask], y[mask], np.where(mask)[0]


def train_and_predict(df: pd.DataFrame, feature_ids: List[str],
                      horizon: int = 5, model: str = "xgboost"
                      ) -> Dict[str, Any]:
    X, y, idx = build_dataset(df, feature_ids, horizon)
    if len(X) < 50:
        return {"error": "not enough data", "n": int(len(X))}

    # temporal split — no shuffling
    n = len(X)
    cut = int(n * 0.75)
    Xtr, Xte = X.iloc[:cut], X.iloc[cut:]
    ytr, yte = y[:cut], y[cut:]

    if model == "randomforest":
        from sklearn.ensemble import RandomForestClassifier
        clf = RandomForestClassifier(n_estimators=200, max_depth=8,
                                     random_state=42, n_jobs=-1)
    else:
        from xgboost import XGBClassifier
        clf = XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.8, eval_metric="logloss",
            random_state=42, n_jobs=-1)
        # xgboost expects 0/1 labels
        ytr = (ytr > 0).astype(int)
        yte = (yte > 0).astype(int)

    clf.fit(Xtr, ytr)
    from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score, log_loss
    ypred = clf.predict(Xte)
    acc = float(accuracy_score(yte, ypred))
    prec = float(precision_score(yte, ypred, zero_division=0))
    rec = float(recall_score(yte, ypred, zero_division=0))
    
    try:
        y_proba = clf.predict_proba(Xte)
        roc_auc = float(roc_auc_score(yte, y_proba[:, 1] if y_proba.shape[1] > 1 else y_proba[:, 0]))
        logloss = float(log_loss(yte, y_proba))
    except Exception:
        roc_auc = 0.5
        logloss = 0.693
    
    last_x = X.iloc[[-1]]
    last_proba = float(clf.predict_proba(last_x)[0, -1]) \
        if hasattr(clf, "predict_proba") else None
    direction = "UP" if (last_proba or 0.5) > 0.5 else "DOWN"

    # Feature importance
    imp = getattr(clf, "feature_importances_", None)
    if imp is not None:
        feat_imp = sorted(
            [{"id": fid, "name": registry.get(fid).name if fid in registry._features else fid,
              "importance": float(v)}
             for fid, v in zip(X.columns, imp)],
            key=lambda d: -d["importance"])[:15]
    else:
        feat_imp = []

    return {
        "model": model, "horizon": horizon, "n_train": int(cut),
        "n_test": int(n - cut), "test_accuracy": round(acc, 4),
        "metrics": {
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
            "roc_auc": roc_auc,
            "log_loss": logloss
        },
        "prediction": {
            "direction": direction,
            "probability_up": round(last_proba, 4) if last_proba is not None else None,
            "confidence": round(abs((last_proba or 0.5) - 0.5) * 2, 4),
        },
        "top_features": feat_imp,
        "features_used": list(X.columns),
    }

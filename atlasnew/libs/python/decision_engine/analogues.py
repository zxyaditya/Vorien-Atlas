"""Historical Analogues — K-nearest-neighbours over Atlas feature snapshots.

Given the current feature vector at time T, find the K past timesteps
whose feature vectors are closest (Euclidean in z-scored space) and
report what happened afterward.

This is genuinely useful and Book-1 respecting — we are not inventing
new mathematics, only reusing Atlas features as a similarity metric.

v0.11.0 (DEC-019): the schema is now versioned. `schema="v1"` (default)
preserves the 19-dim L1-heavy space used since v0.5. `schema="v2"`
switches to the L4-embedding-based space (`L4_EMBEDDING_IDS` +
5 curated L2/L3 numerics), delivering a fully L1+L2+L3+L4 similarity
metric.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from atlas_core.compute import compute_features


# Compact analogue-feature set: stationary Perspectives only.
ANALOGUE_FEATURE_IDS_V1 = [
    "price.motion.log_return_5", "price.motion.log_return_20",
    "price.motion.ema_diff_5_20", "price.motion.ema_diff_20_50",
    "price.statistics.zscore_20", "price.statistics.zscore_50",
    "price.position.bb_percent_b_20_k2", "price.position.donchian_50",
    "price.position.pct_rank_50",
    "price.geometry.straightness_50", "price.geometry.hurst_64",
    "price.expansion.range_ratio_20", "price.expansion.bb_width_20_k2",
    "price.entropy.perm_o3_w30", "price.entropy.spectral_60",
    "price.regime.chande_momentum_14", "price.regime.choppiness_14",
    "price.regime.adx_14",
    "price.clustering.vol_ratio_10",
]

# v0.11.0: L4-embedding-based schema (DEC-019). Consumes `L4_EMBEDDING_IDS`
# from atlas_core (the v0.9.0 handshake constant) + 5 curated L2/L3
# dimensions so historical similarity uses the full stack.
def _v2_feature_ids():
    try:
        from atlas_core.layers.l4_representation import L4_EMBEDDING_IDS
    except Exception:
        L4_EMBEDDING_IDS = []
    curated = [
        # L2 · direction-neutral confidence
        "fractal_relationships.regime.self_similarity_score",
        "trend_relationships.regime.directional_consensus_score_20",
        # L3 · state confidences (winner-take-all)
        "trend_state.statistics.active_state_confidence",
        "range_state.statistics.active_state_confidence",
        "market_regime.statistics.active_state_confidence",
    ]
    return list(L4_EMBEDDING_IDS) + curated


ANALOGUE_FEATURE_IDS = ANALOGUE_FEATURE_IDS_V1   # back-compat alias


def find_analogues(df: pd.DataFrame, k: int = 10, horizon: int = 5,
                    schema: str = "v1") -> dict:
    if schema == "v2":
        ids = _v2_feature_ids()
    else:
        ids = ANALOGUE_FEATURE_IDS_V1
    X = compute_features(df, ids).copy()
    if len(X) < horizon + 30:
        return {"count": 0, "analogues": [], "summary": {},
                "schema": schema, "n_dims": int(X.shape[1])}

    # z-score every column to make distances scale-free
    mu, sd = X.mean(), X.std().replace(0, np.nan)
    Z = (X - mu) / sd
    Z = Z.fillna(0.0).values

    # Forward log-return over horizon
    close = df["close"].astype(float).values
    fwd = np.log(np.roll(close, -horizon) / close)
    fwd[-horizon:] = np.nan

    n = len(X)
    current = Z[-1]
    valid_end = n - horizon
    if valid_end < 30:
        return {"count": 0, "analogues": [], "summary": {},
                "schema": schema, "n_dims": int(X.shape[1])}

    dists = np.linalg.norm(Z[:valid_end] - current, axis=1)
    idx_sorted = np.argsort(dists)[:k]

    analogues = []
    for i in idx_sorted:
        analogues.append({
            "index": int(i),
            "distance": float(dists[i]),
            "date": str(df.index[i]),
            "close": float(close[i]),
            "forward_return_pct": round(100 * float(fwd[i]), 3),
        })

    returns = np.array([a["forward_return_pct"] for a in analogues])
    summary = {
        "k": len(analogues),
        "horizon": horizon,
        "mean_return_pct": round(float(np.mean(returns)), 3),
        "median_return_pct": round(float(np.median(returns)), 3),
        "std_return_pct": round(float(np.std(returns)), 3),
        "worst_case_pct": round(float(np.min(returns)), 3),
        "best_case_pct": round(float(np.max(returns)), 3),
        "hit_rate": round(float(np.mean(returns > 0)), 3),
    }

    return {"count": len(analogues), "analogues": analogues,
            "summary": summary, "schema": schema,
            "n_dims": int(X.shape[1])}

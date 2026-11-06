"""L4 Representation Kernel — layer-local primitives.

DEC-015 principle (extended to L4): primitives are layer-local until
reuse in another layer is observed. Book 1 Ch. 10 discovery discipline.
All functions are deterministic, closed-form, and NaN-tolerant.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Tuple, List
import warnings

EPS = 1e-12


def rolling_zscore(s: pd.Series, window: int = 100) -> pd.Series:
    """Rolling z-score of s. Constant windows → 0."""
    r = s.rolling(window, min_periods=max(5, window // 4))
    mu = r.mean()
    sd = r.std(ddof=0).replace(0.0, np.nan)
    z = (s - mu) / sd
    return z.fillna(0.0).astype(float)


def interaction(a: pd.Series, b: pd.Series, op: str = "product") -> pd.Series:
    """Element-wise interaction of two series.

    op ∈ {product, ratio, min, max, absdiff, sign_agree}.
    NaN-preserving. `ratio` guards against zero denominator.
    `sign_agree` returns +1 when both non-zero and same sign, -1 when
    both non-zero and opposite sign, 0 when either is zero.
    """
    A, B = a.astype(float), b.astype(float)
    if op == "product":
        return (A * B).astype(float)
    if op == "ratio":
        denom = B.replace(0.0, np.nan)
        return (A / denom).astype(float)
    if op == "min":
        return np.minimum(A, B)
    if op == "max":
        return np.maximum(A, B)
    if op == "absdiff":
        return (A - B).abs().astype(float)
    if op == "sign_agree":
        sa, sb = np.sign(A.values), np.sign(B.values)
        out = np.where((sa != 0) & (sb != 0),
                       np.where(sa == sb, 1.0, -1.0), 0.0)
        return pd.Series(out, index=A.index, dtype=float)
    raise ValueError(f"unknown interaction op={op!r}")


def one_hot(code: pd.Series, k: int) -> List[pd.Series]:
    """Dense one-hot: code ∈ {1..k} → k series in {0, 1}. code==0 gives all zeros."""
    c = code.astype(float).values
    idx = code.index
    out = []
    for i in range(1, k + 1):
        out.append(pd.Series((c == i).astype(float), index=idx, dtype=float))
    return out


def quantile_bin(s: pd.Series, k: int = 5, lookback: int = 100) -> pd.Series:
    """Rolling quantile-bin ordinal encoding.

    At bar t, the value s[t] is placed into one of k equal-frequency
    bins computed from the trailing lookback window (exclusive of t
    would introduce lag; we use inclusive-of-t which is standard for
    rank-based encodings and does not constitute future leakage).
    Returns bin index in {0..k-1}; NaN when window is too short.
    """
    n = len(s)
    x = s.astype(float).values
    out = np.full(n, np.nan)
    for i in range(n):
        lo = max(0, i - lookback + 1)
        w = x[lo:i + 1]
        w = w[np.isfinite(w)]
        if len(w) < max(5, k):
            continue
        edges = np.quantile(w, np.linspace(0.0, 1.0, k + 1))
        v = x[i]
        if not np.isfinite(v):
            continue
        # searchsorted-based; clip into range.
        bin_idx = int(np.clip(np.searchsorted(edges, v, side="right") - 1, 0, k - 1))
        out[i] = float(bin_idx)
    return pd.Series(out, index=s.index, dtype=float)


def rolling_rank(s: pd.Series, window: int = 100) -> pd.Series:
    """Rolling percentile rank in [0, 1] over the trailing window."""
    def _rank_last(w: np.ndarray) -> float:
        w = w[np.isfinite(w)]
        if len(w) < 2:
            return np.nan
        v = w[-1]
        return float((w <= v).sum()) / float(len(w))
    return s.rolling(window, min_periods=max(5, window // 4)).apply(_rank_last, raw=True)


def rolling_entropy(s: pd.Series, window: int = 20, bins: int = 5) -> pd.Series:
    """Shannon entropy of the histogram of the rolling window (nats)."""
    def _ent(w: np.ndarray) -> float:
        w = w[np.isfinite(w)]
        if len(w) < max(3, bins):
            return np.nan
        hist, _ = np.histogram(w, bins=bins)
        p = hist / max(1, hist.sum())
        p = p[p > 0]
        return float(-(p * np.log(p)).sum())
    return s.rolling(window, min_periods=max(3, bins)).apply(_ent, raw=True)


def rolling_dispersion(s: pd.Series, window: int = 20) -> pd.Series:
    """Coefficient of variation σ / |μ|. NaN when |μ| < EPS."""
    r = s.rolling(window, min_periods=max(3, window // 4))
    mu = r.mean().abs().replace(0.0, np.nan)
    sd = r.std(ddof=0)
    return (sd / mu).astype(float)


def rolling_pca(M: pd.DataFrame, k: int = 5, lookback: int = 250
                ) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Deterministic rolling PCA. Roll-forward, no future leakage.

    At bar t, compute PCA over rows [t-lookback+1 .. t] of M (after
    column-wise mean-centering AND scaling by std on the same window),
    take the top-k principal components, project the current-bar row
    onto them → pc[t]. Explained-variance ratios of the k components
    are also emitted.

    Returns two DataFrames aligned to M.index:
      pcs: columns ["pc1".."pc{k}"], NaN for warm-up bars
      evr: columns ["evr_1".."evr_{k}"], NaN for warm-up bars

    Sign convention: eigenvector with largest absolute-value at row 0
    of the sub-matrix is made positive — stabilises signs across
    rolling windows and makes the series deterministic.
    """
    n, d = M.shape
    idx = M.index
    pcs = np.full((n, k), np.nan)
    evr = np.full((n, k), np.nan)
    X_all = M.values.astype(float)
    min_w = max(30, k * 4)
    for t in range(n):
        lo = max(0, t - lookback + 1)
        W = X_all[lo:t + 1]
        if W.shape[0] < min_w:
            continue
        # NaN-fill columns with column median for the window.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            col_med = np.nanmedian(W, axis=0)
        col_med = np.where(np.isfinite(col_med), col_med, 0.0)
        Wf = np.where(np.isfinite(W), W, col_med[None, :])
        mu = Wf.mean(axis=0)
        sd = Wf.std(axis=0, ddof=0)
        sd = np.where(sd > EPS, sd, 1.0)
        Z = (Wf - mu) / sd
        try:
            # SVD of the standardised window.
            U, S, Vt = np.linalg.svd(Z, full_matrices=False)
        except np.linalg.LinAlgError:
            continue
        variances = (S ** 2) / max(Z.shape[0] - 1, 1)
        total = variances.sum()
        if total <= EPS:
            continue
        kk = min(k, len(S))
        # Sign stabilisation: force each PC's first row of scores to be positive.
        for j in range(kk):
            pc0_score = float((Z[0:1] @ Vt[j:j + 1].T).squeeze())
            if pc0_score < 0:
                Vt[j] = -Vt[j]
        # Project current-bar row (standardised in the same frame) onto the PCs.
        cur = X_all[t]
        cur = np.where(np.isfinite(cur), cur, col_med)
        z_cur = (cur - mu) / sd
        proj = Vt[:kk] @ z_cur
        pcs[t, :kk] = proj
        evr[t, :kk] = variances[:kk] / total
    pcs_df = pd.DataFrame(pcs, index=idx,
                          columns=[f"pc{i + 1}" for i in range(k)])
    evr_df = pd.DataFrame(evr, index=idx,
                          columns=[f"evr_{i + 1}" for i in range(k)])
    return pcs_df, evr_df

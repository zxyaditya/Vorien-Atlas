"""LSTM classifier plug-in.

A minimal but real recurrent neural network for the Learning-System
framework. Uses PyTorch CPU. Feature vectors are converted into short
sequences via `_windowize`: each row's sequence is the concatenation of
the past `seq_len` feature rows. Output = binary probability (P(up)).

Explainability: LSTM has no exact `feature_importances_`; we surface
the top-K features by |gradient of P(up) w.r.t. input at the last
time-step|, averaged over a batch. Deterministic given `seed`.
"""
from __future__ import annotations
from typing import Any, ClassVar, Dict, List

import numpy as np
import pandas as pd

from learning_system.models.base import BaseModel


def _register(cls):
    from learning_system.models import MODEL_REGISTRY
    if cls.kind not in MODEL_REGISTRY:
        MODEL_REGISTRY[cls.kind] = cls
    return cls


def _windowize(X: np.ndarray, seq_len: int) -> np.ndarray:
    """Return array of shape (n_valid, seq_len, n_features)."""
    n, k = X.shape
    if n <= seq_len:
        return np.zeros((0, seq_len, k), dtype=np.float32)
    windows = np.stack([X[i - seq_len:i] for i in range(seq_len, n)])
    return windows.astype(np.float32)


@_register
class LSTMModel(BaseModel):
    kind: ClassVar[str] = "lstm"
    default_hparams: ClassVar[Dict[str, Any]] = {
        "seq_len": 20,
        "hidden_size": 32,
        "num_layers": 1,
        "dropout": 0.10,
        "lr": 1e-3,
        "epochs": 12,
        "batch_size": 64,
    }

    def __init__(self, hyperparams: Dict[str, Any] = None, seed: int = 42):
        super().__init__(hyperparams, seed)
        import torch
        torch.manual_seed(int(seed))
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._mean: np.ndarray = None
        self._std: np.ndarray = None

    def _build_net(self, n_features: int):
        import torch.nn as nn
        hp = self.hyperparams

        class LSTMNet(nn.Module):
            def __init__(self):
                super().__init__()
                self.lstm = nn.LSTM(
                    input_size=n_features,
                    hidden_size=int(hp["hidden_size"]),
                    num_layers=int(hp["num_layers"]),
                    dropout=float(hp["dropout"]) if int(hp["num_layers"]) > 1 else 0.0,
                    batch_first=True,
                )
                self.head = nn.Linear(int(hp["hidden_size"]), 1)

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.head(out[:, -1, :]).squeeze(-1)

        return LSTMNet()

    # ---- fit / predict ---------------------------------------------
    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        import torch
        from torch import nn, optim
        hp = self.hyperparams
        self._feature_names = list(X.columns)
        Xv = X.values.astype(np.float32)
        # Standardise
        self._mean = np.nanmean(Xv, axis=0)
        self._std = np.nanstd(Xv, axis=0)
        self._mean[np.isnan(self._mean)] = 0.0
        self._std[np.isnan(self._std)] = 1.0
        self._std[self._std == 0] = 1.0
        Xs = (Xv - self._mean) / self._std
        Xs[np.isnan(Xs)] = 0.0
        seq_len = int(hp["seq_len"])
        windows = _windowize(Xs, seq_len)
        if len(windows) < 32:
            # Not enough data — train degenerate model that predicts 0.5.
            self._model = None
            return
        y_aligned = np.asarray(y[seq_len:], dtype=np.float32)
        # Numeric-safety: drop rows with NaN.
        finite = np.isfinite(windows).all(axis=(1, 2)) & np.isfinite(y_aligned)
        windows, y_aligned = windows[finite], y_aligned[finite]
        if len(windows) < 16:
            self._model = None
            return

        net = self._build_net(Xv.shape[1]).to(self._device)
        opt = optim.Adam(net.parameters(), lr=float(hp["lr"]))
        loss_fn = nn.BCEWithLogitsLoss()
        Xt = torch.from_numpy(windows).to(self._device)
        yt = torch.from_numpy(y_aligned).to(self._device)
        bs = int(hp["batch_size"])
        n = len(windows)
        for _ in range(int(hp["epochs"])):
            perm = torch.randperm(n)
            for start in range(0, n, bs):
                idx = perm[start:start + bs]
                opt.zero_grad()
                logits = net(Xt[idx])
                loss = loss_fn(logits, yt[idx])
                loss.backward()
                opt.step()
        net.eval()
        self._model = net

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        import torch
        n = len(X)
        out = np.full((n, 2), 0.5, dtype=np.float32)
        if self._model is None:
            return out
        Xv = X[self._feature_names].values.astype(np.float32)
        Xs = (Xv - self._mean) / self._std
        Xs[np.isnan(Xs)] = 0.0
        seq_len = int(self.hyperparams["seq_len"])
        if n <= seq_len:
            return out
        # Windows aligned to the *last* row of each window: window i
        # (for i in range(seq_len, n)) uses rows [i-seq_len : i] and
        # predicts P(up) at row i. This yields exactly (n - seq_len)
        # predictions filling `out[seq_len:]`.
        windows = np.stack([Xs[i - seq_len:i] for i in range(seq_len, n)])
        Xt = torch.from_numpy(windows).to(self._device)
        with torch.no_grad():
            logits = self._model(Xt).cpu().numpy()
        p = 1.0 / (1.0 + np.exp(-logits))
        out[seq_len:, 1] = p
        out[seq_len:, 0] = 1.0 - p
        return out

    def feature_importances(self) -> Dict[str, float]:
        """Sensitivity: |dP/dx| averaged across a synthetic probe batch."""
        if self._model is None or not self._feature_names:
            return {}
        import torch
        seq_len = int(self.hyperparams["seq_len"])
        n_features = len(self._feature_names)
        # Zero-mean unit-variance probe (since inputs are standardised).
        probe = torch.zeros((16, seq_len, n_features), dtype=torch.float32,
                              device=self._device, requires_grad=True)
        logits = self._model(probe)
        s = logits.sum()
        s.backward()
        grad = probe.grad.detach().cpu().numpy()          # (16, seq_len, F)
        # Use only the last time-step (that's what the head consumes).
        g_last = np.abs(grad[:, -1, :]).mean(axis=0)
        s = g_last.sum()
        if s > 0:
            g_last = g_last / s
        return {name: float(v) for name, v in zip(self._feature_names, g_last)}

    # ---- persistence -----------------------------------------------
    def to_disk(self, path) -> None:
        import joblib
        import torch
        payload = {
            "kind": self.kind, "hyperparams": self.hyperparams,
            "seed": self.seed, "feature_names": self._feature_names,
            "mean": self._mean, "std": self._std,
            "state_dict": (None if self._model is None
                             else self._model.state_dict()),
            "n_features": (len(self._feature_names)
                             if self._feature_names else 0),
        }
        joblib.dump(payload, path)

    @classmethod
    def from_disk(cls, path) -> "LSTMModel":
        import joblib
        payload = joblib.load(path)
        inst = cls(hyperparams=payload["hyperparams"], seed=payload["seed"])
        inst._feature_names = payload["feature_names"]
        inst._mean = payload["mean"]
        inst._std = payload["std"]
        if payload.get("state_dict") is not None and payload["n_features"] > 0:
            net = inst._build_net(int(payload["n_features"])).to(inst._device)
            net.load_state_dict(payload["state_dict"])
            net.eval()
            inst._model = net
        return inst

"""TFTModel — Temporal Fusion Transformer (simplified) plug-in.

A compact variant of the Temporal Fusion Transformer (Lim et al. 2019)
suited to Atlas's tabular time series:

  1. **Variable-selection network (VSN)**: per-feature gating that
     learns which features to attend to at each time step.
  2. **Gated residual network (GRN)**: variable-selected features go
     through a GRN that adds a non-linear transform with a residual
     skip and a gate.
  3. **Interpretable self-attention**: a single multihead attention
     over the resulting sequence, exposing attention weights that a
     future explainer can surface.
  4. **Position-wise feed-forward + head**: yields P(up) at the last
     step.

We deliberately skip the full TFT features (static covariates, quantile
heads, decoder). The subset above already captures TFT's distinguishing
architectural ideas (VSN + GRN + attention) and satisfies the plug-in
contract with zero framework change.
"""
from __future__ import annotations
from typing import Any, ClassVar, Dict

import numpy as np
import pandas as pd

from learning_system.models.base import BaseModel


def _register(cls):
    from learning_system.models import MODEL_REGISTRY
    if cls.kind not in MODEL_REGISTRY:
        MODEL_REGISTRY[cls.kind] = cls
    return cls


@_register
class TFTModel(BaseModel):
    kind: ClassVar[str] = "tft"
    default_hparams: ClassVar[Dict[str, Any]] = {
        "seq_len": 20,
        "d_model": 24,
        "nhead": 4,
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
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
        hp = self.hyperparams
        d_model = int(hp["d_model"])

        class GRN(nn.Module):
            """Gated Residual Network (Lim et al. 2019)."""
            def __init__(self, dim: int, dropout: float):
                super().__init__()
                self.lin1 = nn.Linear(dim, dim)
                self.lin2 = nn.Linear(dim, dim)
                self.gate = nn.Linear(dim, dim)
                self.drop = nn.Dropout(dropout)
                self.norm = nn.LayerNorm(dim)

            def forward(self, x):
                h = F.elu(self.lin1(x))
                h = self.drop(self.lin2(h))
                g = torch.sigmoid(self.gate(x))
                return self.norm(x + g * h)

        class VSN(nn.Module):
            """Variable-selection network (per-feature gating)."""
            def __init__(self, n_in: int, d_model: int):
                super().__init__()
                self.proj = nn.Linear(n_in, d_model)
                self.gate = nn.Linear(n_in, n_in)

            def forward(self, x):
                # x: (batch, seq, n_features) -> softmax gates -> (batch,seq,d_model)
                w = torch.softmax(self.gate(x), dim=-1)
                x = x * w                          # gated features
                return self.proj(x)

        class TFTNet(nn.Module):
            def __init__(self):
                super().__init__()
                self.vsn = VSN(n_features, d_model)
                self.grn = GRN(d_model, float(hp["dropout"]))
                self.attn = nn.MultiheadAttention(
                    embed_dim=d_model, num_heads=int(hp["nhead"]),
                    dropout=float(hp["dropout"]), batch_first=True,
                )
                self.norm = nn.LayerNorm(d_model)
                self.head = nn.Linear(d_model, 1)

            def forward(self, x):
                z = self.vsn(x)                       # (B, T, d)
                z = self.grn(z)                       # (B, T, d)
                a, _ = self.attn(z, z, z, need_weights=False)
                z = self.norm(z + a)                  # residual + norm
                return self.head(z[:, -1, :]).squeeze(-1)

        return TFTNet()

    def _windowize(self, X: np.ndarray) -> np.ndarray:
        seq_len = int(self.hyperparams["seq_len"])
        n, k = X.shape
        if n <= seq_len:
            return np.zeros((0, seq_len, k), dtype=np.float32)
        return np.stack([X[i - seq_len:i]
                          for i in range(seq_len, n)]).astype(np.float32)

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        import torch
        from torch import nn, optim
        hp = self.hyperparams
        self._feature_names = list(X.columns)
        Xv = X.values.astype(np.float32)
        self._mean = np.nanmean(Xv, axis=0)
        self._std = np.nanstd(Xv, axis=0)
        self._mean[np.isnan(self._mean)] = 0.0
        self._std[np.isnan(self._std)] = 1.0
        self._std[self._std == 0] = 1.0
        Xs = (Xv - self._mean) / self._std
        Xs[np.isnan(Xs)] = 0.0
        seq_len = int(hp["seq_len"])
        windows = self._windowize(Xs)
        if len(windows) < 32:
            self._model = None
            return
        y_aligned = np.asarray(y[seq_len:], dtype=np.float32)
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
        net.train()
        for _ in range(int(hp["epochs"])):
            perm = torch.randperm(n)
            for start in range(0, n, bs):
                idx = perm[start:start + bs]
                opt.zero_grad()
                loss_fn(net(Xt[idx]), yt[idx]).backward()
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
        windows = np.stack([Xs[i - seq_len:i] for i in range(seq_len, n)])
        Xt = torch.from_numpy(windows).to(self._device)
        with torch.no_grad():
            logits = self._model(Xt).cpu().numpy()
        p = 1.0 / (1.0 + np.exp(-logits))
        out[seq_len:, 1] = p
        out[seq_len:, 0] = 1.0 - p
        return out

    def feature_importances(self) -> Dict[str, float]:
        if self._model is None or not self._feature_names:
            return {}
        import torch
        seq_len = int(self.hyperparams["seq_len"])
        n_features = len(self._feature_names)
        probe = torch.zeros((16, seq_len, n_features), dtype=torch.float32,
                             device=self._device, requires_grad=True)
        logits = self._model(probe)
        s = logits.sum()
        s.backward()
        grad = probe.grad.detach().cpu().numpy()
        g_last = np.abs(grad[:, -1, :]).mean(axis=0)
        s = g_last.sum()
        if s > 0:
            g_last = g_last / s
        return {name: float(v) for name, v in zip(self._feature_names, g_last)}

    def to_disk(self, path) -> None:
        import joblib
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
    def from_disk(cls, path) -> "TFTModel":
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

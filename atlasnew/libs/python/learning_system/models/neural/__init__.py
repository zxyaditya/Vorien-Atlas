"""Neural-network model plug-ins (LSTM / Transformer / TFT / ...).

DEC-018 plug-in contract. Each concrete class inherits `BaseModel` and
registers via `@register_model`. Imports of `torch` are guarded so the
rest of Atlas keeps working if PyTorch is not installed.
"""
from __future__ import annotations

try:
    import torch  # noqa: F401
    _TORCH_AVAILABLE = True
except Exception:
    _TORCH_AVAILABLE = False

if _TORCH_AVAILABLE:
    from learning_system.models.neural import lstm_model   # noqa: F401
    from learning_system.models.neural import transformer_model   # noqa: F401
    from learning_system.models.neural import tft_model   # noqa: F401


def torch_available() -> bool:
    return _TORCH_AVAILABLE

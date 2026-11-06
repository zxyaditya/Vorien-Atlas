import os
import re

with open("signals.py", "r", encoding="utf-8") as f:
    content = f.read()

# Define the new files
core_code = """from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, List

def _last(series):
    if series is None:
        return None
    try:
        v = float(series.iloc[-1] if isinstance(series, pd.Series) else series)
        return v if np.isfinite(v) else None
    except Exception:
        return None

def _get(vals: Dict[str, float], fid: str, default=None):
    v = vals.get(fid)
    return v if v is not None and np.isfinite(v) else default

def _make_signal(name: str, direction: int, strength: float,
                 confidence: float, evidence: List[dict]) -> dict:
    return {
        "name": name,
        "direction": int(direction),           # -1, 0, +1
        "strength": float(max(0.0, min(1.0, strength))),
        "confidence": float(max(0.0, min(1.0, confidence))),
        "evidence": evidence,
    }

def _row(fid: str, val, arg: str, wt: float) -> dict:
    return {"feature_id": fid, "value": val, "argument": arg, "weight": wt}
"""

l1_funcs = ["trend_signal", "momentum_signal", "volatility_signal", "volume_signal", "liquidity_signal", "structure_signal", "entropy_signal", "meanrev_signal", "regime_signal", "microstructure_signal"]
l2_funcs = ["trend_momentum_signal", "trend_alignment_signal", "fractal_coherence_signal", "relative_strength_signal", "market_structure_signal"]
l3_funcs = ["_l3_signal", "trend_state_signal", "momentum_state_signal", "volatility_state_signal", "volume_state_signal", "liquidity_state_signal", "structure_state_signal"]

l1_code = "from typing import Dict, Any, List\nimport numpy as np\nfrom .core import _get, _make_signal, _row\n\n"
l2_code = "from typing import Dict, Any, List\nimport numpy as np\nfrom .core import _get, _make_signal, _row\n\n"
l3_code = "from typing import Dict, Any, List\nimport numpy as np\nfrom .core import _get, _make_signal, _row\n\n"

registry_code = """from typing import Dict, Any, List
from .l1_primitive import *
from .l2_cross_feature import *
from .l3_state import *
import pandas as pd
"""

# Extract all functions
func_pattern = re.compile(r"def (\w+)\(.*?\)(?: -> .*?)?:.*?(?=\n(?:def |\# ═|$))", re.DOTALL)
funcs = func_pattern.finditer(content)

registry_extras = []
for match in funcs:
    func_name = match.group(1)
    func_body = match.group(0)
    
    if func_name in l1_funcs:
        l1_code += func_body + "\n\n"
    elif func_name in l2_funcs:
        l2_code += func_body + "\n\n"
    elif func_name in l3_funcs:
        l3_code += func_body + "\n\n"
    elif func_name not in ["_last", "_get", "_make_signal", "_row"]:
        registry_extras.append(func_body)

registry_code += "\n".join(registry_extras) + "\n"

# Create package
os.makedirs("signals", exist_ok=True)
with open("signals/__init__.py", "w", encoding="utf-8") as f:
    f.write("from .registry import SIGNAL_FUNCS, SIGNAL_WEIGHTS, SIGNAL_FEATURE_IDS, compute_all_signals\n")
    f.write("__all__ = ['SIGNAL_FUNCS', 'SIGNAL_WEIGHTS', 'SIGNAL_FEATURE_IDS', 'compute_all_signals']\n")

with open("signals/core.py", "w", encoding="utf-8") as f:
    f.write(core_code)
with open("signals/l1_primitive.py", "w", encoding="utf-8") as f:
    f.write(l1_code)
with open("signals/l2_cross_feature.py", "w", encoding="utf-8") as f:
    f.write(l2_code)
with open("signals/l3_state.py", "w", encoding="utf-8") as f:
    f.write(l3_code)
with open("signals/registry.py", "w", encoding="utf-8") as f:
    f.write(registry_code)

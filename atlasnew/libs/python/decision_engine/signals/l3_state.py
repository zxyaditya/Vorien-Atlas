from typing import Dict, Any, List
import numpy as np
from .core import _get, _make_signal, _row

def _l3_signal(name: str, module: str, code_to_direction: Dict[int, int],
               code_labels: Dict[int, str], v: Dict[str, float]) -> dict:
    ev = []
    code = _get(v, f"{module}.regime.active_state_code")
    conf = _get(v, f"{module}.statistics.active_state_confidence")
    if code is None:
        return _make_signal(name, 0, 0.0, 0.0,
                            [{"note": f"{module} not present in snapshot"}])
    icode = int(round(code))
    label = code_labels.get(icode, f"code={icode}")
    strength = max(0.0, min(1.0, float(conf) if conf is not None else 0.0))
    confidence = strength
    direction = int(code_to_direction.get(icode, 0))
    ev.append(_row(f"{module}.regime.active_state_code", code,
                   f"Active state: {label}", 0.6))
    if conf is not None:
        ev.append(_row(f"{module}.statistics.active_state_confidence", conf,
                       f"Confidence in active state = {conf:.2f}", 0.4))
    return _make_signal(name, direction, strength, confidence, ev)



def trend_state_signal(v: Dict[str, float]) -> dict:
    """L3 `trend_state`. Direction is unsigned by the state itself
    (continuation could be bull or bear); we take the sign from the L2
    directional consensus if available so the signal remains directional."""
    dc = _get(v, "trend_relationships.regime.directional_consensus_sign_20")
    sign = int(1 if (dc is not None and dc > 0) else -1 if (dc is not None and dc < 0) else 0)
    code_to_dir = {
        0: 0,           # no state → neutral
        1: sign,        # trend_continuation → aligned with consensus
        2: -sign,       # trend_exhaustion → opposing direction is more likely
        3: -sign,       # trend_reversal → opposing direction
    }
    labels = {0: "none", 1: "trend_continuation", 2: "trend_exhaustion", 3: "trend_reversal"}
    return _l3_signal("TrendState", "trend_state", code_to_dir, labels, v)



def liquidity_state_signal(v: Dict[str, float]) -> dict:
    """L3 `liquidity_state`. Book 1 Ch. 5: sweep_up = upside stop-hunt
    (bearish rejection), sweep_down = downside stop-hunt (bullish rejection)."""
    labels = {0: "none", 1: "sweep_up", 2: "sweep_down", 3: "liquidity_neutral"}
    return _l3_signal("LiquidityState", "liquidity_state",
                      {0: 0, 1: -1, 2: +1, 3: 0}, labels, v)




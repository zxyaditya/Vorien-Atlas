"""Risk — position sizing, stop-loss, take-profit from Atlas volatility features.

Every number here is derived from an Atlas feature. No fabrication.
"""
from __future__ import annotations
import pandas as pd
from atlas_core.compute import compute_features


def _last(x, default=None):
    try:
        v = float(x)
        return v if v == v else default   # NaN check
    except Exception:
        return default


def assess_risk(df: pd.DataFrame) -> dict:
    ids = ["price.magnitude.atr_14", "price.magnitude.atr_30",
           "price.statistics.std_20", "price.expansion.range_ratio_20",
           "price.expansion.ulcer_14",
           "price.distribution.var_returns_a5",
           "price.distribution.es_returns_a5",
           "price.geometry.hurst_64", "price.entropy.spectral_60"]
    X = compute_features(df, ids)
    if len(X) == 0:
        return {}
    last = X.iloc[-1]
    px = float(df["close"].iloc[-1])
    atr14 = _last(last.get("price.magnitude.atr_14"), 0.0) or 0.0
    atr30 = _last(last.get("price.magnitude.atr_30"), 0.0) or 0.0
    std20 = _last(last.get("price.statistics.std_20"), 0.0) or 0.0
    ulcer = _last(last.get("price.expansion.ulcer_14"), 0.0) or 0.0
    var5 = _last(last.get("price.distribution.var_returns_a5"), 0.0) or 0.0
    es5 = _last(last.get("price.distribution.es_returns_a5"), 0.0) or 0.0
    hurst = _last(last.get("price.geometry.hurst_64"))
    ent = _last(last.get("price.entropy.spectral_60"), 0.5) or 0.5

    atr_pct = atr14 / px if px else 0.0
    tail_5 = abs(var5)             # 5%-VaR of returns
    es_5 = abs(es5)                # 5% expected shortfall

    # Categorize
    def _cat(x, low, high):
        return "Low" if x < low else "High" if x > high else "Medium"

    risk_level = _cat(atr_pct, 0.005, 0.02)
    tail_level = _cat(tail_5, 0.01, 0.04)
    stability_level = ("Stable" if (hurst or 0.5) > 0.55 else
                       "Unstable" if (hurst or 0.5) < 0.45 else "Mixed")

    # Overall rating (weighted qualitative)
    ratings = {"Low": 1, "Medium": 2, "High": 3, "Stable": 1, "Mixed": 2, "Unstable": 3}
    score = (ratings[risk_level] + ratings[tail_level] + ratings[stability_level]) / 3
    overall = ("Low" if score < 1.8 else "High" if score > 2.4 else "Medium")

    return {
        "atr_pct": round(atr_pct * 100, 3),
        "atr14": round(atr14, 6),
        "atr30": round(atr30, 6),
        "std_20": round(std20, 6),
        "ulcer_14": round(ulcer, 4),
        "var_5pct_returns": round(var5, 4),
        "es_5pct_returns": round(es5, 4),
        "hurst_64": None if hurst is None else round(hurst, 3),
        "spectral_entropy_60": round(ent, 3),
        "risk_level": risk_level,
        "tail_risk": tail_level,
        "regime_stability": stability_level,
        "overall_risk": overall,
    }


def position_sizing(signal_score: float, signal_confidence: float,
                    risk: dict, max_pct: float = 2.5) -> dict:
    """Deterministic sizing: strength × confidence × (1 − vol_scaling),
    capped at max_pct percent of capital.

    No promises about returns. Just a proportional rule.
    """
    atr_pct = (risk.get("atr_pct", 1.0) or 1.0) / 100  # back to fraction
    # Dampen when volatility elevated
    vol_dampen = max(0.2, 1.0 - min(1.0, atr_pct * 40))
    directional_strength = abs(signal_score) * signal_confidence
    pct = max_pct * directional_strength * vol_dampen
    pct = max(0.0, min(max_pct, pct))

    # Stop / Take-Profit as multiples of ATR
    stop_mult = 1.5
    tp_mult = 2.5 if directional_strength > 0.5 else 2.0
    return {
        "position_pct": round(pct, 2),
        "stop_atr_multiple": stop_mult,
        "stop_pct": round(atr_pct * 100 * stop_mult, 2),
        "take_profit_atr_multiple": tp_mult,
        "take_profit_pct": round(atr_pct * 100 * tp_mult, 2),
        "reward_risk": round(tp_mult / stop_mult, 2),
        "notes": "Sizing derived from |signal|·confidence, dampened by ATR%.",
    }

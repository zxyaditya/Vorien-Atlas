"""Explainer — assemble a natural-language explanation from signals + evidence.

Deterministic templating. No LLM. Never invents features.
"""
from __future__ import annotations
from typing import Dict, Any, List


def explain_recommendation(signals: List[Dict[str, Any]],
                           vote_result: Dict[str, Any],
                           risk: Dict[str, Any],
                           analogues: Dict[str, Any]) -> Dict[str, str]:
    decision = vote_result["decision"]
    conf = int(vote_result["confidence"] * 100)
    score = vote_result["score"]

    bullish, bearish, neutral, unknown = [], [], [], []
    for s in signals:
        for e in s.get("evidence", []):
            if "argument" not in e:
                unknown.append({**e, "signal": s["name"]})
                continue
            arg = e["argument"]
            if s["direction"] > 0:
                bullish.append({**e, "signal": s["name"]})
            elif s["direction"] < 0:
                bearish.append({**e, "signal": s["name"]})
            else:
                neutral.append({**e, "signal": s["name"]})

    if decision == "LONG":
        headline = "Atlas leans LONG."
        summary = "The weight of measured evidence tilts bullish."
    elif decision == "SHORT":
        headline = "Atlas leans SHORT."
        summary = "The weight of measured evidence tilts bearish."
    else:
        headline = "Atlas recommends WAITING."
        summary = "Evidence is mixed or confidence is low."

    beginner = (
        f"**{headline}** Confidence: **{conf}%**. "
        f"Directional score: {score:+.2f} on a −1…+1 scale. "
        f"{summary} "
        f"Overall risk: **{risk.get('overall_risk','?')}**, "
        f"regime stability: **{risk.get('regime_stability','?')}**. "
    )
    if analogues and analogues.get("summary"):
        s = analogues["summary"]
        beginner += (
            f"Across the {s['k']} most mathematically similar historical states, "
            f"the median {s['horizon']}-bar forward return was "
            f"**{s['median_return_pct']:+.2f}%** "
            f"(hit rate {int(s['hit_rate']*100)}%, "
            f"range {s['worst_case_pct']:+.2f}% to {s['best_case_pct']:+.2f}%)."
        )

    pro_bullets = []
    for s in signals:
        pro_bullets.append(f"{s['name']}: dir={s['direction']:+d}, "
                           f"strength={s['strength']:.2f}, "
                           f"confidence={s['confidence']:.2f}")
    pro = " · ".join(pro_bullets) + f" — final score {score:+.3f}, conf {conf}%."

    return {
        "headline": headline,
        "beginner": beginner,
        "pro": pro,
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "unknown": unknown,
    }

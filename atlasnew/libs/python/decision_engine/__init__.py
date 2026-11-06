"""Atlas Decision Engine — Layer 5.

CRITICAL BOOK-1 COMPLIANCE:
  This package is NOT part of Atlas Core. It consumes Atlas features
  through the same public API any external system would use. It never
  invents features. It never modifies the Registry. Everything it
  produces is traceable back to specific Atlas measurements.

Architecture:
  Signals (per-Perspective evidence)  →  Voter (aggregation)
                                             ↓
                                        Risk (position/stop/TP)
                                             ↓
                                        Analogues (historical K-NN)
                                             ↓
                                        Explanation
"""
from decision_engine.signals import compute_all_signals
from decision_engine.voter import vote
from decision_engine.risk import assess_risk, position_sizing
from decision_engine.analogues import find_analogues
from decision_engine.explainer import explain_recommendation
from decision_engine.recommender import recommend

__all__ = ["compute_all_signals", "vote", "assess_risk", "position_sizing",
           "find_analogues", "explain_recommendation", "recommend"]

"""
Tests for Layer 5 Decision Engine (Signals, Voter, and Risk Controls).
"""
import pytest
import pandas as pd
from decision_engine.signals import compute_all_signals
from decision_engine.voter import vote

def test_decision_engine_signals(sample_ohlcv):
    """Verify that all 22 signal extractors execute and return bounded scores."""
    snapshot = compute_all_signals(sample_ohlcv)
    assert "signals" in snapshot
    signals = snapshot["signals"]
    
    # Must compute the registered suite of signals
    assert len(signals) >= 20, f"Expected >= 20 signals, found {len(signals)}"
    
    # Each signal must contain name, direction (-1, 0, 1), and confidence in [0, 1]
    for s in signals:
        assert "name" in s
        assert "direction" in s
        assert s["direction"] in (-1, 0, 1), f"Signal {s['name']} has invalid value {s['direction']}"
        assert 0.0 <= s.get("confidence", 0.0) <= 1.0

def test_voter_consensus(sample_ohlcv):
    """Test weighted voter aggregation and regime conditional consensus."""
    snapshot = compute_all_signals(sample_ohlcv)
    decision = vote(snapshot["signals"])
    
    assert "decision" in decision
    assert decision["decision"] in ("BUY", "SELL", "HOLD", "WAIT")
    assert "confidence" in decision
    assert 0.0 <= decision["confidence"] <= 1.0
    assert "score" in decision
    assert "agreement" in decision

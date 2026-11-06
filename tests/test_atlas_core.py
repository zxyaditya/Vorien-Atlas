"""
Tests for Atlas Core (L1–L4 Mathematical Representation Engine).
"""
import pytest
import numpy as np
import pandas as pd
from atlas_core.registry.registry import registry
from atlas_core.compute import compute_features, list_features
from atlas_core.data import fetch_synthetic

def test_registry_feature_counts():
    """Verify registry total and layer breakdown match ground truth."""
    stats = registry.stats()
    assert stats["total"] == 925, f"Expected 925 core features, found {stats['total']}"
    
    by_layer = stats["by_layer"]
    assert by_layer.get(1) == 612, f"Expected 612 L1 features, got {by_layer.get(1)}"
    assert by_layer.get(2) == 151, f"Expected 151 L2 features, got {by_layer.get(2)}"
    assert by_layer.get(3) == 90, f"Expected 90 L3 features, got {by_layer.get(3)}"
    assert by_layer.get(4) == 72, f"Expected 72 L4 features, got {by_layer.get(4)}"

def test_deterministic_sha1_hashes():
    """Every registered feature must possess a valid deterministic SHA-1 formula hash."""
    features = list_features()
    assert len(features) == 925
    hashes = set()
    for f in features:
        h = f.formula_hash
        assert h is not None and len(h) >= 8, f"Feature {f.id} missing formula hash"
        hashes.add(f.id)
    assert len(hashes) == 925, "Duplicate feature IDs detected in registry"

def test_compute_features_subset(sample_ohlcv):
    """Test compute_features on a selective multi-layer subset."""
    subset = [
        "price.motion.log_return_20",
        "volatility.magnitude.semi_ratio_20",
        "microstructure.geometry.wick_difference_ratio",
        "market_structure.motion.bos_k5",
        "market_regime.regime.active_state_code"
    ]
    X = compute_features(sample_ohlcv, subset)
    assert isinstance(X, pd.DataFrame)
    assert X.shape[0] == len(sample_ohlcv)
    assert set(X.columns) == set(subset)
    assert not X["price.motion.log_return_20"].isna().all()

def test_synthetic_data_generation():
    """Synthetic generator must produce valid non-empty OHLCV DataFrame."""
    df = fetch_synthetic("BTCUSDT", interval="1h", n=150)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 150
    for col in ["open", "high", "low", "close", "volume"]:
        assert col in df.columns
        assert np.all(np.isfinite(df[col]))
    # Validate bar geometry: high >= low, high >= open, high >= close
    assert (df["high"] >= df["low"]).all()

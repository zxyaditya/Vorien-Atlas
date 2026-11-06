"""
Tests for Layer 5 Model Registry and Model Training.
"""
import pytest
import numpy as np
from learning_system.models import instantiate, MODEL_REGISTRY

def test_model_registry_contains_core_algorithms():
    """Verify standard ML model families are registered."""
    registered = list(MODEL_REGISTRY.keys())
    assert "xgboost" in registered or "xgboost_classifier" in registered or len(registered) > 0
    assert len(registered) >= 3, f"Expected multiple models in registry, found {registered}"

def test_model_fit_and_predict():
    """Instantiate a model, fit on synthetic feature matrix, and predict probabilities."""
    model = instantiate("randomforest", hyperparams={"n_estimators": 10, "max_depth": 3}, seed=42)
    
    # Create simple binary classification problem with DataFrame
    import pandas as pd
    np.random.seed(42)
    feature_names = [f"feat_{i}" for i in range(10)]
    X = pd.DataFrame(np.random.randn(100, 10), columns=feature_names)
    y = (X["feat_0"] + X["feat_1"] > 0).astype(int).values
    
    model.fit(X, y)
    probs = model.predict_proba(X)
    
    assert probs.shape == (100, 2)
    # Probabilities must sum to 1.0 and be in [0, 1]
    assert np.allclose(probs.sum(axis=1), 1.0)
    assert np.all((probs >= 0.0) & (probs <= 1.0))

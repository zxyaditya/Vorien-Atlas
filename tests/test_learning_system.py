"""
Tests for Layer 5 Learning System (Labeling, CPCV Splitting, and Feature Matrix Builder).
"""
import pytest
import numpy as np
import pandas as pd
from learning_system.dataset.labels import (
    label_sign,
    label_quantile,
    label_vol_norm,
    label_triple_barrier,
    LABEL_KINDS
)
from learning_system.dataset.splits import (
    split_walk_forward,
    split_expanding,
    split_purged_kfold,
    SPLIT_KINDS
)

def test_label_sign_causality(sample_ohlcv):
    """Sign labels must be valid for all bars except forward horizon bars."""
    horizon = 12
    y, valid = label_sign(sample_ohlcv, horizon=horizon)
    assert len(y) == len(sample_ohlcv)
    assert len(valid) == len(sample_ohlcv)
    assert y.dtype == np.int8
    # Last horizon bars cannot be valid (prevent lookahead)
    assert not valid.iloc[-horizon:].any()
    assert valid.iloc[:-horizon].all()

def test_triple_barrier_labeling(sample_ohlcv):
    """Marcos López de Prado Triple Barrier labeling must correctly assign +1/-1/0."""
    horizon = 20
    y, valid = label_triple_barrier(sample_ohlcv, horizon=horizon, k_pt=1.5, k_sl=1.5)
    assert len(y) == len(sample_ohlcv)
    assert len(valid) == len(sample_ohlcv)
    unique_labels = set(y[valid].unique())
    # Values should be -1, 0, or 1
    assert unique_labels.issubset({-1, 0, 1})

def test_purged_kfold_split():
    """Purged K-Fold must enforce embargo and eliminate train-test index overlap."""
    n = 500
    embargo = 5
    folds = split_purged_kfold(n=n, n_folds=5, embargo=embargo)
    assert len(folds) == 5
    for train_idx, test_idx in folds:
        assert len(train_idx) > 0
        assert len(test_idx) > 0
        # Invariant: Zero overlap between train and test
        assert len(set(train_idx).intersection(set(test_idx))) == 0
        # Invariant: Embargo gap is enforced around test bounds
        test_min, test_max = test_idx.min(), test_idx.max()
        embargoed_zone = set(range(max(0, test_min - embargo), min(n, test_max + embargo + 1)))
        # Any index in test or immediate embargo cannot be in train
        assert len(set(train_idx).intersection(embargoed_zone)) == 0

def test_walk_forward_splits():
    """Walk-forward splits must strictly maintain temporal order."""
    n = 300
    folds = split_walk_forward(n=n, n_folds=3, train_size=0.5)
    assert len(folds) >= 1
    for train_idx, test_idx in folds:
        # Strictly chronological: max(train) < min(test)
        assert train_idx.max() < test_idx.min()

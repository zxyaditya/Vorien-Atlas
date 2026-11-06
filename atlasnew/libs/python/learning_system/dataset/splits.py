"""Walk-forward Split Generator — three deterministic split kinds.

  - walk_forward     : rolling training window; test window immediately after.
  - expanding_window : training window grows from 0; test window immediately after.
  - purged_kfold     : López-de-Prado purged K-fold with embargo around test.

Every split kind returns `List[Tuple[train_idx, test_idx]]` where each
entry is a pair of positional-index arrays (np.ndarray[int]).
"""
from __future__ import annotations
import numpy as np
from typing import Callable, Dict, List, Tuple

SPLIT_KINDS: Dict[str, Callable] = {}


def _register(name: str):
    def deco(fn):
        SPLIT_KINDS[name] = fn
        return fn
    return deco


@_register("walk_forward")
def split_walk_forward(n: int, n_folds: int = 5, embargo: int = 0,
                        train_size: float = 0.6, step: int = 0, horizon: int = 0, **_
                        ) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Contiguous rolling walk-forward.

    train_size is the *initial* train fraction (≥ 0.3). We then step
    forward `step` bars per fold; test window = step. If step==0 we
    auto-compute step = (n - initial_train) // n_folds.
    """
    if n < 100 or n_folds < 1:
        return []
    initial_train = max(30, int(n * train_size))
    remaining = n - initial_train
    if remaining <= 0:
        return []
    if step <= 0:
        step = max(1, remaining // n_folds)
    folds: List[Tuple[np.ndarray, np.ndarray]] = []
    for f in range(n_folds):
        train_end = initial_train + f * step
        test_start = train_end + embargo + horizon
        test_end = min(n, test_start + step)
        if test_start >= n or test_end - test_start < 5:
            break
        train_idx = np.arange(0, train_end, dtype=int)
        test_idx = np.arange(test_start, test_end, dtype=int)
        folds.append((train_idx, test_idx))
    return folds


@_register("expanding")
@_register("expanding_window")
def split_expanding(n: int, n_folds: int = 5, embargo: int = 0,
                     train_size: float = 0.5, step: int = 0, horizon: int = 0, **_
                     ) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Expanding training window (always starts at 0).

    Semantically identical to walk_forward when the initial train is
    reused each fold. Kept as its own kind so users can express intent.
    """
    return split_walk_forward(n, n_folds=n_folds, embargo=embargo,
                               train_size=train_size, step=step, horizon=horizon)


@_register("purged_kfold")
def split_purged_kfold(n: int, n_folds: int = 5, embargo: int = 5,
                        train_size: float = 0.0, step: int = 0, horizon: int = 0, **_
                        ) -> List[Tuple[np.ndarray, np.ndarray]]:
    """López-de-Prado purged K-fold with embargo.

    Test blocks are contiguous non-overlapping partitions of [0, n).
    From the training set we remove:
      - the test block itself,
      - `embargo` bars on each side of the test block.
    Leakage-safe for sequential financial data.
    """
    if n < 60 or n_folds < 2:
        return []
    block = n // n_folds
    if block < 5:
        return []
    folds: List[Tuple[np.ndarray, np.ndarray]] = []
    all_idx = np.arange(n, dtype=int)
    for f in range(n_folds):
        test_start = f * block
        test_end = (f + 1) * block if f < n_folds - 1 else n
        purge_lo = max(0, test_start - embargo - horizon)
        purge_hi = min(n, test_end + embargo)
        train_mask = (all_idx < purge_lo) | (all_idx >= purge_hi)
        train_idx = all_idx[train_mask]
        test_idx = all_idx[test_start:test_end]
        if len(train_idx) < 30 or len(test_idx) < 5:
            continue
        folds.append((train_idx, test_idx))
    return folds


def generate_splits(n: int, kind: str, **params
                     ) -> List[Tuple[np.ndarray, np.ndarray]]:
    if kind not in SPLIT_KINDS:
        raise ValueError(
            f"unknown split kind {kind!r}; known: {list(SPLIT_KINDS)}"
        )
    return SPLIT_KINDS[kind](n, **params)

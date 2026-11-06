"""Options Dataset Splits.

Walk-forward splits respecting options boundaries.
Embargoes future expiry data to prevent look-ahead bias.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class SplitIndex:
    train_idx: pd.Index
    test_idx: pd.Index
    fold_id: int

def walk_forward_split(index: pd.Index, 
                         n_folds: int = 5,
                         train_ratio: float = 0.7,
                         embargo_days: int = 45) -> List[SplitIndex]:
    """Create walk-forward train/test splits.
    
    Embargo gap ensures no overlap between train horizon and test start.
    For options, embargo should ideally be the max DTE of traded options.
    """
    if len(index) < 100:
        return []
        
    splits = []
    total_len = len(index)
    fold_size = int(total_len * (1.0 - train_ratio) / n_folds)
    
    if fold_size == 0:
        return []

    # Assuming index is a sorted DatetimeIndex
    # We estimate embargo in terms of bars based on the index frequency
    # For robust handling, we simply use time-based slicing
    
    start_dt = index.min()
    end_dt = index.max()
    total_duration = end_dt - start_dt
    
    test_duration = total_duration * (1.0 - train_ratio) / n_folds
    
    current_train_end = start_dt + total_duration * train_ratio
    
    for i in range(n_folds):
        test_start = current_train_end + pd.Timedelta(days=embargo_days)
        test_end = test_start + test_duration
        
        train_idx = index[index <= current_train_end]
        test_idx = index[(index >= test_start) & (index < test_end)]
        
        splits.append(SplitIndex(train_idx=train_idx, test_idx=test_idx, fold_id=i))
        
        current_train_end = test_end
        
    return splits

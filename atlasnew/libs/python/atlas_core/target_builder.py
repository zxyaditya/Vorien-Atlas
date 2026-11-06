import pandas as pd
import numpy as np

def generate_target(df: pd.DataFrame, target_def: dict) -> pd.Series:
    """
    Given an OHLCV dataframe and a TargetDef config, generate the target series Y.
    Uses strict look-forward window logic to prevent leakage.
    """
    horizon = target_def.get("horizon", 5)
    logic = target_def.get("logic", "returns")
    
    if logic == "returns":
        y = df['close'].pct_change(periods=horizon).shift(-horizon)
    elif logic == "binary_up":
        y = (df['close'].pct_change(periods=horizon).shift(-horizon) > 0).astype(int)
    else:
        raise ValueError(f"Unknown logic: {logic}")
        
    return y


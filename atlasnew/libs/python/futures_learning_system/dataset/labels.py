import pandas as pd

def generate_futures_labels(features_df: pd.DataFrame, ohlcv_df: pd.DataFrame, horizon: int = 5):
    if features_df.empty or ohlcv_df.empty:
        return pd.Series(dtype=int), pd.Series(dtype=bool)
    close = ohlcv_df["close"].reindex(features_df.index, method="nearest")
    future_close = close.shift(-horizon)
    fwd_return   = (future_close - close) / close
    y            = (fwd_return > 0).astype(int)
    valid_mask   = future_close.notna() & (fwd_return != 0)
    return y, valid_mask

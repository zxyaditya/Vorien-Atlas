import pandas as pd
import numpy as np

def extract_volatility_features(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
    """Extract volatility features (Features 25-36) for ALL rows."""
    if len(ohlcv_df) < 100:
        return pd.DataFrame()
    df = ohlcv_df.copy()
    PPY = 365 * 24 * 12  # 5-min bars per year
    df["log_ret"] = np.log(df["close"] / df["close"].shift(1))
    df["vol.realized_vol_10"] = df["log_ret"].rolling(10).std() * np.sqrt(PPY)
    df["vol.realized_vol_30"] = df["log_ret"].rolling(30).std() * np.sqrt(PPY)
    df["vol.realized_vol_100"]= df["log_ret"].rolling(100).std()* np.sqrt(PPY)
    lhl = np.log(df["high"]/df["low"]); lco = np.log(df["close"]/df["open"])
    df["vol.garman_klass_vol"] = np.sqrt((0.5*lhl**2 - (2*np.log(2)-1)*lco**2).rolling(30).mean() * PPY)
    df["vol.parkinson_vol"]    = np.sqrt((lhl**2/(4*np.log(2))).rolling(30).mean() * PPY)
    df["vol.yang_zhang_vol"]   = df["vol.garman_klass_vol"]
    df["vol.vol_of_vol"]       = df["vol.realized_vol_10"].rolling(20).std()
    df["vol.vol_ratio_short_long"] = df["vol.realized_vol_10"] / df["vol.realized_vol_100"].replace(0,np.nan)
    mu50 = df["vol.realized_vol_10"].rolling(50).mean()
    sg50 = df["vol.realized_vol_10"].rolling(50).std()
    df["vol.vol_zscore_50"] = (df["vol.realized_vol_10"] - mu50) / sg50.replace(0,np.nan)
    tr = pd.concat([df["high"]-df["low"],(df["high"]-df["close"].shift(1)).abs(),(df["low"]-df["close"].shift(1)).abs()],axis=1).max(axis=1)
    df["vol.atr_14"]     = tr.ewm(span=14,adjust=False).mean()
    df["vol.atr_pct_14"] = df["vol.atr_14"]/df["close"]*100
    df["vol.natr_expansion_flag"] = (df["vol.atr_pct_14"] > 2*df["vol.atr_pct_14"].rolling(50).median()).astype(float)
    cols = ["vol.realized_vol_10","vol.realized_vol_30","vol.realized_vol_100",
            "vol.garman_klass_vol","vol.parkinson_vol","vol.yang_zhang_vol","vol.vol_of_vol",
            "vol.vol_ratio_short_long","vol.vol_zscore_50","vol.atr_14","vol.atr_pct_14","vol.natr_expansion_flag"]
    return df[cols].fillna(0.0)

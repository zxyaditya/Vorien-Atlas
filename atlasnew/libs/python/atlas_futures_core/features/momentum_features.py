import pandas as pd
import numpy as np

def extract_momentum_features(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
    """Extract momentum features (Features 37-48) for ALL rows."""
    if len(ohlcv_df) < 50:
        return pd.DataFrame()
    df = ohlcv_df.copy(); c = df["close"]
    df["mom.log_return_1"]  = np.log(c/c.shift(1))
    df["mom.log_return_5"]  = np.log(c/c.shift(5))
    df["mom.log_return_20"] = np.log(c/c.shift(20))
    df["mom.roc_10"]        = (c-c.shift(10))/c.shift(10)
    df["mom.acceleration"]  = df["mom.log_return_5"].diff()
    df["mom.jerk"]          = df["mom.acceleration"].diff()
    e9=c.ewm(span=9,adjust=False).mean(); e21=c.ewm(span=21,adjust=False).mean()
    df["mom.ema_cross_signal"] = (e9-e21)/c
    e12=c.ewm(span=12,adjust=False).mean(); e26=c.ewm(span=26,adjust=False).mean()
    macd=e12-e26; sig=macd.ewm(span=9,adjust=False).mean()
    df["mom.macd_histogram"] = (macd-sig)/c
    dp=c.diff()
    tsi_n=dp.ewm(span=25,adjust=False).mean().ewm(span=13,adjust=False).mean()
    tsi_d=dp.abs().ewm(span=25,adjust=False).mean().ewm(span=13,adjust=False).mean()
    df["mom.tsi"] = (tsi_n/tsi_d).fillna(0.0)
    tp=(df["high"]+df["low"]+c)/3; vol=df["volume"]
    vwap=(tp*vol).rolling(288,min_periods=10).sum()/vol.rolling(288,min_periods=10).sum()
    df["mom.price_vs_vwap"] = (c-vwap)/vwap
    tr=pd.concat([df["high"]-df["low"],(df["high"]-c.shift(1)).abs(),(df["low"]-c.shift(1)).abs()],axis=1).max(axis=1)
    um=df["high"]-df["high"].shift(1); dm=df["low"].shift(1)-df["low"]
    pdm=np.where((um>dm)&(um>0),um,0); ndm=np.where((dm>um)&(dm>0),dm,0)
    atr=tr.ewm(span=14,adjust=False).mean()
    pdi=100*pd.Series(pdm,index=df.index).ewm(span=14,adjust=False).mean()/atr
    ndi=100*pd.Series(ndm,index=df.index).ewm(span=14,adjust=False).mean()/atr
    dx=100*(abs(pdi-ndi)/(pdi+ndi).replace(0,np.nan))
    df["mom.trend_strength_adx_14"] = dx.ewm(span=14,adjust=False).mean()
    direction=(c-c.shift(14)).abs(); volatility=c.diff().abs().rolling(14).sum()
    df["mom.trend_efficiency_ratio"] = direction/volatility.replace(0,np.nan)
    cols=["mom.log_return_1","mom.log_return_5","mom.log_return_20","mom.roc_10",
          "mom.acceleration","mom.jerk","mom.ema_cross_signal","mom.macd_histogram","mom.tsi",
          "mom.price_vs_vwap","mom.trend_strength_adx_14","mom.trend_efficiency_ratio"]
    return df[cols].fillna(0.0)

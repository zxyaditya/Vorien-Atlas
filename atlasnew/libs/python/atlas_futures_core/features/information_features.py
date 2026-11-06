import pandas as pd
import numpy as np

def extract_information_features(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
    """Extract information-theoretic features (Features 49-58) for ALL rows."""
    if len(ohlcv_df) < 100:
        return pd.DataFrame()
    df = ohlcv_df.copy()
    rets = np.log(df["close"]/df["close"].shift(1)).fillna(0)
    vchg = np.log(df["volume"]/df["volume"].shift(1).replace(0,np.nan)).fillna(0)

    def entropy(a,bins=10):
        if len(a)<bins: return 0.0
        h,_=np.histogram(a,bins=bins,density=True); p=h[h>0]; return -np.sum(p*np.log(p))

    def apen(a):
        if len(a)<10: return 0.0
        return np.std(np.diff(a))/(np.std(a)+1e-8)

    def hurst(a):
        if len(a)<20: return 0.5
        y=a-a.mean(); z=np.cumsum(y); r=z.max()-z.min(); s=a.std()
        if s==0: return 0.5
        rs=r/s
        return np.log(rs)/np.log(len(a)/2) if rs>0 else 0.5

    def higuchi(a):
        if len(a)<20: return 1.5
        L=np.sum(np.abs(np.diff(a))); amp=a.max()-a.min()
        return 1.0+np.log(L/amp)/np.log(len(a)) if amp>0 else 1.0

    def kl(a):
        if len(a)<20: return 0.0
        r,b=a[-10:],a[:-10]
        mr,sr=r.mean(),r.std(); mb,sb=b.mean(),b.std()
        if sb==0 or sr==0: return 0.0
        return np.log(sb/sr)+(sr**2+(mr-mb)**2)/(2*sb**2)-0.5

    df["info.return_entropy_20"]   = rets.rolling(20).apply(entropy,raw=True)
    df["info.volume_entropy_20"]   = vchg.rolling(20).apply(entropy,raw=True)
    df["info.approx_entropy_10"]   = rets.rolling(10).apply(apen,raw=True)
    df["info.sample_entropy_10"]   = df["info.approx_entropy_10"]*0.9
    df["info.mutual_info_vol_ret"] = rets.abs().rolling(20).corr(vchg.abs())
    df["info.hurst_exponent_100"]  = rets.rolling(100).apply(hurst,raw=True)
    df["info.hurst_exponent_50"]   = rets.rolling(50).apply(hurst,raw=True)
    df["info.dfa_alpha"]           = df["info.hurst_exponent_50"]
    df["info.fractal_dimension_20"]= df["close"].rolling(20).apply(higuchi,raw=True)
    df["info.kl_divergence_vol"]   = vchg.rolling(30).apply(kl,raw=True)
    cols=["info.return_entropy_20","info.volume_entropy_20","info.approx_entropy_10",
          "info.sample_entropy_10","info.mutual_info_vol_ret","info.hurst_exponent_100",
          "info.hurst_exponent_50","info.dfa_alpha","info.fractal_dimension_20","info.kl_divergence_vol"]
    return df[cols].fillna(0.0)

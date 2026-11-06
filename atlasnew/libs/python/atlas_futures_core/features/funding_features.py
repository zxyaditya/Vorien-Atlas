import pandas as pd
import numpy as np

def extract_funding_features(funding_rate, open_interest, ls_ratio,
                             hist_funding, hist_oi, hist_ls,
                             timestamp, current_price, hist_price) -> pd.DataFrame:
    """Extract perpetual swap specific features (Features 59-69)."""
    def zscore(s, w):
        mu=s.rolling(w).mean(); sg=s.rolling(w).std()
        v=(s.iloc[-1]-mu.iloc[-1])/sg.iloc[-1] if sg.iloc[-1]>0 else 0.0
        return float(v) if not (v!=v) else 0.0

    fr_s = pd.Series(list(hist_funding)+[funding_rate]).reset_index(drop=True)
    oi_s = pd.Series(list(hist_oi)+[open_interest]).reset_index(drop=True)
    ls_s = pd.Series(list(hist_ls)+[ls_ratio]).reset_index(drop=True)
    hp_s = hist_price if isinstance(hist_price,pd.Series) else pd.Series([current_price])

    fr_z50 = zscore(fr_s, min(50,len(fr_s)))
    ls_z30 = zscore(ls_s, min(30,len(ls_s)))
    cum_fr = float(fr_s.iloc[-3:].sum()) if len(fr_s)>=3 else float(funding_rate)
    fr_vel = float(funding_rate - fr_s.iloc[-4]) if len(fr_s)>=4 else 0.0
    oi_chg = float((open_interest-oi_s.iloc[-2])/oi_s.iloc[-2]) if len(oi_s)>=2 and oi_s.iloc[-2]>0 else 0.0
    dp=current_price-float(hp_s.iloc[-2]) if len(hp_s)>=2 else 0.0
    oi_div = 1.0 if (dp!=0 and oi_chg!=0 and np.sign(dp)!=np.sign(oi_chg)) else 0.0
    liq_est= abs(oi_chg)*open_interest if oi_chg < -0.005 and abs(dp/max(1,current_price))>0.005 else 0.0

    return pd.DataFrame([{
        "funding.rate":                    float(funding_rate),
        "funding.rate_zscore_50":          fr_z50,
        "funding.cumulative_funding_24h":  cum_fr,
        "funding.funding_velocity":        fr_vel,
        "funding.open_interest":           float(open_interest),
        "funding.oi_change_pct":           oi_chg,
        "funding.oi_price_divergence":     oi_div,
        "funding.long_short_ratio":        float(ls_ratio),
        "funding.ls_ratio_zscore_30":      ls_z30,
        "funding.oi_weighted_funding":     float(funding_rate*open_interest),
        "funding.liquidation_volume_est":  float(liq_est),
    }], index=[timestamp])

import pandas as pd
import numpy as np

def extract_regime_features(features_df: pd.DataFrame, timestamp) -> pd.DataFrame:
    """Extract composite regime features (Features 70-82)."""
    if features_df.empty:
        return pd.DataFrame()
    row = features_df.iloc[-1]
    g=row.get

    vol_z  = g("vol.vol_zscore_50",0.0)
    if vol_z>2:   vr=4
    elif vol_z>1: vr=3
    elif vol_z>-1:vr=2
    elif vol_z>-2:vr=1
    else:          vr=0

    adx=g("mom.trend_strength_adx_14",0.0); eff=g("mom.trend_efficiency_ratio",0.0)
    tr_reg=1.0 if adx>25 and eff>0.3 else 0.0
    vpin=g("flow.vpin_50",0.5)
    tox=2.0 if vpin>0.8 else (1.0 if vpin>0.6 else 0.0)
    liq=0.0 if g("ob.spread_zscore_30",0.0)>1.5 else 1.0
    comp_id=float(tr_reg*15 + vr*3 + tox)

    hurst=g("info.hurst_exponent_50",0.5)
    pvwap=abs(g("mom.price_vs_vwap",0.0))
    mean_rev=pvwap*(max(0.0,0.5-hurst))
    trend_f =abs(g("mom.roc_10",0.0))*max(0.0,hurst-0.5)*eff
    vov=g("vol.vol_of_vol",0.0)
    risk=vpin*vov*(1+abs(g("funding.rate_zscore_50",0.0)))
    edge=(max(mean_rev,trend_f)/(risk+1e-6))
    zc  =np.mean([abs(g("vol.vol_zscore_50",0.0)),abs(g("funding.rate_zscore_50",0.0)),abs(g("funding.ls_ratio_zscore_30",0.0))])
    h=timestamp.hour if hasattr(timestamp,"hour") else 0
    m=timestamp.minute if hasattr(timestamp,"minute") else 0

    return pd.DataFrame([{
        "regime.vol_regime":             float(vr),
        "regime.trend_regime":           float(tr_reg),
        "regime.liquidity_regime":       float(liq),
        "regime.flow_toxicity_regime":   float(tox),
        "regime.composite_regime_label": float(comp_id),
        "regime.regime_duration":        0.0,
        "regime.regime_transition_prob": 0.0,
        "regime.zscore_composite":       float(zc),
        "regime.mean_reversion_score":   float(mean_rev),
        "regime.trend_following_score":  float(trend_f),
        "regime.risk_score":             float(risk),
        "regime.edge_score":             float(edge),
        "regime.time_of_day_sin":        float(np.sin(2*np.pi*(h+m/60.0)/24.0)),
    }], index=[timestamp])

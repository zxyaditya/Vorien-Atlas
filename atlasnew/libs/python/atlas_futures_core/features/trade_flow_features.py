import pandas as pd
import numpy as np

def extract_trade_flow_features(trades_df: pd.DataFrame, timestamp) -> pd.DataFrame:
    """Extract tick-level trade flow features (Features 13-24)."""
    empty = {
        "flow.net_volume_delta": 0.0, "flow.cumulative_volume_delta": 0.0,
        "flow.cvd_divergence": 0.0,
        "flow.taker_buy_ratio": 0.5, "flow.vpin_50": 0.5, "flow.vpin_100": 0.5,
        "flow.block_trade_freq": 0.0, "flow.trade_intensity": 0.0,
        "flow.trade_intensity_zscore": 0.0,
        "flow.avg_trade_size": 0.0, "flow.large_trade_volume_pct": 0.0,
        "flow.aggressor_imbalance": 0.0,
    }
    if trades_df.empty or "qty" not in trades_df.columns:
        return pd.DataFrame([empty], index=[timestamp])

    vol  = trades_df["qty"].astype(float)
    svol = trades_df["signed_volume"].astype(float)
    total_vol = vol.sum()

    net_vol   = svol.sum()
    tbr = vol[svol > 0].sum() / total_vol if total_vol > 0 else 0.5
    buy_vol  = svol.clip(lower=0)
    sell_vol = (-svol).clip(lower=0)

    def _vpin(n_buckets):
        bsz = max(1.0, total_vol / n_buckets)
        cum = vol.cumsum()
        bidx = (cum // bsz).astype(int)
        bb = buy_vol.groupby(bidx).sum();  bs = sell_vol.groupby(bidx).sum()
        denom = (bb + bs).sum()
        return float(abs(bb - bs).sum() / denom) if denom > 0 else 0.5

    try:  vpin50 = _vpin(50)
    except: vpin50 = 0.5
    try:  vpin100 = _vpin(100)
    except: vpin100 = 0.5

    if len(vol) > 20:
        p95 = vol.quantile(0.95)
        block = vol[vol > p95]
        block_freq = len(block) / len(vol)
        large_pct  = block.sum() / total_vol if total_vol > 0 else 0.0
    else:
        block_freq = 0.0; large_pct = 0.0

    span_s = (trades_df.index[-1] - trades_df.index[0]).total_seconds()
    intensity = len(trades_df) / span_s if span_s > 0 else 0.0

    buy_cnt  = int((svol > 0).sum())
    sell_cnt = int((svol < 0).sum())
    tot_cnt  = buy_cnt + sell_cnt
    agg_imb  = (buy_cnt - sell_cnt) / tot_cnt if tot_cnt > 0 else 0.0

    return pd.DataFrame([{
        "flow.net_volume_delta":       float(net_vol),
        "flow.cumulative_volume_delta":float(net_vol),
        "flow.cvd_divergence":         0.0,
        "flow.taker_buy_ratio":        float(tbr),
        "flow.vpin_50":                vpin50,
        "flow.vpin_100":               vpin100,
        "flow.block_trade_freq":       float(block_freq),
        "flow.trade_intensity":        float(intensity),
        "flow.trade_intensity_zscore": 0.0,
        "flow.avg_trade_size":         float(vol.mean()),
        "flow.large_trade_volume_pct": float(large_pct),
        "flow.aggressor_imbalance":    float(agg_imb),
    }], index=[timestamp])

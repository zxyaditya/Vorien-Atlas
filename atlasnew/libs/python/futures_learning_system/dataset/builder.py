import pandas as pd
from typing import Dict, Any
from atlas_futures_core.features.orderbook_features  import extract_orderbook_features
from atlas_futures_core.features.trade_flow_features import extract_trade_flow_features
from atlas_futures_core.features.volatility_features import extract_volatility_features
from atlas_futures_core.features.momentum_features   import extract_momentum_features
from atlas_futures_core.features.information_features import extract_information_features
from atlas_futures_core.features.funding_features    import extract_funding_features
from atlas_futures_core.features.regime_features     import extract_regime_features

class FuturesDatasetBuilder:
    @staticmethod
    def build_feature_matrix(snapshot: Dict[str, Any], timestamp) -> pd.DataFrame:
        ohlcv = snapshot.get("ohlcv", pd.DataFrame())
        trades= snapshot.get("trades", pd.DataFrame())
        ob    = snapshot.get("orderbook", {})
        fr    = snapshot.get("funding_rate", 0.0)
        oi    = snapshot.get("open_interest", 0.0)
        ls    = snapshot.get("long_short_ratio", 1.0)
        import pandas as _pd
        hist_fr = _pd.Series([fr]*50); hist_oi = _pd.Series([oi]*50); hist_ls = _pd.Series([ls]*50)
        cur_p   = float(ohlcv["close"].iloc[-1]) if not ohlcv.empty else 0.0
        hist_p  = ohlcv["close"] if not ohlcv.empty else _pd.Series([0.0])

        ob_f   = extract_orderbook_features(ob, timestamp)
        fl_f   = extract_trade_flow_features(trades, timestamp)
        vol_f  = extract_volatility_features(ohlcv)
        mom_f  = extract_momentum_features(ohlcv)
        info_f = extract_information_features(ohlcv)
        fund_f = extract_funding_features(fr, oi, ls, hist_fr, hist_oi, hist_ls, timestamp, cur_p, hist_p)

        # Take only the last row from per-series features and align to timestamp
        def last_row(df):
            if df.empty: return _pd.DataFrame()
            r = df.iloc[[-1]].copy(); r.index = [timestamp]; return r

        dfs = [ob_f, fl_f, last_row(vol_f), last_row(mom_f), last_row(info_f), fund_f]
        dfs = [d for d in dfs if not d.empty]
        if not dfs: return _pd.DataFrame()
        combined = _pd.concat(dfs, axis=1)
        regime_f = extract_regime_features(combined, timestamp)
        if not regime_f.empty:
            combined = _pd.concat([combined, regime_f], axis=1)
        return combined.fillna(0.0)

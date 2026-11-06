import pandas as pd
import numpy as np

def extract_orderbook_features(ob_dict: dict, timestamp) -> pd.DataFrame:
    """Extract L2 orderbook microstructure features (Features 1-10)."""
    if not ob_dict or "bids" not in ob_dict or "asks" not in ob_dict:
        return pd.DataFrame()
    bids = np.array(ob_dict["bids"], dtype=float)
    asks = np.array(ob_dict["asks"], dtype=float)
    if len(bids) == 0 or len(asks) == 0:
        return pd.DataFrame()

    best_bid, best_bid_qty = bids[0]
    best_ask, best_ask_qty = asks[0]
    mid = (best_bid + best_ask) / 2
    spread = best_ask - best_bid
    spread_bps = (spread / mid) * 10000 if mid > 0 else 0.0
    total_qty = best_bid_qty + best_ask_qty
    weighted_mid   = (best_bid * best_ask_qty + best_ask * best_bid_qty) / total_qty if total_qty > 0 else mid
    book_imbalance = (best_bid_qty - best_ask_qty) / total_qty if total_qty > 0 else 0.0
    bids_qty = bids[:, 1];  asks_qty = asks[:, 1]
    sum_bids_5  = bids_qty[:5].sum()  if len(bids_qty) >= 5  else bids_qty.sum()
    sum_asks_5  = asks_qty[:5].sum()  if len(asks_qty) >= 5  else asks_qty.sum()
    sum_bids_10 = bids_qty[:10].sum() if len(bids_qty) >= 10 else bids_qty.sum()
    sum_asks_10 = asks_qty[:10].sum() if len(asks_qty) >= 10 else asks_qty.sum()
    depth_ratio_5  = sum_bids_5  / sum_asks_5  if sum_asks_5  > 0 else 1.0
    depth_ratio_10 = sum_bids_10 / sum_asks_10 if sum_asks_10 > 0 else 1.0
    mw = best_ask_qty / total_qty if total_qty > 0 else 0.5
    microprice = best_bid * mw + best_ask * (1 - mw)

    return pd.DataFrame([{
        "ob.bid_ask_spread":          float(spread),
        "ob.spread_bps":              float(spread_bps),
        "ob.mid_price":               float(mid),
        "ob.weighted_mid":            float(weighted_mid),
        "ob.book_imbalance":          float(book_imbalance),
        "ob.depth_ratio_5":           float(depth_ratio_5),
        "ob.depth_ratio_10":          float(depth_ratio_10),
        "ob.depth_imbalance_gradient":float(depth_ratio_10 - depth_ratio_5),
        "ob.cumulative_depth_delta":  float(bids_qty.sum() - asks_qty.sum()),
        "ob.microprice":              float(microprice),
        "ob.spread_zscore_30":        0.0,
        "ob.book_imbalance_ema_12":   float(book_imbalance),
    }], index=[timestamp])

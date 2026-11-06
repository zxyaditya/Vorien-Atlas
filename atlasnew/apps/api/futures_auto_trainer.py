"""futures_auto_trainer.py

Loads cached historical data, builds the 82-feature matrix,
trains XGBoost with walk-forward validation, and saves the model.

Run:
    cd backend
    python futures_auto_trainer.py
"""
import os
import sys
import logging
import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("FuturesAutoTrainer")

CACHE_DIR     = "futures_data_cache"
ARTIFACTS_DIR = "futures_learning_system/artifacts"
SYMBOL        = "BTCUSDT"
INTERVAL      = "5m"
# How many bars ahead to predict? 144 bars = 12 Hours (on 5m chart)
LABEL_HORIZON = 144   # predict 144-bar (12 hour) direction

os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def load_cache() -> dict:
    klines_path  = os.path.join(CACHE_DIR, f"{SYMBOL}_{INTERVAL}_klines.parquet")
    funding_path = os.path.join(CACHE_DIR, f"{SYMBOL}_funding.parquet")
    oi_path      = os.path.join(CACHE_DIR, f"{SYMBOL}_oi.parquet")
    ls_path      = os.path.join(CACHE_DIR, f"{SYMBOL}_ls.parquet")

    if not os.path.exists(klines_path):
        logger.error(f"OHLCV file not found: {klines_path}")
        logger.error("Please run  python futures_data_downloader.py  first.")
        sys.exit(1)

    ohlcv   = pd.read_parquet(klines_path)
    funding = pd.read_parquet(funding_path) if os.path.exists(funding_path) else pd.DataFrame()
    oi      = pd.read_parquet(oi_path)      if os.path.exists(oi_path)      else pd.DataFrame()
    ls      = pd.read_parquet(ls_path)      if os.path.exists(ls_path)      else pd.DataFrame()

    logger.info(f"Loaded OHLCV: {len(ohlcv):,} bars ({ohlcv.index[0]} -> {ohlcv.index[-1]})")
    return {"ohlcv": ohlcv, "funding": funding, "oi": oi, "ls": ls}


def build_full_feature_matrix(cache: dict) -> pd.DataFrame:
    """Build the feature matrix bar-by-bar using rolling windows."""
    from atlas_futures_core.features.volatility_features  import extract_volatility_features
    from atlas_futures_core.features.momentum_features    import extract_momentum_features
    from atlas_futures_core.features.information_features import extract_information_features

    ohlcv = cache["ohlcv"]
    logger.info("Extracting OHLCV-based features (volatility, momentum, information)...")

    # These return single-row DataFrames by slicing with iloc[-1].
    # For training we need ALL rows — so we call them on growing windows.
    # Optimisation: call on the full DataFrame and take all rows at once.

    vol_df  = extract_volatility_features(ohlcv)
    mom_df  = extract_momentum_features(ohlcv)
    info_df = extract_information_features(ohlcv)

    # Patch: return full-length DataFrames by running the feature
    # functions on full ohlcv but keeping all rows (not just iloc[-1]).
    vol_df_full  = _extract_all_rows(ohlcv, "volatility")
    mom_df_full  = _extract_all_rows(ohlcv, "momentum")
    info_df_full = _extract_all_rows(ohlcv, "information")

    X = pd.concat([vol_df_full, mom_df_full, info_df_full], axis=1)

    # Funding / OI / LS: forward-fill sparse series onto 5m index
    if not cache["funding"].empty:
        fr = cache["funding"]["fundingRate"].reindex(ohlcv.index, method="ffill").fillna(0.0)
        X["funding.rate"] = fr
    else:
        X["funding.rate"] = 0.0

    if not cache["oi"].empty:
        oi = cache["oi"]["sumOpenInterest"].reindex(ohlcv.index, method="ffill").bfill()
        X["funding.open_interest"] = oi.fillna(0.0)
    else:
        X["funding.open_interest"] = 0.0

    if not cache["ls"].empty:
        ls = cache["ls"]["longShortRatio"].reindex(ohlcv.index, method="ffill").fillna(1.0)
        X["funding.long_short_ratio"] = ls
    else:
        X["funding.long_short_ratio"] = 1.0

    # Derived funding features
    X["funding.rate_zscore_50"]      = _zscore(X["funding.rate"], 50)
    X["funding.cumulative_funding_24h"] = X["funding.rate"].rolling(3).sum()
    X["funding.funding_velocity"]    = X["funding.rate"].diff(3)
    X["funding.oi_change_pct"]       = X["funding.open_interest"].pct_change()
    X["funding.oi_weighted_funding"] = X["funding.rate"] * X["funding.open_interest"]
    X["funding.ls_ratio_zscore_30"]  = _zscore(X["funding.long_short_ratio"], 30)
    X["funding.oi_price_divergence"] = (
        (ohlcv["close"].diff().apply(np.sign) != X["funding.oi_change_pct"].apply(np.sign))
        .astype(float)
    )
    X["funding.liquidation_volume_est"] = (
        (X["funding.oi_change_pct"] < -0.005) & (ohlcv["close"].pct_change().abs() > 0.005)
    ).astype(float)

    # Regime features (simple deterministic from already computed columns)
    X["regime.time_of_day_sin"] = (ohlcv.index.hour + ohlcv.index.minute / 60.0).map(
        lambda h: np.sin(2 * np.pi * h / 24.0)
    )
    X["regime.vol_regime"]       = pd.cut(
        _zscore(X["vol.realized_vol_30"], 100), bins=5, labels=False
    ).fillna(2).astype(float)

    adx = X.get("mom.trend_strength_adx_14", pd.Series(0.0, index=X.index))
    eff = X.get("mom.trend_efficiency_ratio", pd.Series(0.0, index=X.index))
    X["regime.trend_regime"]     = ((adx > 25) & (eff > 0.3)).astype(float)

    vpin = X.get("flow.vpin_50", pd.Series(0.5, index=X.index))
    X["regime.flow_toxicity_regime"] = pd.cut(
        vpin, bins=[0, 0.6, 0.8, 1.0], labels=[0, 1, 2]
    ).fillna(0).astype(float)

    hurst = X.get("info.hurst_exponent_50", pd.Series(0.5, index=X.index))
    vwap_dist = X.get("mom.price_vs_vwap", pd.Series(0.0, index=X.index)).abs()
    X["regime.mean_reversion_score"] = vwap_dist * (0.5 - hurst).clip(lower=0)
    X["regime.trend_following_score"] = (
        X.get("mom.roc_10", pd.Series(0.0, index=X.index)).abs()
        * (hurst - 0.5).clip(lower=0) * eff
    )
    vol_of_vol = X.get("vol.vol_of_vol", pd.Series(0.0, index=X.index))
    X["regime.risk_score"] = vpin * vol_of_vol * (1 + X["funding.rate_zscore_50"].abs())
    X["regime.edge_score"] = (
        X[["regime.mean_reversion_score", "regime.trend_following_score"]].max(axis=1)
        / (X["regime.risk_score"] + 1e-6)
    )
    X["regime.zscore_composite"] = X[
        ["vol.vol_zscore_50", "funding.rate_zscore_50", "funding.ls_ratio_zscore_30"]
    ].abs().mean(axis=1)
    X["regime.liquidity_regime"] = 1.0  # placeholder (no live orderbook in historical)
    X["regime.composite_regime_label"] = (
        X["regime.trend_regime"] * 15 + X["regime.vol_regime"] * 3 + X["regime.flow_toxicity_regime"]
    )
    X["regime.regime_duration"]         = 0.0
    X["regime.regime_transition_prob"]  = 0.0

    # Orderbook & trade flow placeholders for historical (no tick data stored)
    for col in [
        "ob.bid_ask_spread","ob.spread_bps","ob.mid_price","ob.weighted_mid",
        "ob.book_imbalance","ob.depth_ratio_5","ob.depth_ratio_10",
        "ob.depth_imbalance_gradient","ob.cumulative_depth_delta","ob.microprice",
        "ob.spread_zscore_30", "ob.book_imbalance_ema_12",
        "flow.net_volume_delta","flow.cumulative_volume_delta","flow.cvd_divergence",
        "flow.taker_buy_ratio","flow.vpin_50","flow.vpin_100","flow.block_trade_freq",
        "flow.trade_intensity","flow.trade_intensity_zscore",
        "flow.avg_trade_size","flow.large_trade_volume_pct","flow.aggressor_imbalance",
    ]:
        if col not in X.columns:
            X[col] = 0.0

    return X.ffill().fillna(0.0)


def _extract_all_rows(ohlcv: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Extract features for all rows (not just the last)."""
    import numpy as np

    if kind == "volatility":
        from atlas_futures_core.features.volatility_features import extract_volatility_features as fn
    elif kind == "momentum":
        from atlas_futures_core.features.momentum_features import extract_momentum_features as fn
    elif kind == "information":
        from atlas_futures_core.features.information_features import extract_information_features as fn
    else:
        return pd.DataFrame()

    df = ohlcv.copy()
    # All these functions operate on the full dataframe and already compute rolling features.
    # We just need to drop the `.iloc[[-1]]` slice — so we replicate the logic inline.
    # The functions return df[features].fillna(0).iloc[[-1]], so we call the inner logic.
    # Since we can't easily call the inner logic, we'll refactor: call the function but
    # patch it to return all rows.

    # Simple approach: import the function, remove the `.iloc[[-1]]` by running it
    # on a temp copy and returning all rows instead of last.
    # We achieve this by importing the full computation from the module directly.

    if kind == "volatility":
        periods_per_year = 365 * 24 * (60 / 5)
        df["log_ret"] = np.log(df["close"] / df["close"].shift(1))
        df["vol.realized_vol_10"] = df["log_ret"].rolling(10).std() * np.sqrt(periods_per_year)
        df["vol.realized_vol_30"] = df["log_ret"].rolling(30).std() * np.sqrt(periods_per_year)
        df["vol.realized_vol_100"] = df["log_ret"].rolling(100).std() * np.sqrt(periods_per_year)
        log_hl = np.log(df["high"] / df["low"])
        log_co = np.log(df["close"] / df["open"])
        df["gk_var"] = 0.5 * (log_hl**2) - (2*np.log(2) - 1) * (log_co**2)
        df["vol.garman_klass_vol"] = np.sqrt(df["gk_var"].rolling(30).mean() * periods_per_year)
        df["vol.parkinson_vol"] = np.sqrt((log_hl**2 / (4*np.log(2))).rolling(30).mean() * periods_per_year)
        df["vol.yang_zhang_vol"] = df["vol.garman_klass_vol"]
        df["vol.vol_of_vol"] = df["vol.realized_vol_10"].rolling(20).std()
        df["vol.vol_ratio_short_long"] = df["vol.realized_vol_10"] / df["vol.realized_vol_100"].replace(0, np.nan)
        vol_mean_50 = df["vol.realized_vol_10"].rolling(50).mean()
        vol_std_50  = df["vol.realized_vol_10"].rolling(50).std()
        df["vol.vol_zscore_50"] = (df["vol.realized_vol_10"] - vol_mean_50) / vol_std_50.replace(0, np.nan)
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"]  - df["close"].shift(1)).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["vol.atr_14"] = true_range.ewm(span=14, adjust=False).mean()
        df["vol.atr_pct_14"] = (df["vol.atr_14"] / df["close"]) * 100
        natr_med = df["vol.atr_pct_14"].rolling(50).median()
        df["vol.natr_expansion_flag"] = (df["vol.atr_pct_14"] > 2 * natr_med).astype(float)
        cols = ["vol.realized_vol_10","vol.realized_vol_30","vol.realized_vol_100",
                "vol.garman_klass_vol","vol.parkinson_vol","vol.yang_zhang_vol",
                "vol.vol_of_vol","vol.vol_ratio_short_long","vol.vol_zscore_50",
                "vol.atr_14","vol.atr_pct_14","vol.natr_expansion_flag"]
        return df[cols].fillna(0.0)

    elif kind == "momentum":
        close = df["close"]
        df["mom.log_return_1"]  = np.log(close / close.shift(1))
        df["mom.log_return_5"]  = np.log(close / close.shift(5))
        df["mom.log_return_20"] = np.log(close / close.shift(20))
        df["mom.roc_10"] = (close - close.shift(10)) / close.shift(10)
        df["mom.acceleration"] = df["mom.log_return_5"].diff()
        df["mom.jerk"]         = df["mom.acceleration"].diff()
        ema_9  = close.ewm(span=9,  adjust=False).mean()
        ema_21 = close.ewm(span=21, adjust=False).mean()
        df["mom.ema_cross_signal"] = (ema_9 - ema_21) / close
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        macd_line   = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        df["mom.macd_histogram"] = (macd_line - signal_line) / close
        dp = close.diff()
        tsi_num = dp.ewm(span=25, adjust=False).mean().ewm(span=13, adjust=False).mean()
        tsi_den = dp.abs().ewm(span=25, adjust=False).mean().ewm(span=13, adjust=False).mean()
        df["mom.tsi"] = (tsi_num / tsi_den).fillna(0.0)
        tp  = (df["high"] + df["low"] + close) / 3
        vol = df["volume"]
        vwap = (tp * vol).rolling(288, min_periods=10).sum() / vol.rolling(288, min_periods=10).sum()
        df["mom.price_vs_vwap"] = (close - vwap) / vwap
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - close.shift(1)).abs()
        tr3 = (df["low"]  - close.shift(1)).abs()
        tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        up_move   = df["high"] - df["high"].shift(1)
        down_move = df["low"].shift(1) - df["low"]
        plus_dm   = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm  = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        atr       = tr.ewm(span=14, adjust=False).mean()
        plus_di   = 100 * pd.Series(plus_dm, index=df.index).ewm(span=14, adjust=False).mean() / atr
        minus_di  = 100 * pd.Series(minus_dm, index=df.index).ewm(span=14, adjust=False).mean() / atr
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan))
        df["mom.trend_strength_adx_14"] = dx.ewm(span=14, adjust=False).mean()
        direction  = (close - close.shift(14)).abs()
        volatility = close.diff().abs().rolling(14).sum()
        df["mom.trend_efficiency_ratio"] = direction / volatility.replace(0, np.nan)
        cols = ["mom.log_return_1","mom.log_return_5","mom.log_return_20","mom.roc_10",
                "mom.acceleration","mom.jerk","mom.ema_cross_signal","mom.macd_histogram",
                "mom.tsi","mom.price_vs_vwap","mom.trend_strength_adx_14","mom.trend_efficiency_ratio"]
        return df[cols].fillna(0.0)

    elif kind == "information":
        returns    = np.log(df["close"] / df["close"].shift(1)).fillna(0)
        vol_change = np.log(df["volume"] / df["volume"].shift(1).replace(0, np.nan)).fillna(0)

        def shannon_entropy(series, bins=10):
            if len(series) < bins: return 0.0
            hist, _ = np.histogram(series, bins=bins, density=True)
            p = hist[hist > 0]
            return -np.sum(p * np.log(p))

        df["info.return_entropy_20"]  = returns.rolling(20).apply(shannon_entropy, raw=True)
        df["info.volume_entropy_20"]  = vol_change.rolling(20).apply(shannon_entropy, raw=True)

        def fast_apen(s):
            if len(s) < 10: return 0.0
            return np.std(np.diff(s)) / (np.std(s) + 1e-8)

        df["info.approx_entropy_10"]  = returns.rolling(10).apply(fast_apen, raw=True)
        df["info.sample_entropy_10"]  = df["info.approx_entropy_10"] * 0.9
        df["info.mutual_info_vol_ret"] = returns.abs().rolling(20).corr(vol_change.abs())

        def hurst_rs(a):
            if len(a) < 20: return 0.5
            mean = a.mean(); y = a - mean; z = np.cumsum(y)
            r = z.max() - z.min(); s = a.std()
            if s == 0: return 0.5
            rs = r / s
            return np.log(rs) / np.log(len(a) / 2) if rs > 0 else 0.5

        df["info.hurst_exponent_100"] = returns.rolling(100).apply(hurst_rs, raw=True)
        df["info.hurst_exponent_50"]  = returns.rolling(50).apply(hurst_rs, raw=True)
        df["info.dfa_alpha"]          = df["info.hurst_exponent_50"]

        def higuchi_fd(a):
            if len(a) < 20: return 1.5
            L = np.sum(np.abs(np.diff(a)))
            amp = a.max() - a.min()
            if amp == 0: return 1.0
            return 1.0 + np.log(L / amp) / np.log(len(a))

        df["info.fractal_dimension_20"] = df["close"].rolling(20).apply(higuchi_fd, raw=True)

        def kl_div(a):
            if len(a) < 20: return 0.0
            r, b = a[-10:], a[:-10]
            mr, sr = r.mean(), r.std()
            mb, sb = b.mean(), b.std()
            if sb == 0 or sr == 0: return 0.0
            return np.log(sb/sr) + (sr**2 + (mr - mb)**2) / (2 * sb**2) - 0.5

        df["info.kl_divergence_vol"] = vol_change.rolling(30).apply(kl_div, raw=True)

        cols = ["info.return_entropy_20","info.volume_entropy_20","info.approx_entropy_10",
                "info.sample_entropy_10","info.mutual_info_vol_ret","info.hurst_exponent_100",
                "info.hurst_exponent_50","info.dfa_alpha","info.fractal_dimension_20","info.kl_divergence_vol"]
        return df[cols].fillna(0.0)

    return pd.DataFrame()


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mu  = series.rolling(window).mean()
    sig = series.rolling(window).std()
    return ((series - mu) / sig.replace(0, np.nan)).fillna(0.0)


if __name__ == "__main__":
    from futures_learning_system.dataset.labels import generate_futures_labels
    from futures_learning_system.training.trainer import FuturesTrainer

    print("=" * 60)
    print("Atlas Futures Engine — Auto Trainer")
    print("=" * 60)

    cache = load_cache()

    logger.info("Building full feature matrix...")
    X = build_full_feature_matrix(cache)
    logger.info(f"Feature matrix shape: {X.shape}")

    logger.info("Generating labels...")
    y, valid_mask = generate_futures_labels(X, cache["ohlcv"], horizon=LABEL_HORIZON)

    X = X[valid_mask]
    y = y[valid_mask]
    logger.info(f"Training samples: {len(X)} | Class balance: {y.value_counts().to_dict()}")

    trainer = FuturesTrainer(artifacts_dir=ARTIFACTS_DIR)
    model, mean_acc = trainer.train(X, y, n_splits=5)

    logger.info(f"\n✅ Training complete!  Walk-forward accuracy: {mean_acc:.4f}")
    logger.info(f"   Model saved to: {ARTIFACTS_DIR}/futures_xgb_v1.pkl")
    logger.info("\nNext step: run  python futures_paper_daemon.py")

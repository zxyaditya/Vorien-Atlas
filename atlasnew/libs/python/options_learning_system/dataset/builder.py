"""Dataset Builder.

Builds the complete OptionsDataset consisting of features (X) and labels (y).
Combines Greeks, Surface, Flow, Moneyness, and Spot features.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Any
import pandas as pd

from atlas_options_core.features.greeks_features import extract_greeks_features
from atlas_options_core.features.surface_features import extract_surface_features
from atlas_options_core.features.flow_features import extract_flow_features
from atlas_options_core.features.moneyness_features import extract_moneyness_features
from atlas_options_core.features.spot_features import extract_spot_features
from atlas_options_core.features.hft_features import extract_hft_features
from options_learning_system.dataset.labels import generate_labels
from atlas_options_core.data.chain_builder import OptionsChain


@dataclass
class OptionsDatasetSpec:
    horizon: int = 5
    label_kind: str = "spot_direction"
    label_params: Dict[str, Any] = field(default_factory=dict)
    front_dte_max: int = 45


@dataclass
class OptionsDataset:
    spec: OptionsDatasetSpec
    X: pd.DataFrame
    y: pd.Series
    index: pd.Index
    n_rows: int
    n_features: int
    class_balance: Dict[str, int]
    fingerprint: str


def build_options_feature_matrix(chains: List[OptionsChain],
                                   trades_df: pd.DataFrame,
                                   spot_ohlcv: pd.DataFrame,
                                   spec: OptionsDatasetSpec) -> pd.DataFrame:
    """Extract and merge all feature layers into a single matrix."""
    greeks_df = extract_greeks_features(chains, spec.front_dte_max)
    surface_df = extract_surface_features(chains, spot_ohlcv, spec.front_dte_max)
    flow_df = extract_flow_features(chains, trades_df, spec.front_dte_max)
    money_df = extract_moneyness_features(chains, spec.front_dte_max)
    spot_df = extract_spot_features(spot_ohlcv)
    hft_df = extract_hft_features(chains, trades_df, spot_ohlcv)

    # Merge all DataFrames on timestamp (which is the index)
    dfs = [greeks_df, surface_df, flow_df, money_df, spot_df, hft_df]
    X = dfs[0]
    for df in dfs[1:]:
        if not df.empty:
            X = X.join(df, how="outer", rsuffix="_dup")

    # Drop any duplicate columns that may have resulted from joins
    X = X.loc[:, ~X.columns.str.endswith('_dup')]
    
    # Drop any index duplicates that could cause Cartesian blowups during labels alignment
    X = X[~X.index.duplicated(keep="last")]
    
    return X.ffill().fillna(0.0)


def build_dataset(chains: List[OptionsChain],
                    trades_df: pd.DataFrame,
                    spot_ohlcv: pd.DataFrame,
                    spec: OptionsDatasetSpec) -> OptionsDataset:
    
    # 1. Build Features
    X = build_options_feature_matrix(chains, trades_df, spot_ohlcv, spec)
    
    # 2. Build Labels
    spot_close = spot_ohlcv["close"] if not spot_ohlcv.empty else pd.Series(index=X.index, dtype=float)
    y, valid_mask = generate_labels(X, spot_close, spec.label_kind, spec.horizon, **spec.label_params)
    
    # 3. Align & Filter
    idx = X.index.intersection(y.index)
    X = X.loc[idx]
    y = y.loc[idx]
    valid_mask = valid_mask.loc[idx]
    
    X = X[valid_mask]
    y = y[valid_mask]
    
    # 4. Fingerprint
    payload = f"{spec.horizon}_{spec.label_kind}_{X.shape}_{y.sum()}"
    fingerprint = hashlib.sha1(payload.encode()).hexdigest()[:12]
    
    counts = y.value_counts().to_dict()
    balance = {str(k): v for k, v in counts.items()}
    
    return OptionsDataset(
        spec=spec, X=X, y=y, index=X.index,
        n_rows=len(X), n_features=X.shape[1],
        class_balance=balance, fingerprint=fingerprint
    )

import os
import time
import random
import argparse
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup API URL and Authentication
API_URL = "http://127.0.0.1:8001/api"
ACCESS_CODE = os.environ.get("ATLAS_ACCESS_CODES", "atlas2026").split(",")[0]
HEADERS = {"Authorization": f"Bearer {ACCESS_CODE}"}

def fetch_available_models():
    """Fetch registered models from backend."""
    try:
        res = requests.get(f"{API_URL}/learning/models/registered", headers=HEADERS)
        res.raise_for_status()
        return res.json().get("kinds", [])
    except Exception as e:
        print(f"[AutoTrainer] Error fetching models: {e}")
        return ["xgboost", "lightgbm", "random_forest", "linear_svm", "logistic_regression", "elastic_net", "tcn", "mlp", "transformer"]

def fetch_available_features():
    """Fetch registered features from backend."""
    try:
        res = requests.get(f"{API_URL}/registry/features", headers=HEADERS)
        res.raise_for_status()
        features = res.json()
        return [f["id"] for f in features]
    except Exception as e:
        print(f"[AutoTrainer] Error fetching features: {e}")
        return ["price.magnitude.close", "price.trend.sma_cross", "volatility.regime"]

def get_random_hyperparams(model_kind: str) -> dict:
    """Generate random hyperparameter grids for specific models."""
    if model_kind in ["xgboost", "lightgbm", "random_forest"]:
        return {
            "n_estimators": random.choice([50, 100, 200]),
            "max_depth": random.choice([3, 5, 7]),
            "learning_rate": random.choice([0.01, 0.05, 0.1]),
            "alpha": 5.0,
            "lambda": 1.0,
            "colsample_bytree": 0.8
        }
    elif model_kind in ["tcn", "mlp", "transformer"]:
        return {
            "hidden_size": random.choice([32, 64, 128]),
            "num_layers": random.choice([1, 2, 3]),
            "dropout": random.choice([0.1, 0.2, 0.3])
        }
    return {}

def run_backtest(model_id: str, provider: str, symbol: str, interval: str, period: str):
    print(f"   -> [Backtest] Running out-of-sample backtest for {model_id}...")
    try:
        payload = {
            "model_id": model_id,
            "provider": provider,
            "symbol": symbol,
            "interval": interval,
            "period": "1y",              # STRICT 1-year OOS holdout
            "allow_short": True,
            "upper_threshold": 0.502,    # Tight threshold for L1-regularized prob squashing
            "lower_threshold": 0.498,
            "stop_loss_pct": 0.0,
            "take_profit_pct": 0.0,
            "stop_atr_mult": 1.5,        # ATR-based initial stop loss
            "take_profit_atr_mult": 3.0, # ATR-based initial TP (ratcheted to trailing)
            "trailing_stop_atr_mult": 1.5,
            "hold_bars": 0,
            "cool_down_bars": 1,
            "regime_gate": False,        # Let the ML model decide; no manual regime filter
            "warmup_bars": 150,
            "initial_cash": 100000.0,
            "position_size_pct": 20.0,   # Flat 20% sizing for fair ablation comparison
            "max_leverage": 2.0,
            "fractional_kelly": 1.0,     # No Kelly scaling — flat sizing for ablation
            "dynamic_sizing": False,     # Disable L4 Kelly for fair L1/L2/L3 comparison
            "dynamic_exits": False,      # Disable L3 regime exits for fair comparison
        }
        res = requests.post(f"{API_URL}/learning/backtest/run", json=payload, headers=HEADERS, timeout=600)
        if res.status_code == 200:
            data = res.json()
            metrics = data.get("metrics", {})
            ret = metrics.get("total_return_pct", 0)
            sharpe = metrics.get("sharpe", 0)
            n_trades = metrics.get("n_trades", 0)
            mdd = metrics.get("max_drawdown_pct", 0)
            print(f"   -> [Backtest Success] Return: {ret:.2f}% | Sharpe: {sharpe:.2f} | Trades: {n_trades} | MDD: {mdd:.2f}%")
            
            # Patch the model with these stats
            patch_data = {"n_trades": n_trades, "max_drawdown_pct": mdd}
            requests.patch(f"{API_URL}/learning/models/{model_id}", json=patch_data, headers=HEADERS)
        else:
            print(f"   -> [Backtest Failed]: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"   -> [Backtest Error]: {e}")

def run_loop(provider: str, symbol: str, intervals: list, period: str, label_kinds: list):
    print("=" * 60)
    print("ATLAS AUTO-TRAINER DAEMON STARTED")
    print("=" * 60)
    print(f"Target: {provider}/{symbol}")
    print(f"Intervals: {intervals}")
    print(f"Period: {period}")
    print("=" * 60)
    
    models = fetch_available_models()
    gpu_models = ["xgboost"]
    if not gpu_models:
        gpu_models = ['xgboost']  # Fallback
        
    all_features = fetch_available_features()
    
    print(f"Loaded {len(models)} models ({len(gpu_models)} GPU-accelerated) and {len(all_features)} features.")
    
    experiment_count = 1
    
    while True:
        try:
            model_kind = random.choice(gpu_models)
            hyperparams = get_random_hyperparams(model_kind)
            seed = random.randint(1, 1000)
            horizon = 5
            interval = random.choice(intervals)
            min_history = 1000
            
            categories = {}
            for f in all_features:
                cat = f.split(".")[0]
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(f)
                
            layer1_prefixes = ["price", "volume", "time"]
            layer2_prefixes = ["trend", "momentum", "volatility"]
            layer3_prefixes = ["cycle", "pattern", "overlap"]
            
            layer1_cats = [c for c in categories if any(c.startswith(p) for p in layer1_prefixes)]
            layer2_cats = [c for c in categories if any(c.startswith(p) for p in layer2_prefixes)]
            layer3_cats = [c for c in categories if any(c.startswith(p) for p in layer3_prefixes)]
            layer4_cats = [c for c in categories if c not in layer1_cats + layer2_cats + layer3_cats]
            
            L1_features = []
            for c in layer1_cats: L1_features.extend(categories[c])
            
            L2_features = []
            for c in layer2_cats: L2_features.extend(categories[c])
                
            L3_features = []
            for c in layer3_cats: L3_features.extend(categories[c])
                
            L4_features = []
            for c in layer4_cats: L4_features.extend(categories[c])
            
            print(f"\n=======================================================")
            print(f"Starting ABLATION STUDY for {symbol} ({interval}) using {model_kind}")
            
            feature_sets = [
                ("L1_Only", L1_features),
                ("L1_L2", L1_features + L2_features),
                ("L1_L2_L3", L1_features + L2_features + L3_features),
                ("L1_L2_L3_L4", L1_features + L2_features + L3_features + L4_features)
            ]
            
            for stage_name, stage_features in feature_sets:
                if not stage_features:
                    continue
                    
                payload = {
                    "name": f"AutoML-{model_kind}-{experiment_count}-{stage_name}",
                    "provider": provider,
                    "symbol": symbol,
                    "interval": interval,
                    "period": period,
                    "dataset": {
                        "feature_ids": stage_features,
                        "horizon": horizon,
                        "label_kind": "regime_triple_barrier",
                        "label_params": {"k_upper": 2.0, "k_lower": 2.0},
                        "min_history": min_history,
                        "dropna_policy": "drop",
                        "regime_filter": True
                    },
                    "split": {
                        "kind": "walk_forward",
                        "n_folds": 5,
                        "embargo": 5,
                        "train_size": 0.5
                    },
                    "model": {
                        "kind": model_kind,
                        "hyperparams": hyperparams,
                        "seed": seed
                    }
                }
                
                print(f"[{stage_name}] Training with {len(stage_features)} features...")
                res = requests.post(f"{API_URL}/learning/experiments/run", json=payload, headers=HEADERS)
                
                if res.status_code == 200:
                    data = res.json()
                    agg = data.get("aggregate", {})
                    acc = agg.get("accuracy_mean", 0)
                    ic = agg.get("information_coefficient_mean", 0)
                    model_ids = data.get('model_ids', [])
                    model_id = model_ids[0] if model_ids else data.get('experiment_id')
                    print(f"   -> [Success] Acc: {acc:.2%} | IC: {ic:.4f} | ID: {model_id}")
                    
                    if model_id:
                        run_backtest(model_id, provider, symbol, interval, period)
                else:
                    print(f"   -> [Failed]: {res.status_code} - {res.text}")
                    
                time.sleep(2)
                
        except Exception as e:
            print(f"[Error] in ablation loop: {e}")
            
        experiment_count += 1
        
        sleep_time = random.randint(20, 60)
        print(f"[Sleeping] for {sleep_time} seconds before next ablation study...\n")
        time.sleep(sleep_time)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Atlas Auto-Trainer")
    parser.add_argument("--provider", type=str, default="binance", help="Data provider")
    parser.add_argument("--symbol", type=str, default="ETHUSDT", help="Symbol to train on")
    parser.add_argument("--intervals", type=str, default="4h",
                        help="Comma-separated intervals (e.g. 1h,2h,4h)")
    parser.add_argument("--period", type=str, default="4y", help="Historical period to train on")
    parser.add_argument("--label_kinds", type=str, default="quantile,triple_barrier",
                        help="Comma-separated label kinds (e.g. sign,triple_barrier)")
    
    args = parser.parse_args()
    intervals = [i.strip() for i in args.intervals.split(",")]
    label_kinds = [l.strip() for l in args.label_kinds.split(",")]
    
    time.sleep(3)
    run_loop(args.provider, args.symbol, intervals, args.period, label_kinds)

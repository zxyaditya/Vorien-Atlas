# Atlas — Getting Started & Developer Guide

This guide walks you through setting up Atlas on your personal laptop, verifying security, and executing the complete quantitative research lifecycle: **Ingest Data $\to$ Compute Features $\to$ Train Models $\to$ Backtest Strategies $\to$ Deploy to Paper Trading**.

---

## 1. Local Environment & Data Architecture
- **Pure Open-Source Code:** Transparent Python, NumPy, SciPy, and React codebase. Zero compiled binaries, zero obfuscated code, and zero telemetry/external network reporting.
- **Isolated Storage:** Data artifacts, models, and backtest logs write strictly to `~/.atlas/` or local Docker volumes. System files and root directories are untouched.
- **Public Market Feeds (Unauthenticated):** Live and historical candles are pulled directly from public read-only endpoints: Binance CDN mirrors (`data-api.binance.vision`, `fapi.binance.com`), CoinGecko, and Yahoo Finance (`yfinance`). These endpoints are completely public and unauthenticated — no exchange accounts or API keys are used or required.
- **Offline Synthetic Sandbox:** Built-in deterministic regime-switching GBM generators (`atlas_core.data.fixtures`) provide predictable datasets for mathematical unit tests and offline development without internet access.
- **Bring Your Own Data:** Pass any standard OHLCV pandas DataFrame from CSV, Parquet, or local databases directly into the compute pipeline.

---

## 2. Quick Setup: Choose Your Mode

You can run Atlas in two ways depending on your workflow:

### Mode A: Full Platform via Docker Compose (Recommended)
Spins up the complete distributed stack: FastAPI Gateway, Celery ML Workers, React Terminal, MongoDB, Redis, and MinIO.

```bash
# 1. Clone the repository
git clone https://github.com/zxyaditya/vorien-atlas.git
cd vorien-atlas

# 2. Boot the cluster
make up
# (or: cd atlasnew && docker-compose up -d)
```
- **Web Terminal UI:** `http://localhost:3000`
- **FastAPI OpenAPI Swagger:** `http://localhost:8000/docs`
- **MinIO Storage Console:** `http://localhost:9001` (User: `minioadmin` / Pass: `minioadmin`)

To stop: `make down`

---

### Mode B: Lightweight Local Python Development (No Docker Required)
If you just want to use the mathematical features, run backtests, or train models directly in Python or Jupyter notebooks:

```bash
# 1. Create a clean virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add libs to your python path
# Windows PowerShell:
$env:PYTHONPATH = "$PWD\atlasnew\libs\python;$PWD\atlasnew"
# Linux/macOS:
export PYTHONPATH="$PWD/atlasnew/libs/python:$PWD/atlasnew"
```

To run the API and Web UI natively:
```bash
# Terminal 1 — Start FastAPI Server
cd atlasnew
python -m uvicorn apps.api.server:app --reload --port 8000

# Terminal 2 — Start React 19 Atlas Terminal
cd atlasnew/apps/web
npm install
npm start
```
The React frontend automatically connects to your local API on port `8000`.

---

## 3. The 5-Step End-to-End Workflow

Here is how you go from raw market data to a live paper-trading bot using Atlas:

### Step 1: Compute 925 Mathematical Features on Raw Data
Load any standard OHLCV DataFrame (from CSV, Parquet, Binance, or Yahoo Finance) and compute the Atlas Core feature matrix:

```python
import pandas as pd
from atlas_core.compute import compute_features

# Load your OHLCV data (columns: open, high, low, close, volume)
df = pd.read_parquet("BTCUSDT_1h.parquet")

# Compute the entire 925-feature mathematical representation
features = compute_features(df)
print(f"Computed {features.shape[1]} features across {len(features)} bars.")
```

You can also request a specific subset of features by name:
```python
feature_subset = [
    "price.motion.log_return_20",
    "volatility.magnitude.semi_ratio_20",
    "microstructure.geometry.wick_difference_ratio",
    "market_structure.motion.bos_k5",
    "market_regime.regime.active_state_code"
]
X = compute_features(df, feature_subset)
```

---

### Step 2: Generate Leakage-Free Target Labels
Atlas provides 5 institutional label generators in `learning_system.dataset.labels` to prevent lookahead bias:

```python
from learning_system.dataset.labels import (
    generate_sign_labels,
    generate_triple_barrier_labels,
    generate_vol_normalized_labels
)

# 1. Directional Sign of forward 5-bar return
y_sign = generate_sign_labels(df["close"], horizon=5)

# 2. Marcos López de Prado Triple Barrier Labels
# (1 = Profit Target hit first, -1 = Stop Loss hit first, 0 = Vertical Time Barrier)
y_barrier = generate_triple_barrier_labels(
    prices=df["close"],
    pt_pct=0.02,        # 2% Take Profit
    sl_pct=0.01,        # 1% Stop Loss
    horizon_bars=20     # Max holding period
)
```

---

### Step 3: Train an ML Model with Purged K-Fold
Train an XGBoost, LightGBM, or PyTorch sequence model using Purged Cross-Validation with an Embargo window (eliminating autocorrelation leakage):

```python
from learning_system.models.xgboost_model import XGBoostModel
from learning_system.training.walk_forward import purged_kfold_split

# Align features and target
dataset = pd.concat([X, y_barrier.rename("target")], axis=1).dropna()
features_matrix = dataset[X.columns]
labels_vector = dataset["target"]

# Initialize model
model = XGBoostModel(params={"n_estimators": 100, "max_depth": 4, "learning_rate": 0.05})

# Train on historical window
model.fit(features_matrix.iloc[:1000], labels_vector.iloc[:1000])

# Predict out-of-sample edge
probabilities = model.predict_proba(features_matrix.iloc[1000:])
```

---

### Step 4: Run an Event-Driven Walk-Forward Backtest
Simulate realistic execution with maker/taker fees, adverse slippage, and Kelly-fractional position sizing:

```python
from learning_system.backtest.contracts import BacktestSpec, StrategyPolicy
from learning_system.backtest.engine import BacktestEngine

spec = BacktestSpec(
    symbol="BTCUSDT",
    execution_mode="paper",
    initial_cash=100000.0,
    fee_bps=5.0,           # 5 bps fee
    slippage_bps=2.0,      # 2 bps adverse slippage
    policy=StrategyPolicy(
        upper_threshold=0.60,      # Buy if probability > 60%
        lower_threshold=0.40,      # Short if probability < 40%
        allow_short=True,
        position_size_pct=10.0,    # 10% cash per trade
        atr_stop_multiplier=2.0    # Dynamic ATR trailing stop
    )
)

engine = BacktestEngine.build(spec)
result = engine.run(df=df.iloc[1000:], model=model, feature_ids=X.columns.tolist())

# View performance metrics
print(f"Sharpe Ratio:    {result.metrics.sharpe:.2f}")
print(f"Total Return:    {result.metrics.total_return_pct:.2f}%")
print(f"Max Drawdown:    {result.metrics.max_drawdown_pct:.2f}%")
print(f"Win Rate:        {result.metrics.win_rate * 100:.1f}%")
print(f"Profit Factor:   {result.metrics.profit_factor:.2f}")
```

---

### Step 5: Deploy to Paper Trading & Decision Engine Voting
Deploy your strategy to the Atlas execution sandbox and view live signals in the Web UI:

```python
from decision_engine.signals import compute_all_signals
from decision_engine.voter import vote
from paper_trading.contracts import OpenPositionRequest
from paper_trading.engine import open_position

# 1. Evaluate the 22 Decision Engine signals on latest market state
snapshot = compute_all_signals(df)
decision = vote(snapshot["signals"])

print(f"Recommendation: {decision['decision']}")
print(f"Confidence:     {decision['confidence']:.2f}")

# 2. If decision triggers, route to Paper Trading Ledger
if decision["decision"] == "LONG":
    account = {"account_id": "acc_001", "cash": 100000.0, "currency": "USD"}
    req = OpenPositionRequest(
        account_id="acc_001",
        provider="binance",
        symbol="BTCUSDT",
        interval="1h",
        side="long",
        reference_price=float(df["close"].iloc[-1]),
        size_pct=10.0,
        stop_price=float(df["close"].iloc[-1] * 0.98),
        take_profit_price=float(df["close"].iloc[-1] * 1.04),
        atlas_snapshot=decision
    )
    new_position, updated_account = open_position(account, [], req)
    print(f"Paper Order Filled: {new_position.side} @ ${new_position.entry_price:.2f}")
```

Open the Atlas Terminal UI at `http://localhost:3000` to monitor your portfolio equity curve, mark-to-market valuations, and active trades in real time.

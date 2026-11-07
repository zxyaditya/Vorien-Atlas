# Vorien · Atlas

**An open-source quantitative research and feature engineering engine for financial markets.**

---

## What is Vorien · Atlas?

If you have ever tried building a quantitative trading strategy, you probably noticed two common challenges:
1. **Most open-source tools are too simplistic**: They rely on basic technical indicators (like simple RSI or moving averages) that fail in modern, high-speed electronic markets.
2. **Most backtests lie to you**: It is surprisingly easy to accidentally write code that "cheats" by looking into the future (lookahead bias) or testing models on overlapping data (data leakage). You end up with a strategy that looks amazing on historical charts but loses money the moment it runs live.

**Vorien Atlas is built to solve this.** Think of it as a **scientific laboratory for financial market data**.

Rather than telling you what to buy or sell, Atlas provides an institutional foundation to explore, measure, and model market dynamics with mathematical honesty:

- 🔬 **Measures the Market from Over 1,000 Angles**: Computes **1,039 mathematical features** across Spot, Futures, and Options — measuring orderbook depth, trade flow, buyer/seller aggression, volatility waves, and options Greeks. Every formula is strictly **causal** (strictly backward-looking, zero lookahead bias).
- 🛡️ **Prevents You From Fooling Yourself**: Built-in **Combinatorial Purged Cross-Validation (CPCV)** and **Triple Barrier event-driven labeling** guarantee your machine learning models are trained and tested without future leakage.
- ⚙️ **Simulates Realistic Market Realities**: Event-driven backtesting simulates real exchange conditions: maker/taker commission tiers, volume-weighted adverse slippage, and execution queues.
- 💻 **Frictionless Developer Experience**: Use Atlas as a lightweight Python library directly inside your Jupyter notebooks (`pip install -r requirements.txt`), or launch the local web terminal and FastAPI service to inspect orderbooks and paper-trade visually.

---

## What Can You Do With Atlas?

Atlas provides an end-to-end quantitative pipeline out-of-the-box:

```text
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│ 1. Raw Market   │ ──> │ 2. Compute 1,039     │ ──> │ 3. Train ML Models  │
│    Data (OHLCV) │     │    Features (L1–L4)  │     │    (Purged K-Fold)  │
└─────────────────┘     └──────────────────────┘     └──────────┬──────────┘
                                                                │
                                                                ▼
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│ 6. React 19 Web │ <── │ 5. Paper Trading &   │ <── │ 4. Event-Driven     │
│    Terminal UI  │     │    Live Decisions    │     │    Backtesting      │
└─────────────────┘     └──────────────────────┘     └─────────────────────┘
```

1. **Feature Engineering:** Instantly compute **925 Core mathematical features** (price, volume, volatility, microstructure, liquidity, wavelets, fractal scaling, and regime states) directly from raw OHLCV tick or bar data.
2. **Leakage-Free Labeling:** Generate institutional target variables: Marcos López de Prado's **Triple Barrier Method**, Volatility-Normalized Returns, and Forward Return Quantiles.
3. **Machine Learning Pipelines:** Train and register tabular models (**XGBoost**, **LightGBM**, **RandomForest**) and sequence architectures (**PyTorch LSTM**, **Transformer**, **Temporal Fusion Transformer (TFT)**) with combinatorial purged cross-validation to prevent autocorrelation leakage.
4. **Event-Driven Backtesting:** Simulate historical execution with realistic maker/taker commission schedules, volume-weighted adverse slippage, and Kelly-criterion position sizing.
5. **Autonomous Decision Engine & Paper Execution:** Route market representations through **22 regime-conditional signal voters** and execute simulated live trades in an isolated paper trading ledger with mark-to-market accounting.
6. **Interactive Visual Terminal:** Monitor real-time charts, model predictions, feature distributions, and equity curves inside a high-speed React 19 terminal interface.

---

## 5-Minute Python Quickstart (Zero-Docker Required)

You do not need to run Docker to use Atlas as a quantitative library. You can import and compute features directly in Python or Jupyter notebooks:

```bash
# 1. Clone the repository
git clone https://github.com/zxyaditya/Vorien-Atlas.git
cd Vorien-Atlas

# 2. Install dependencies
pip install -r requirements.txt
```

```python
import pandas as pd
import numpy as np
from atlas_core.compute import compute_features
from decision_engine.signals import compute_all_signals
from decision_engine.voter import vote

# 1. Load any standard OHLCV DataFrame (from CSV, Parquet, or Exchange API)
df = pd.read_parquet("your_market_data.parquet")

# 2. Compute the 925-feature mathematical representation
features = compute_features(df)
print(f"Computed {features.shape[1]} features across {len(features)} bars.")

# 3. Evaluate the 22 Decision Engine signals & get a regime-aware vote
snapshot = compute_all_signals(df)
decision = vote(snapshot["signals"])
print(f"Strategy Recommendation: {decision['decision']} (Confidence: {decision['confidence']:.2f})")
```

For the complete end-to-end tutorial with model training and backtesting code, see the **[Getting Started Developer Guide](./docs/GETTING_STARTED.md)**.

---

## Local Environment & Data Architecture

- **Open Source & Local Execution:** Pure Python, NumPy, SciPy, and React. No compiled binaries, no obfuscation, and no external telemetry or cloud dependencies.
- **Local Storage Isolation:** Model checkpoints, cache files, and logs write strictly to `~/.atlas/` or local Docker volumes. System files are never touched.
- **Public Market Data (Unauthenticated):** Historical and live crypto candles are fetched from Binance public REST/CDN mirrors (`data-api.binance.vision`, `fapi.binance.com`) and equities from Yahoo Finance. These are public market feeds — no API keys, accounts, or credentials are required.
- **Custom Datasets:** Compatible with any standard OHLCV pandas DataFrame loaded from CSV, Parquet, or local databases.
- **Offline Synthetic Mode:** Deterministic regime-switching GBM generators (`atlas_core.data.fixtures`) provide predictable data for mathematical unit tests and offline development without internet access.

---

## Architecture & Feature Universe

Atlas organizes market representation into two strict tiers, computing **1,039 verified features**:

### Tier 1: Atlas Core (L1–L4) — The Mathematical Representation Layer

**925 features** across four mathematically ordered layers. No opinions. No predictions. Pure measurement.

| Layer | Count | Modules | What it measures |
|:---|:---:|:---:|:---|
| **L1 · Measurement** | **612** | 12 | Price (316), volatility (85), volume (65), microstructure (54), liquidity (40), time (27), orderbook (10), whale microstructure (5), econometrics (4), entropy (3), chaos theory (2), spectral (1) — directly from raw OHLCV and tick feeds |
| **L2 · Relationships** | **151** | 9 | Inter-feature relationships: market structure (44), momentum of trend (32), fractal scaling (21), trend relationships (20), relative strength (12), swing dynamics (10), compression/expansion (7), derivatives (3), stat arb (2) |
| **L3 · Understanding** | **90** | 5 | Categorical and probabilistic regimes: market regime (22), trend state (17), range state (17), participation state (17), liquidity state (17) |
| **L4 · Representation** | **72** | 5 | Compressed abstractions: cross-module interactions (19), meta-features (15), state encodings (14), multi-scale representations (14), embeddings (10) |

Every feature is uniquely identified by a deterministic SHA-1 formula-and-parameter hash. Zero duplicates. Zero lookahead bias.

### Specialized Derivatives Domain Cores (114 Features)

- **Futures Core (69 features):** Orderbook depth gradients, Cumulative Volume Delta (CVD), aggressor imbalance, Hawkes trade arrival intensity, and perpetual funding rate dynamics.
- **Options Core (45 features):** First- to third-order greeks (vanna, volga, charm, speed, color), volatility surfaces, skew/smile dynamics, and gamma exposure (GEX).

---

### Tier 2: Layer-5 Consumers — The Reasoning Layer

L5 modules sit entirely outside Atlas Core. They consume features through a read-only API and produce decisions, never modifying the representation layer.

- **Decision Engine** — 22 signal extractors with a regime-conditional weighted voter. Learns signal weights from recent realized returns via rolling logistic regression. Historical analogue retrieval via K-NN in L4 embedding space.
- **Learning System** — Full ML lifecycle: dataset construction with combinatorial purged cross-validation (CPCV) → walk-forward experiment → model training (XGBoost, LightGBM, PyTorch LSTM, Transformer, TFT) → backtest → live inference. Deployed as async Celery workers.
- **Paper Trading Engine** — Position management, mark-to-market accounting, ATR-dynamic stops, Kelly-fractional sizing, and adverse slippage simulation.
- **Research Modules** — Statistical Arbitrage (cointegration, Kalman filter, HMM, Copula), Whale Hunter (volume-bar HFT, order flow imbalance), Futures Engine, Options Engine, Funding Arbitrage.

---

## Full Distributed Cluster (Docker Compose)

To spin up the complete distributed enterprise cluster (FastAPI + React 19 UI + Celery Worker + MongoDB + Redis + MinIO):

```bash
# Start all services in the background
make up
# (or: cd atlasnew && docker-compose up -d)
```

- **Atlas Terminal (Web UI):** `http://localhost:3000`
- **FastAPI OpenAPI Swagger:** `http://localhost:8000/docs`
- **MinIO Object Store:** `http://localhost:9001` (User: `minioadmin` / Pass: `minioadmin`)

To stop the cluster: `make down`

---

## Documentation

Full architectural and mathematical documentation lives in [`docs/`](./docs/):

- [`docs/GETTING_STARTED.md`](./docs/GETTING_STARTED.md) — Complete end-to-end developer walkthrough with working code examples
- [`docs/README.md`](./docs/README.md) — System overview, invariants, and architecture diagram
- [`docs/FEATURE_HIERARCHY.md`](./docs/FEATURE_HIERARCHY.md) — Complete 925-feature mathematical taxonomy
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — Distributed infrastructure, service topology, and network layer
- [`docs/DECISION_ENGINE.md`](./docs/DECISION_ENGINE.md) — 22 signal extractors, voter mechanics, and K-NN analogues
- [`docs/LEARNING_SYSTEM.md`](./docs/LEARNING_SYSTEM.md) — ML lifecycle, purged cross-validation, and neural models
- [`docs/BACKTEST_ENGINE.md`](./docs/BACKTEST_ENGINE.md) — Event-driven backtesting engine and execution simulation
- [`docs/PAPER_TRADING.md`](./docs/PAPER_TRADING.md) — Mark-to-market accounting, slippage modeling, and audit trails
- [`docs/RESEARCH_MODULES.md`](./docs/RESEARCH_MODULES.md) — Stat Arb, Whale Hunter, Futures, and Options engines
- [`docs/VALIDATION_FRAMEWORK.md`](./docs/VALIDATION_FRAMEWORK.md) — Mathematical certification, universal validation gates

---

## Contributing, Bug Reports & Feature Requests

We highly value your bug reports, feature suggestions, and contributions!

- **Report Bugs & Suggest Features**: Please feel free to open a [GitHub Issue](https://github.com/zxyaditya/Vorien-Atlas/issues) for any unexpected numerical behavior, API edge cases, performance bottlenecks, or feature proposals.
- **Before Submitting a Pull Request (PR)**: You **must** read our comprehensive [Documentation](./docs/) and review the [Contributing Guide](./CONTRIBUTING.md) to understand our architectural standards (strict mathematical purity in L1–L4, zero lookahead bias, and test coverage). All PRs must pass `pytest tests/` before being merged.

---

## License & Dual Licensing

Vorien Atlas is dual-licensed under the **PolyForm Noncommercial License 1.0.0**:

- **Personal, Academic & Research Use**: 100% Free to use, study, explore, modify, and build personal quantitative models.
- **Commercial & Institutional Use**: Any deployment by hedge funds, proprietary trading firms, commercial enterprises, or for trading live capital for monetary compensation requires a commercial license agreement.

For institutional inquiries, enterprise licensing, or commercial clearance, please contact:  
**Aditya Yadav** (`@zxyaditya`) — `adityakumar93416@gmail.com`

See the full [LICENSE](./LICENSE) file for complete legal terms.

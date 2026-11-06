# Atlas Platform — Documentation

> **Institutional-Grade Quantitative Research Infrastructure**  
> Mathematically rigorous representation framework, autonomous research pipelines, and execution engine.

Atlas is a distributed quantitative research platform governed by strict mathematical purity invariants (*Book 1: Foundations of Atlas*). It is **not** an off-the-shelf trading bot, **not** a basic Technical Analysis library, and **not** a superficial machine-learning wrapper. 

It is designed from first principles to represent financial markets purely mathematically before any predictive or commercial decision is attempted.

---

## 1. Architectural Philosophy: The Book 1 Principles

Atlas is strictly governed by the foundational invariants of **Book 1**. 

When anything in the repository conflicts with Book 1, Book 1 wins — no exceptions. 

### Core Architectural Invariants:
1. **Separation of Measurement and Decision (Invariant 5.6):**  
   Never place Layer-5 concepts inside `atlas_core/`. Machine learning models, price predictions, sentiment, portfolio optimization, risk sizing, and order routing are Layer-5 concerns. They belong exclusively in `decision_engine/`, `learning_system/`, or external consumers.
2. **Strict Upward Information Flow (Invariant 6.4):**  
   Information flows upward only: $\text{Raw Data} \to L1 \to L2 \to L3 \to L4 \to L5$. No layer may import from a sibling module or read from a higher layer. Lower-layer math is never re-implemented in higher layers; higher layers consume lower layers via the Feature Registry.
3. **Deterministic Uniqueness (Invariant 2.1):**  
   Every feature in the Registry is uniquely identified by a deterministic SHA-1 formula-and-parameter hash. Duplicate mathematical formulations are rejected at boot time.
4. **Descriptive Naming Discipline:**  
   Feature identifiers describe *what is measured*, not *what it means* (e.g., `price.motion.log_return_20`, not `price.bullish_momentum`).
5. **Analytical Validation Standards:**  
   Every engine and module must adhere to formal analytical properties (monotonicity, scale invariance, zero-bias, and bounded domain verification).

---

## 2. Two-Tier Platform Architecture

The system is fundamentally structured into two tiers:
1. **Tier 1: Atlas Core (L1–L4)** — The mathematical market representation engine.
2. **Tier 2: Layer-5 Consumers** — Autonomous reasoning, decision-making, and execution engines.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ATLAS TERMINAL (L5 UI)                           │
│                        React 19  ·  Lightweight Charts                      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTPS / WSS
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI APPLICATION GATEWAY                        │
│                           Port 8000  ·  REST & WebSockets                   │
└─┬───────────────────────────────────────────┬───────────────────────────────┘
  │                                           │
  ▼                                           ▼
┌───────────────────────────────┐   ┌─────────────────────────────────────────┐
│ Infrastructure Services       │   │ Layer 5 Consumers                       │
│ • MongoDB 6.0 (Metadata)      │   │ • Decision Engine (22 Signals + Voter)  │
│ • Redis 7 (Message Broker)    │   │ • Learning System (ML Lifecycle)        │
│ • MinIO (S3 Artifact Storage) │   │ • Paper Trading Engine (Slippage/Risk)  │
│ • Celery Distributed Workers  │   │ • Quantitative Research Modules         │
└───────────────────────────────┘   └────────────────────┬────────────────────┘
                                                         │ Read-Only Registry
                                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ATLAS CORE (LAYERS 1–4)                             │
│                    925 Registered Mathematical Features                     │
│                                                                             │
│  ╔════ Layer 4: Representation (72 features) ════════════════════════════╗  │
│  ║     Dense embeddings, state encodings, multi-scale compression        ║  │
│  ╚══════════════════════════════▲════════════════════════════════════════╝  │
│                                 │ (L3, L2, L1 inputs)                       │
│  ╔════ Layer 3: Market Understanding (90 features) ══════════════════════╗  │
│  ║     Regime classification, accumulation, sweeps, structural state     ║  │
│  ╚══════════════════════════════▲════════════════════════════════════════╝  │
│                                 │ (L2, L1 inputs)                           │
│  ╔════ Layer 2: Relationships (151 features) ════════════════════════════╗  │
│  ║     Cross-module interactions, fractal scaling, relative strength     ║  │
│  ╚══════════════════════════════▲════════════════════════════════════════╝  │
│                                 │ (L1 inputs)                               │
│  ╔════ Layer 1: Measurement (612 features) ══════════════════════════════╗  │
│  ║     Price, volume, volatility, microstructure, liquidity, time        ║  │
│  ╚══════════════════════════════▲════════════════════════════════════════╝  │
│                                 │ (Raw Tick & OHLCV Feeds)                  │
│                     Raw Market Ingestion Engine                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Platform Feature Universe: 1,039 Total Features

Atlas provides an expansive, verified universe of **1,039 features** across all quantitative dimensions:

### Tier 1: Atlas Core (925 Features)

| Layer | Features | Modules | What it Represents |
|:---|:---:|:---:|:---|
| **Layer 1: Measurement** | **612** | 12 | Pure physical measurements: price (316), volatility (85), volume (65), microstructure (54), liquidity (40), time (27), orderbook (10), whale microstructure (5), econometrics (4), entropy (3), chaos theory (2), spectral (1). |
| **Layer 2: Relationships** | **151** | 9 | Inter-feature relationships: market structure (44), momentum of trend (32), fractal relationships (21), trend relationships (20), relative strength (12), swing dynamics (10), compression/expansion (7), derivatives (3), stat arb (2). |
| **Layer 3: Understanding** | **90** | 5 | Categorical and probabilistic market regimes: market regime (22), trend state (17), range state (17), participation state (17), liquidity state (17). |
| **Layer 4: Representation** | **72** | 5 | Compressed geometric abstractions: cross-module interactions (19), meta features (15), state encodings (14), multi-scale representations (14), embeddings (10). |

### Tier 2: Derivatives & Domain Cores (114 Features)

- **`atlas_futures_core` (69 features):** Perpetual swaps & futures: orderbook depth gradient (12), trade flow & CVD (12), volatility (12), momentum (12), information-theoretic entropy (10), funding rates & open interest dynamics (11).
- **`atlas_options_core` (45 features):** Options surfaces & greeks: first- to third-order greeks (21), volatility surface & skew (9), moneyness dynamics (7), high-frequency gamma exposure (5), order flow toxicity (3).

---

## 4. Layer-5 Reasoning Consumers

Layer-5 modules sit completely outside Atlas Core and consume its features to perform analysis and execution:

1. **Decision Engine:**  
   Evaluates 22 signal extractors across L1–L4 representations. Uses a regime-conditional weighted voter with dynamic weights learned via rolling logistic regression against forward returns. Includes K-NN historical analogue retrieval in L4 embedding space.
2. **Learning System:**  
   Orchestrates the entire ML lifecycle: automated dataset generation with combinatorial purged cross-validation (CPCV), model training (XGBoost, LightGBM, PyTorch LSTM, Transformer, TFT), walk-forward validation, model registry, and async inference.
3. **Paper Trading Engine:**  
   Full execution sandbox with mark-to-market accounting, adverse slippage modeling, commission schedules, Kelly-fractional sizing, and ATR-dynamic trailing stops.
4. **Quantitative Research Modules:**  
   - **Statistical Arbitrage:** Cointegration testing, Kalman filter dynamic hedge ratios, Ornstein-Uhlenbeck mean-reversion modeling, and Copula pairs trading.
   - **Whale Hunter:** Volume-bar aggregation, Order Flow Imbalance (OFI), Kyle's Lambda liquidity impact, and institutional accumulation detection.
   - **Funding Arbitrage:** Cross-exchange perpetual swap funding rate divergence tracking.

---

## 5. Distributed Infrastructure

The platform runs as a coordinated Docker Compose cluster:

- **`api`:** FastAPI backend exposing REST and WebSocket endpoints for market snapshots, feature registries, decision feeds, and backtest results.
- **`web`:** React 19 Atlas Terminal interface with real-time Lightweight Charts.
- **`worker`:** Celery distributed worker executing asynchronous model training and multi-year walk-forward backtests.
- **`mongo`:** MongoDB 6.0 document store for feature definitions, experiment metadata, and project state.
- **`redis`:** Redis 7 message broker and low-latency cache.
- **`minio`:** S3-compatible high-performance object store for model weights, dataset parquet matrices, and backtest artifacts.

---

## 6. Documentation Index

The complete documentation suite provides exhaustive specifications:

- **[GETTING_STARTED.md](./GETTING_STARTED.md)** — Comprehensive developer guide: install, compute features, train ML models, backtest, and paper trade.
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Distributed microservices architecture, network topology, and API specifications.
- **[FEATURE_HIERARCHY.md](./FEATURE_HIERARCHY.md)** — Complete mathematical taxonomy of all 925 Atlas Core features across L1–L4.
- **[DECISION_ENGINE.md](./DECISION_ENGINE.md)** — 22 signal extractors, voter mechanics, adaptive weight learning, and risk controls.
- **[LEARNING_SYSTEM.md](./LEARNING_SYSTEM.md)** — End-to-end machine learning lifecycle, neural architectures, and model tracking.
- **[BACKTEST_ENGINE.md](./BACKTEST_ENGINE.md)** — Event-driven and vectorized backtesting, broker execution simulation, and performance metrics.
- **[PAPER_TRADING.md](./PAPER_TRADING.md)** — Simulated execution engine, portfolio state tracking, and risk management.
- **[RESEARCH_MODULES.md](./RESEARCH_MODULES.md)** — Statistical Arbitrage, Whale Hunter, and Funding Arbitrage specifications.
- **[VALIDATION_FRAMEWORK.md](./VALIDATION_FRAMEWORK.md)** — Mathematical certification, universal validation gates, and invariant checks.
- **[PROJECT_CONTEXT.md](./PROJECT_CONTEXT.md)** — Platform status, implementation audit, and roadmap.
- **[KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md)** — Documented technical constraints and deliberate engineering trade-offs.

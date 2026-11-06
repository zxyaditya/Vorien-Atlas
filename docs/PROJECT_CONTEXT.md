# Atlas — Project Context

## The Founding Mission of Atlas
Quantitative finance and algorithmic development are often hampered by brittle data pipelines, unprincipled indicators, and coupled codebases. **Atlas** is designed to address this challenge: a distributed, mathematically pure, institutional-grade quantitative research infrastructure platform. The mission of Atlas is to provide a complete, rigorous, and completely decoupled ecosystem where quantitative researchers can transition from raw tick/bar data to deep market representations without writing ad-hoc data engineering boilerplate.

## The Book 1 Philosophy: Pure Mathematical Representation
Atlas is governed by **Book 1**, the foundational architectural constitution. The core philosophy of Book 1 is that **measurement must always precede interpretation**. Atlas Core (Layers 1 through 4) is dedicated entirely to the pure mathematical representation of financial markets. It extracts **925 features** across 22 Perspectives (Statistics, Motion, Regime, Geometry, Magnitude, Position, Relative, Distribution, Expansion, Entropy, Clustering, Microstructure, Risk, Flow, Efficiency, Information, Liquidity, DSP, Activity, Spectral, Memory, Fractal). 

There are no opinions, no machine learning predictions, and no trading logic inside the Core. It is a deterministic engine that maps OHLCV and market depth into a structured, multi-dimensional geometric space.

## What Atlas is NOT
To understand Atlas, one must understand what it is not:
- **Atlas is NOT a simple trading bot:** It does not blindly execute simplistic moving average crossovers on a live brokerage account.
- **Atlas is NOT a basic TA (Technical Analysis) library:** It is not a wrapper over retail indicator libraries. It provides mathematically robust, institutional-grade measurements (e.g., fractional differentiation, rolling spectral entropy, L-moments, K-NN analogue matching in embedding spaces).
- **Atlas is NOT a collection of ad-hoc Jupyter Notebooks:** It is a scalable, distributed platform built on FastAPI, Celery, Redis, MongoDB, and MinIO, designed for massive parallel backtesting and live inference.
- **Atlas is NOT a superficial ML wrapper:** It handles the entire lifecycle of quantitative research, ensuring zero future-leakage, combinatorial purged cross-validation, and proper mark-to-market execution modeling.

## Research Principles Governing Architecture
Every line of code in Atlas respects these principles:
1. **Mathematical Purity:** A function does exactly one mathematical operation with proven properties.
2. **Zero Future Leakage:** Lookahead bias is mathematically prevented by design.
3. **Interpretability:** Decision Engine rules and adaptive weights are completely explainable.
4. **Decoupled Isolation:** Subsystems (Decision Engine, Learning System, Paper Trading) are siblings. They consume Atlas Core representations through a read-only registry interface and never mutate them.

## The Target User
Atlas is built for the **quantitative researcher, algorithmic trader, and systems engineer**. It provides an institutional framework that demonstrates how distributed, high-performance computing (NumPy, Numba JIT, Celery, Redis) and pure mathematics intersect.

## The Core Architectural Invariant: The L1-L4 / L5 Split
The decision to split the system into **Atlas Core (L1-L4)** and the **Consumer Subsystems (L5)** is the defining architectural feature of Atlas (DEC-001):
- **L1-L4 (Atlas Core):** Contains 925 purely mathematical features (L1: 612, L2: 151, L3: 90, L4: 72). It knows nothing about labels, predictions, or money.
- **L5 (Consumers):** The Decision Engine (22 signal extractors + regime-conditional voter), the Learning System (full ML lifecycle), Paper Trading, and specialized research engines (Stat Arb, Whale Hunter, Futures, Options) exist here.

This split guarantees that the mathematical representation of the market can evolve independently of strategy and execution logic, preventing architectural entropy.

## Long-Term Vision
Atlas provides an open-source, reproducible standard for quantitative research infrastructure. It enables researchers to discover and validate alpha from mathematically sound representations of financial markets.

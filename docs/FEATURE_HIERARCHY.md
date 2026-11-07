# Feature Hierarchy — Domain Logic and Architectural Specifications

## 1. Core Philosophy

Atlas is a mathematically pure financial market representation framework. It is fundamentally **not** a trading bot, **not** a technical analysis library, and **not** a machine learning wrapper. It exists to engineer a robust, objective, and mathematically sound understanding of market state. This document is the single overarching contract defining the domain logic of the entire feature computation pipeline.

Every feature within Atlas is governed by the principles of **Book 1: Foundations of Atlas**. A feature must represent a purely objective mathematical property of the market state. Subjective interpretations (e.g., "bullish", "oversold", "buy signal") are strictly forbidden within the feature layer; such concepts are deferred entirely to Layer-5 consumers (Decision Engine, Learning System).

---

## 2. The 4-Layer Hierarchy

Atlas organizes its feature computation into four mathematically ordered layers. Each layer represents an increasing level of abstraction, built strictly upon the foundations of the layers beneath it.

```text
+-----------------------------------------------------------------------------------+
| LAYER 4: REPRESENTATION (72 features)                                             |
| Exposes ML-ready embeddings, PCAs, cross-module interactions, state encodings.    |
| Modules: cross_module_interactions (19), meta_features (15),                      |
|          state_encodings (14), multi_scale_representations (14), embeddings (10).  |
+----------------------------------------^------------------------------------------+
                                         | (l3_series, l2_series, l1_series)
+----------------------------------------|------------------------------------------+
| LAYER 3: MARKET UNDERSTANDING (90 features)                                       |
| Contextual interpretation of states, regime flags, hysteresis durations.          |
| Modules: market_regime (22), trend_state (17), range_state (17),                  |
|          participation_state (17), liquidity_state (17).                          |
+----------------------------------------^------------------------------------------+
                                         | (l2_series, l1_series)
+----------------------------------------|------------------------------------------+
| LAYER 2: RELATIONSHIPS (151 features)                                             |
| Interactions and relationships between L1 measurements. Does not see raw OHLCV.   |
| Modules: market_structure (44), momentum_of_trend (32), fractal_relationships (21)|
|          trend_relationships (20), relative_strength (12), swing_dynamics (10),    |
|          compression_expansion (7), derivatives (3), stat_arb_features (2).       |
+----------------------------------------^------------------------------------------+
                                         | (l1_series)
+----------------------------------------|------------------------------------------+
| LAYER 1: MEASUREMENT (612 features)                                               |
| Pure objective measurements of physical reality (price, volume, time, dispersion).|
| Modules: price (316), volatility (85), volume (65), microstructure (54),          |
|          liquidity (40), time (27), orderbook (10), whale_microstructure (5),     |
|          econometrics (4), advanced_entropy (3), chaos_theory (2), spectral (1).  |
+----------------------------------------^------------------------------------------+
                                         | (raw ingestion)
+----------------------------------------|------------------------------------------+
| RAW DATA                                                                          |
| Tick data, OHLCV, L2/L3 Orderbook, Executed Trades                                |
+-----------------------------------------------------------------------------------+
```

### 2.1 Total Feature Count Per Layer
Atlas Core computes **925 features** across its four core layers:
* **L1 (Measurement):** 612 features (The widest base of pure physical metrics)
* **L2 (Relationships):** 151 features (Interacting properties)
* **L3 (Market Understanding):** 90 features (Categorical and probabilistic states)
* **L4 (Representation):** 72 features (Dense embeddings, interactions)

In addition, derivative domain cores provide:
* **`atlas_futures_core`:** 69 perpetual swap & futures features (orderbook, CVD, funding rate dynamics).
* **`atlas_options_core`:** 45 options surface & greeks features (first- to third-order greeks, skew, variance swaps).
* **Grand Total Platform Features:** **1,039 features**

### 2.2 The Strict Rule: No Sibling or Upward Imports
**No layer may import from a sibling module or a higher layer.** (Book 1 Invariant 1). 
* An L2 module cannot read from L3. 
* An L2 module cannot import directly from another L2 module. 
If cross-module interaction is required within the same layer, it must be escalated to a higher layer that naturally synthesizes those concepts (e.g., L4 synthesizes L1/L2/L3). This ensures the DAG (Directed Acyclic Graph) of feature computation remains perfectly cycle-free and mathematically tractable.

---

## 3. L1: Measurement Layer (612 features)

**Book 1 Definition:** *"What objectively happened?"*

Layer 1 operates directly on raw market data (OHLCV, orderbook, trades). It applies domain-neutral mathematical engines to extract fundamental measurements. It interprets nothing; it merely observes and quantifies physical realities of the market instrument.

### 3.1 L1 Feature Modules and Exact Counts
The L1 ecosystem consists of 612 features distributed across 12 distinct modules:
* **`price` (316 features):** Raw distance, displacement, moving averages as pure low-pass filters, logarithmic returns, ATR bounds, fractional differentiation series.
* **`volatility` (85 features):** Variance, standard deviation, Parkinson volatility, Garman-Klass, Yang-Zhang, kurtosis, inter-quantile ranges, semi-variance.
* **`volume` (65 features):** Execution quantities, block densities, volume-weighted pricing, point processes of trades, VWAP deviations.
* **`microstructure` (54 features):** Order flow imbalances, bid-ask spread geometries, tick-level sign agreement, wick asymmetries, Kyle's Lambda.
* **`liquidity` (40 features):** Amihud illiquidity, turnover ratios, depth ratios, bid-ask spreads, orderbook slope.
* **`time` (27 features):** Time-in-state, bar counts between structural events, cyclical time encodings (sine/cosine transforms).
* **`orderbook` (10 features):** Level-2 book depth ratios, top-of-book skew, microprice deviation.
* **`whale_microstructure` (5 features):** Large-trade arrival rates, institutional volume concentration, execution aggression.
* **`econometrics` (4 features):** Autoregressive parameters, ADF statistics, Hurst exponents.
* **`advanced_entropy` (3 features):** Permutation entropy, spectral entropy, sample entropy.
* **`chaos_theory` (2 features):** Higuchi fractal dimension, Lyapunov exponent approximations.
* **`spectral_advanced` (1 feature):** Dominant cycle phase angle via Fast Fourier Transform.

---

## 4. L2: Relationships Layer (151 features)

**Book 1 Definition:** *"How do these measurements interact?"*

Layer 2 composes L1 measurements to describe relationships. It does not look directly at raw market data; it accesses L1 through the `_l1_bridge`.

### 4.1 L2 Feature Modules and Exact Counts
* **`market_structure` (44 features):** Break of Structure (BOS), Change of Character (CHoCH), fractal highs/lows agreement, swing distance.
* **`momentum_of_trend` (32 features):** Velocity of linear regression slopes, ADX acceleration, sign agreement between momentum and trend.
* **`fractal_relationships` (21 features):** Multi-scale self-similarity, variance scaling exponents across dyadic scales ($2^1$ to $2^6$).
* **`trend_relationships` (20 features):** Directional consensus across disparate moving average cascades, alignment scores.
* **`relative_strength` (12 features):** Cross-asset beta, rolling correlation, cointegration residual variance against peers.
* **`swing_dynamics` (10 features):** Swing amplitude ratios, wave duration asymmetries, retracement percentages.
* **`compression_expansion` (7 features):** Bollinger bandwidth ratios, Donchian channel squeeze indicators.
* **`derivatives` (3 features):** Basis spread, spot-perpetual premium.
* **`stat_arb_features` (2 features):** Spread z-score, half-life of mean reversion.

---

## 5. L3: Market Understanding Layer (90 features)

**Book 1 Definition:** *"What state is the market in?"*

Layer 3 provides structural, categorical, and probabilistic classifications of market environment. It contextualizes the measurements and relationships of L1 and L2 into discrete, mutually exclusive regimes with hysteresis damping to eliminate signal chatter.

### 5.1 L3 Feature Modules and Exact Counts
Each L3 module outputs state codes, duration in state, and probabilistic state confidences:
* **`market_regime` (22 features):** Four-way macroeconomic regime classification:
  - State 1: Trending Quiet (low volatility, persistent drift)
  - State 2: Trending Volatile (high volatility, persistent drift)
  - State 3: Ranging Quiet (low volatility, mean-reverting)
  - State 4: Ranging Volatile (high volatility, turbulent mean-reversion)
* **`trend_state` (17 features):** Uptrend, downtrend, exhaustion, consolidation states with multi-scale confidence.
* **`range_state` (17 features):** Range formation, breakout environment, expansion states.
* **`participation_state` (17 features):** Institutional accumulation, aggressive distribution, passive absorption.
* **`liquidity_state` (17 features):** Deep liquidity, liquidity void, sweep vulnerability, replenishment speed.

---

## 6. L4: Representation Layer (72 features)

**Book 1 Definition:** *"How can this market state be encoded for reasoning?"*

Layer 4 transforms all lower-layer measurements, relationships, and states into compressed, orthogonal, ML-ready vector representations.

### 6.1 L4 Feature Modules and Exact Counts
* **`cross_module_interactions` (19 features):** Non-linear interactions combining trend $\times$ volume, structure $\times$ momentum, and volatility $\times$ liquidity.
* **`meta_features` (15 features):** Agreement scores across L3 state families, cross-layer confidence standard deviations.
* **`state_encodings` (14 features):** One-hot and continuous geometric encodings of active market regimes.
* **`multi_scale_representations` (14 features):** Multi-timeframe compressed representations.
* **`embeddings` (10 features):** Dense low-dimensional representations optimized for K-NN historical analogue search.

---

## 7. Mathematical Engines (20 Domain-Neutral Engines)

All Atlas Core features are computed using 20 domain-neutral mathematical engines in `atlas_core/engines`:

1. **`crossasset`:** Rolling correlation, covariance, and cointegration estimation.
2. **`distance`:** Euclidean, Manhattan, and Mahalanobis distances in multi-dimensional space.
3. **`distribution`:** Skewness, kurtosis, empirical quantiles, and probability density functions.
4. **`dsp`:** Digital signal processing: Butterworth, Chebyshev, and Kalman filters.
5. **`flow_proxy`:** Order flow proxy estimations from tick and bar data.
6. **`fractal`:** Hurst exponent, Higuchi fractal dimension, and variance ratio tests.
7. **`fractional`:** Fractional differentiation for long-memory preservation.
8. **`geometry`:** Linear regression straightness, curvature, angle, and channel slopes.
9. **`information`:** Shannon entropy, permutation entropy, mutual information, and Kullback-Leibler divergence.
10. **`liquidity`:** Amihud illiquidity, Roll spread, Kyle's Lambda, and bid-ask modeling.
11. **`lmoments`:** L-location, L-scale, L-skewness, and L-kurtosis for outlier-resistant statistics.
12. **`motion`:** Velocity, acceleration, momentum, and rate-of-change estimators.
13. **`normalization`:** Rolling z-scores, min-max bounds, and quantile transforms.
14. **`point_process`:** Hawkes process and Poisson estimators for trade arrival dynamics.
15. **`rolling`:** High-performance rolling window accumulators.
16. **`spectral`:** Fast Fourier Transforms, Lomb-Scargle periodograms, and cyclical decomposition.
17. **`statistics`:** Welford online variance, covariance, and sample moments.
18. **`swings`:** Zig-zag peak/trough detection, swing amplitude, and retracement geometry.
19. **`technical`:** Baseline indicators formulated as pure mathematical filters.
20. **`wavelet`:** Continuous Wavelet Transform (CWT) multi-frequency decomposition.

---

## 8. Layer-5 Derivatives Domain Extensions (114 Features)

Beyond the 925 core spot primitives in L1–L4, Atlas incorporates 114 specialized derivatives dimensions defined in `apps/api/derivatives_registry.py` and computed via `atlas_futures_core` and `atlas_options_core`:

### 8.1 Futures & Perpetuals Features (69 features)
- **Orderbook Microstructure (15 features):** Depth-weighted microprice, microprice-midpoint divergence, Level-1/5/10 bid-ask depth imbalance ratios, depth slope, weighted spread in basis points.
- **Order Flow & Toxicity (12 features):** Volume-Synchronized Probability of Toxicity (VPIN 50 & 100 buckets), Cumulative Volume Delta (CVD), aggressive taker buy ratio, trade arrival intensity, large block taker frequency.
- **Perpetual Funding & Carry (18 features):** 8-hour settlement funding rate, funding velocity ($d\text{Rate}/dt$), funding acceleration, funding 50-period Z-score, annualized carry APR, spot-perpetual basis spread.
- **Open Interest & Liquidations (14 features):** Rolling OI delta, OI/Price divergence vectors, Top Trader Long/Short account ratio, Top Trader position ratio, estimated liquidation volume cascades.
- **Intraday Volatility Dynamics (10 features):** High-frequency Parkinson volatility, Garman-Klass volatility, Yang-Zhang drift-independent estimator, intraday ATR ratio, return velocity and acceleration.

### 8.2 Options Volatility Surface & Greeks (45 features)
- **First-Order Greeks (10 features):** Black-Scholes Delta, Vega, Theta, Rho computed across strikes and expiries.
- **Higher-Order Greeks (12 features):** Gamma (convexity), Vanna ($d\Delta/d\sigma$), Volga ($d\nu/d\sigma$), Charm ($d\Delta/dt$), Color ($d\Gamma/dt$), Speed ($d\Gamma/dS$).
- **Volatility Surface Dynamics (11 features):** At-The-Money (ATM) Implied Volatility (30d, 60d, 90d), 25-Delta Risk Reversal (Put vs. Call skew), 25-Delta Butterfly (smile curvature / fat-tail pricing), Term Structure slope (Contango vs. Backwardation).
- **Dealer Market Structure (12 features):** Net Dealer Gamma Exposure (GEX in $M), Net Dealer Vega Exposure (VEX), Gamma Flip Level (volatility transition boundary), Max Pain strike (expiration magnet pin), Options VPIN flow toxicity, Volatility Risk Premium (VRP = IV - RV).

---

## 9. The Validation Framework

The Atlas Validation Framework (DEC-013) is an active subsystem that mathematically certifies features against rigorous criteria:

### Validation Gates:
- **Universal Gates:**
  - `determinism`: Identical inputs strictly yield identical outputs.
  - `length_invariance`: Output length matches input length exactly.
  - `no_future_leakage`: Data at index $t+k$ cannot affect feature output at index $t$.
  - `nan_input_behavior`: Validates defined behavior on missing values.
  - `degenerate_constant`: Validates behavior on zero-variance flatline series.
- **Property Gates:**
  - `bounded`: Enforces output bounds $[lo, hi]$ where mathematically applicable.
  - `scale_invariance`: $f(k \cdot X) = f(X)$ for scale-independent metrics.
  - `translation_invariance`: $f(X + c) = f(X)$ for location-independent metrics.
  - `monotonic_with`: Output changes monotonically with named market variables.
- **Registry-Wide Gates:**
  - `unique_formula_hash`: SHA-1 deduplication constraint.
  - `no_duplicate_values`: Prevents co-linear redundant features.

Every feature exposed to Layer-5 reasoning satisfies these certification standards.

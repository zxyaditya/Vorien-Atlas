# Atlas — Roadmap

> Long-term plan, separated by track. Not fixed in stone; re-prioritise as we learn.

---

## Track · Layer 1 (Measurement)

### Shipped
- price (285), volatility (79), volume (46), liquidity (40), time (27), microstructure (40)

### Next
- Extend microstructure with intra-bar tick-imbalance proxies (when tick data available).
- **Do not add more L1 modules speculatively.** Book 1 says architecture > feature count.

---

## Track · Layer 2 (Relationships) — the active frontier

### Shipped (v0.6)
- market_structure (44), swing_dynamics (10), compression_expansion (7), relative_strength (12)

### Shipped (v0.7)
- **v0.7.0** — `momentum_of_trend` (32) — temporal derivatives of L1 trend measurements (slopes, ADX, Aroon). 4 goldens. New `TrendMomentum` DE signal.
- **v0.7.1** — `trend_relationships` (20) — cross-source + cross-scale agreement across LR-slope / EMA-slope / ADX / Aroon / R². 5 goldens. New `TrendAlignment` DE signal.
- **v0.7.2** — `fractal_relationships` (21) — self-similarity / scale-invariance across ≥ 3 scales (variance-scaling, structure-function generalised Hurst H(q), variance-ratio envelope, Hurst/FD cross-window consistency, Haar wavelet variance, range-scaling). 6 goldens (all Brownian-anchored). **New `FractalCoherence` DE signal (direction-neutral).** Introduces the **Three-Scale Rule** as a permanent architectural guardrail.
- **v0.7.3** — Relative Strength **frontend integration** (peer picker + RS mini-chart + `RelativeStrength` direction-neutral DE signal + DEC-012 retrofit spec + peer-abstraction architectural review). No new features registered; 12 pre-existing RS features become fully visible. **1 new pytest golden anchor** (`rs(a, a) ≡ 1`) inside `TestRelativeStrengthV073`.
- **v0.7.4** — **Validation Framework** (Priority 5 of Session 7). Turns Book 1 Ch. 9 validation from a hand-authored pytest collection into a permanent architectural subsystem (`atlas_core/validation/`). Every feature carries an optional first-class `FeatureValidation` declaration; a `ValidationRunner` proves each declared claim against canonical fixtures; a `ValidationProfile` is persistent metadata alongside `formula`/`params`/`perspective`. Ships 5 universal gates, property gates, and 4 registry-wide gates (`unique_formula_hash`, `no_duplicate_values`, `three_scale_rule`, `context_isolation`). Authorised by **DEC-013**. First live run surfaced the **DEC-007 context leak** in `_orchestrator.compute_features` — fixed and regression-tested at both the framework and orchestrator levels. **42/42 backend pytests pass (serial).**

### v0.7 remaining targets
- ✅ Session 7 complete. Second-order compression/expansion (regime-conditional) — deferred to post-Session 7 / v0.8.

### v0.8 targets
- **momentum_relationships** — divergences between price momentum and volume/liquidity momentum.
- **microstructure_relationships** — body-imbalance persistence, wick-difference regime, participation-vs-return coupling.
- Extend relative_strength beyond pairwise to peer-set aggregation once multi-symbol pipeline matures.

---

## Track · Layer 3 (Market Understanding)

Not started. Requires an L3 access contract (bridge for L2 features).

### v0.9 targets (Book 1 examples)
- accumulation, distribution
- trend_continuation, trend_exhaustion
- range_formation, breakout_environment, mean_reversion_environment
- liquidity_sweeps
- market_regimes

Each produces contextual states (persistent regime probabilities), not measurements.

---

## Track · Layer 4 (Representation)

Not started. This is where Cross-Asset lives per Book 1.

### v1.0 targets (Book 1 examples)
- cross_module_interactions (including full Cross-Asset)
- meta_features
- feature_embeddings (auto-encoders on Atlas features)
- dimensionality_reduction (PCA, UMAP)
- feature_selection
- multi_scale_representations
- state_encodings

---

## Track · Decision Engine (Layer 5 · outside Atlas Core)

This track evolves *with* Atlas Core. Every new module in a lower track triggers a review of the Decision Engine (Point 10 permanent rule).

### v0.6 status
- 15 signals as of v0.7.3 (6 new since v0.5: Microstructure L1, MarketStructure L2, TrendMomentum L2 v0.7, TrendAlignment L2 v0.7.1, FractalCoherence L2 v0.7.2 direction-neutral, **RelativeStrength L2 v0.7.3 direction-neutral peer-driven**)
- Voter with manual / learned weights
- Risk engine + deterministic sizing
- K-NN=10 historical analogues
- 4-model ensemble
- Deterministic explainer

### Near-term (v0.7–v0.8)
- **RelativeStrength signal** ✅ **shipped v0.7.3** (consumes relative_strength.* via optional peer context).
- Regime-conditional weight learning: separate learned weights inside {trending, choppy, high-vol, low-vol}.
- **Backtest engine** (`decision_engine/backtest/`): walk-forward, purged K-fold, combinatorial CV.
- Confidence estimation improvements: use L2 fractal_agreement as a confidence booster; use L2 compression as a size-multiplier.
- **Unsigned-strength term for direction-neutral signals in the weight learner** — currently direction-neutral signals get β ≈ 0 because the learner's feature is `direction × strength = 0`. A first-class treatment of confidence-modulator signals lives here alongside regime-conditional weights.

### Mid-term (v0.9–v1.0)
- L3 signals: RegimeSignal (from Market Regime module), ExhaustionSignal, ContinuationSignal.
- L4-informed decisions: use embeddings as analogue-similarity space (replacing the current 19-dim z-space).
- Adaptive analogues: peer-symbol-aware K-NN.
- Position-sizing improvements grounded in L3 regime probabilities.

### Long-term (v1.x)
- Multi-symbol portfolio-level decisions (once L4 cross-module lands).
- LLM narrative explainer (Registry-reader only). Requires Emergent LLM key.
- Reinforcement-learning consumer of Atlas as an alternate L5 (research track).

**Rule**: any new Atlas capability that could improve Signals / Risk / Weight Learner / Analogues / Sizing / Confidence / Explanations / Recommendation Quality must be evaluated. Document "not yet useful" with justification if we defer.

---

## Track · Frontend

### v0.7
- Layer filter (L1 / L2) in Feature Explorer.
- Peer-symbol picker on Decision tab. ✅ **shipped v0.7.3**
- Signal Breakdown responsive to 15+ signals. ✅ **v0.7.3 uses `grid-cols-5` (3×5).** Will need another pass at v0.8.

### v0.8
- Component split of App.js (~968 LOC → components/).
- Structure-view panel: swings + BOS overlays on the candlestick chart.
- Golden test dashboard tab.

### v1.0
- L3 regime timeline visualisation.
- L4 embedding scatter (2-D projection).
- LLM-narrated tab (behind feature flag).

---

## Track · Validation

### v0.7
- Duplicate-value detection across Registry. ✅ **shipped v0.7.4** as registry-wide gate `no_duplicate_values`. Intentionally surfaces the ~20 legacy Registry duplicates for targeted v0.8 cleanup.
- Future-leakage detection (per-feature synthetic-spike test). ✅ **shipped v0.7.4** as universal gate `no_future_leakage`.
- Numerical-stability edge tests (all-zeros, all-equal, NaN-infested). ✅ **shipped v0.7.4** as universal gates `degenerate_constant` + `nan_input_behavior`.
- **Framework-level context isolation gate** (`context_isolation`, registry-wide) — ✅ **shipped v0.7.4**. Its first live run surfaced the DEC-007 orchestrator leak; the fix ships alongside the gate.

### v0.8
- Per-module golden test coverage: minimum 5 declared `Identity` gates per module (cheap now that the framework unifies goldens with declarations).
- **Cleanup of the ~20 legacy numerical Registry duplicates** surfaced by v0.7.4's `no_duplicate_values` gate. One duplicate at a time, one-line rationale per feature (keep / rename / merge).
- **Reproducibility harness**: deterministic seed + hash of Registry stats + framework report hash.
- **Validation-report caching** to remove the parallel-pytest flakiness (~24 s cold report call starves concurrent lightweight endpoints under `-n 2`).

### v0.9
- L3 module goldens (each L3 state must have an analytical scenario that triggers it). The `bridge` field on `FeatureValidation` is reserved for `"l3"` — no framework changes needed to plug L3 modules in.

---

## Track · Research

- Regime-conditional weight learning as a paper-worthy interpretability contribution.
- L4 embedding evaluation: does an autoencoder on Atlas features outperform hand-picked feature subsets for analogues?
- Cross-symbol dispersion regimes: does L4 cross-module dispersion predict L3 breakout/continuation transitions?
- Backtest of Decision Engine vs simple baselines (buy-and-hold, MA cross) on synthetic + real data.

---

## Track · Infrastructure

### v0.7
- Structured logging for `compute_features` (log which feature failed and why).
- Refactor `SIGNAL_FEATURE_IDS` into per-signal `.reads` attribute.

### v0.8
- **Postgres migration for the Registry.** In-memory rebuilding is limiting.
- Vectorise the weight learner (currently O(n·11) per bar in Python).
- Cache `compute_features` results keyed on `(provider, symbol, interval, period)`.

### v0.9
- WebSocket live-tick streaming.
- Finnhub / Polygon / Alpaca integration (paid keys required — request from user).
- CoinGecko volume replacement (synthesized today; misleading in UI).

---

## Long-term vision (unchanged from user directive)

- Atlas Core becomes the world's most complete mathematical representation of financial markets.
- The Decision Engine becomes the world's most explainable AI trader built entirely on Atlas representations.
- Every recommendation traces to specific Atlas features. Never a black box.

---

*Last updated: v0.7.4 (Session 7 · Priority 5 shipped — Validation Framework + DEC-013 + DEC-007 orchestrator context-isolation fix; Session 7 complete).*

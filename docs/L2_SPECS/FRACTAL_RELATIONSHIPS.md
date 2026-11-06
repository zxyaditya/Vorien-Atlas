# L2 Module Specification — `fractal_relationships`

> **Ship version:** v0.7.2 (Session 7 · Priority 3).
> **Layer:** 2 (Relationships) — Book 1 Ch. 5, named exemplar.
> **Status:** Specification (Phase 1 of the DEC-012 workflow). Implementation
> begins only after this specification is approved.

---

## 1. Purpose

Measure whether **the same market phenomenon exhibits self-similar
behaviour across multiple observation scales** — i.e., whether the
statistical laws that describe the market at short scales continue to
describe it at long scales, and by how much they deviate when they do
not.

This module is orthogonal to both existing Session-7 L2 trend modules.
The distinction — enforced at feature-registration time by the
**Three-Scale Rule** (§2 below) and verified by pytest — is:

| Module | Axis | Question |
|---|---|---|
| `momentum_of_trend` (v0.7.0) | **Temporal** derivatives of one L1 measurement | "How does *this measurement* evolve over time?" |
| `trend_relationships` (v0.7.1) | **Cross-methodology / cross-scale** agreement of independent trend measurements at the same `t` | "Do independent trend measurements *agree right now*?" |
| **`fractal_relationships`** (this ship) | **Scaling law across ≥ 3 scales of the same measurement family** | "Does the same phenomenon *scale self-similarly*?" |

Every feature in this module is a **statistical or geometric property of
a scaling relationship**, i.e., of a function `X(τ) = f(τ; α₁, α₂, …)`
where `τ` ranges over a scale set of size ≥ 3. See §2.

---

## 2. The Three-Scale Rule (defining property of this module)

> **Every feature registered in `fractal_relationships` must be computed
> from ≥ 3 distinct observation scales.** If a proposed feature can be
> computed using only one or two scales, it does not belong here.

### 2.1 Why three scales are necessary

A **scaling relationship** is a claim of the form `X(τ) ∝ τ^α` — a
power law whose exponent `α` is the object of interest. Detecting the
relationship means asking whether the log-log data `(log τ, log X(τ))`
falls on a line. This question is only well-posed for `N ≥ 3` scale
points:

- With `N = 1` scale, there is a single point; no line, no exponent.
- With `N = 2` scales, any two points fit a line exactly; the R² of the
  fit is undefined (0/0) and there is no residual against which
  scale-invariance could fail. Two-point features degenerate to a
  simple ratio — which is the mathematical object of
  `trend_relationships` (see the module comparison table above).
- With `N ≥ 3`, the fit has `N − 2 ≥ 1` degrees of freedom in the
  residuals. Only then can we ask *"how well does the power law hold?"*
  — R², max-deviation, envelope-width — and these questions are the
  raison d'être of this module.

### 2.2 Anti-overlap contract

For every registered feature `F`, the module docstring will name the
**minimum scale count `k_F`** used in its computation. `k_F ≥ 3` is a
hard invariant, enforced by:

- Every feature's `params` dict carries a `scales` list; a pytest
  regression asserts `len(scales) ≥ 3` for every `fractal_relationships.*`
  registered feature (see §7).
- Two-scale ratios like `variance_ratio_2 = Var[r_2] / (2 · Var[r_1])`
  are *never* registered on their own; only aggregates across the whole
  scale set (max deviation, std across scales) are registered.

### 2.3 Consequence for architecture

The Three-Scale Rule makes it structurally impossible for
`fractal_relationships` to contain a feature that also fits inside
`trend_relationships`. `trend_relationships.relative.slope_ratio_20_50`
(two-scale ratio) is intentionally *not* replicated here; conversely,
`variance_scaling_exponent_2_64` (six-scale slope) cannot be phrased
inside `trend_relationships` without violating its own scope.

---

## 3. Mathematical question

Given a family of L1 measurements `M_S = {M(τ; ·) : τ ∈ S}` where `S`
is a **scale set of size ≥ 3**, quantify the properties of the
scaling relationship between `M` and `τ`.

Concretely, the module answers seven sub-questions, each of which
requires ≥ 3 scales by construction:

| # | Sub-question | Mathematical object |
|---|---|---|
| Q1 | Do returns' variance scale linearly with time (self-similar Brownian) or with a power? | `α` in `Var[r_τ] ∝ τ^α`, τ ∈ {2,4,8,16,32,64} |
| Q2 | Does the market exhibit **multifractality** — different scaling exponents at different moment orders? | `H(q)` for `q ∈ {1,2,3}`; **spread** `H(1) − H(3)` |
| Q3 | Do variance-ratio departures from unity cluster at a single scale or persist across scales? | Envelope of `VR(τ) = Var[r_τ] / (τ Var[r_1])` over `τ ∈ {2,4,8,16}` |
| Q4 | Is the R/S Hurst estimate **stable** across observation windows, or does it drift with window length? | `std({H_32, H_64, H_128})`, `range(...)`, agreement-side flag |
| Q5 | Is the fractal dimension (path roughness) stable across observation windows? | `std({FD_25, FD_50, FD_100})`, `range(...)` |
| Q6 | Do range-based scaling laws (roughness in the high–low sense) hold at short and long scales? | `β` in `Range(τ) ∝ τ^β`, τ ∈ {5,10,20,40,80} |
| Q7 | Do the *independent* estimators (variance / structure / R/S / FD / range / wavelet) all report a **scale-invariant** story? | Composite self-similarity score across the estimator family; unanimity flag |

Every quantity above is computed on **rolling windows** of length `W`;
`W` is chosen so that even the largest scale in the fit is sampled ≥ 4
times inside `W`. Defaults: `W = 128` for the variance-scaling, VR,
structure-function, and range-scaling families; `W = 256` for the
wavelet family (needed to resolve level `j = 4`).

---

## 4. Inputs (all consumed via `_l1_bridge.l1_series`)

### 4.1 Already registered L1 sources

| Symbol | Feature ID | Used by families |
|---|---|---|
| `close` | `price.magnitude.close` | A, B, C, D, F, G |
| `log_return_1` | `price.motion.log_return_1` | A, B, C, G |
| `hurst_64` | `price.geometry.hurst_64` | D |
| `hurst_128` | `price.geometry.hurst_128` | D |
| `higuchi_fd_50` | `price.geometry.higuchi_fd_50` | E |
| `higuchi_fd_100` | `price.geometry.higuchi_fd_100` | E |
| `true_range` | `price.magnitude.true_range` | F |

### 4.2 L1 prerequisite additions shipped in the same commit as this module

`fractal_relationships` needs **≥ 3 scales** of R/S Hurst and Higuchi
FD (currently registered at only 2 windows each). Rather than compute
extra scales internally — which would be an unregistered L1
measurement, violating Registry-as-source-of-truth — the module ships
alongside two additive L1 registrations:

| New L1 feature ID | Formula | Uses which engine |
|---|---|---|
| `price.geometry.hurst_32` | `hurst_rs(close, w=32)` | `engines.fractal.hurst_rs` (existing) |
| `price.geometry.higuchi_fd_25` | `higuchi_fd(close, w=25, kmax=8)` | `engines.fractal.higuchi_fd` (existing) |

Both use engines that already ship with a golden test in the current
suite (`higuchi_fd_smooth_line_close_to_1` etc.); no additional
engine-level goldens are required. The L1 module goldens are not
extended (Book 1 Ch. 9 minimum: ≥ 1 golden per module — `price`
already exceeds that). L1 feature counts after this addition: **519**
(was 517).

### 4.3 Direct OHLCV access

**None.** Every input above is a Registry lookup. The module's
implementation may not read `df["close"]`, `df["high"]`, `df["low"]`,
`df["open"]`, or `df["volume"]` directly. This is Invariant 6.4 and
is enforced by pytest (`test_fractal_relationships_no_direct_ohlcv`,
mirrored on the audit already applied to `momentum_of_trend` and
`trend_relationships`).

---

## 5. Outputs (registered features)

Feature IDs are formula-descriptive per DEC-009 (no "efficiency",
"complexity", "long-memory" interpretive words in the ID). The signal
name `FractalCoherence` (§8) is L5 and permitted to be interpretive.

Registered under `MODULE = "fractal_relationships"`. Perspectives
touched: **Geometry, Statistics, Distribution, Regime, Position** — 5
of 11.

### 5.1 Geometry — variance & range scaling exponents (5 features)

Scale set `S₁ = {2, 4, 8, 16, 32, 64}` (6 scales) for variance; `S₂ = {5, 10, 20, 40, 80}` (5 scales) for range.

| Feature ID | `k_F` | Formula |
|---|---|---|
| `fractal_relationships.geometry.variance_scaling_exponent_2_64` | 6 | OLS slope of `log Var[r_τ]` vs `log τ` for `τ ∈ S₁` |
| `fractal_relationships.geometry.variance_scaling_r2_2_64` | 6 | R² of the same log-log fit |
| `fractal_relationships.geometry.range_scaling_exponent_5_80` | 5 | OLS slope of `log ⟨range(τ)⟩` vs `log τ` for `τ ∈ S₂` |
| `fractal_relationships.geometry.range_scaling_r2_5_80` | 5 | R² of the same log-log fit |
| `fractal_relationships.geometry.range_scaling_deviation_from_brownian_5_80` | 5 | `|β − 0.5|` — magnitude of departure from Brownian roughness |

### 5.2 Statistics — generalised Hurst & wavelet-variance (5 features)

Scale set `S₃ = {2, 4, 8, 16, 32}` for structure functions (5 scales);
wavelet-scale set `S_W = {1, 2, 3, 4}` for Haar detail levels (4 scales).

| Feature ID | `k_F` | Formula |
|---|---|---|
| `fractal_relationships.statistics.generalized_hurst_h1_2_32` | 5 | slope of `log ⟨|r_τ|¹⟩` vs `log τ`, τ ∈ S₃ |
| `fractal_relationships.statistics.generalized_hurst_h2_2_32` | 5 | slope of `log ⟨|r_τ|²⟩` vs `log τ` (canonical Hurst analogue) |
| `fractal_relationships.statistics.generalized_hurst_h3_2_32` | 5 | slope of `log ⟨|r_τ|³⟩` vs `log τ` |
| `fractal_relationships.statistics.multifractal_spread_h1_minus_h3_2_32` | 5 | `H(1) − H(3)` — zero for a monofractal, positive under multifractality |
| `fractal_relationships.statistics.wavelet_variance_scaling_exponent_1_4` | 4 | slope of `log Var[d_j]` vs `j` for Haar detail levels 1..4 |

### 5.3 Distribution — variance-ratio envelope (3 features)

Scale set `S₄ = {2, 4, 8, 16}` (4 scales). Individual `VR(τ)` values
are two-scale and thus intentionally **not** registered; only aggregates
that respect the Three-Scale Rule are exposed.

| Feature ID | `k_F` | Formula |
|---|---|---|
| `fractal_relationships.distribution.variance_ratio_max_deviation_from_unity_2_16` | 4 | `max_{τ ∈ S₄} |VR(τ) − 1|` |
| `fractal_relationships.distribution.variance_ratio_scale_std_2_16` | 4 | `std_{τ ∈ S₄}(VR(τ))` |
| `fractal_relationships.distribution.variance_ratio_signed_extreme_2_16` | 4 | signed VR at the τ achieving the max |·− 1| — `>0` = persistent across scales, `<0` = anti-persistent |

### 5.4 Regime — cross-window consistency & self-similarity (5 features)

Scale set for Hurst consistency `S₅ = {32, 64, 128}`; for Higuchi FD
`S₆ = {25, 50, 100}`. Both `|S₅| = |S₆| = 3`, exactly at the Three-Scale
threshold.

| Feature ID | `k_F` | Formula |
|---|---|---|
| `fractal_relationships.regime.hurst_cross_window_std_32_64_128` | 3 | `std({H_32, H_64, H_128})` |
| `fractal_relationships.regime.hurst_cross_window_range_32_64_128` | 3 | `max − min` of the same set |
| `fractal_relationships.regime.higuchi_fd_cross_window_std_25_50_100` | 3 | `std({FD_25, FD_50, FD_100})` |
| `fractal_relationships.regime.self_similarity_score` | ≥ 3 | mean over the module's own scaling-quality outputs (R² of variance-fit, R² of range-fit, `1 − |β − 0.5|`, `1 − hurst_cross_window_std_norm`, `1 − multifractal_spread_norm`) — a composite in `[0, 1]`. Formally: geometric mean of five sub-scores, each normalised so that a strictly self-similar Brownian input yields sub-score → 1. |
| `fractal_relationships.regime.self_similarity_flag` | ≥ 3 | `1` iff `self_similarity_score > 0.75` **and** every sub-input agrees in sign of deviation from its Brownian canonical value; else `0` |

### 5.5 Position — rolling percentile ranks over 60 bars (3 features)

| Feature ID | `k_F` | Formula |
|---|---|---|
| `fractal_relationships.position.variance_scaling_exponent_rank_60` | 6 | percentile rank of `variance_scaling_exponent_2_64` over 60 bars |
| `fractal_relationships.position.multifractal_spread_rank_60` | 5 | percentile rank of `multifractal_spread_h1_minus_h3_2_32` |
| `fractal_relationships.position.self_similarity_score_rank_60` | ≥ 3 | percentile rank of `self_similarity_score` over 60 bars |

### 5.6 Canonical values for reference processes

For every scaling-law feature this module registers, the table below
lists the value expected for three well-known reference processes.
These references anchor mathematical interpretation, guide golden-test
construction, and serve as a shared vocabulary for future L3 modules
reading these features as evidence.

**Reference processes:**
- **BM** — *Brownian motion* on price (i.i.d. Gaussian log-returns).
  The canonical monofractal, `H = 0.5`.
- **PP** — *Persistent* fractional-Brownian-like process, `H > 0.5`
  (positive long-range autocorrelation of returns; e.g., trending
  regime).
- **AP** — *Anti-persistent* process, `H < 0.5` (negative long-range
  autocorrelation; e.g., mean-reverting regime).

| Feature ID | BM (H=0.5) | PP (H>0.5) | AP (H<0.5) |
|---|---|---|---|
| `geometry.variance_scaling_exponent_2_64` | ≈ **1.0** (exact for i.i.d.) | > 1 (super-diffusive) | < 1 (sub-diffusive) |
| `geometry.variance_scaling_r2_2_64` | ≈ **1.0** (perfect power law) | ≈ 1.0 (if truly self-similar) | ≈ 1.0 (if truly self-similar) |
| `geometry.range_scaling_exponent_5_80` | ≈ **0.5** (Brownian range ∝ √τ) | > 0.5 | < 0.5 |
| `geometry.range_scaling_r2_5_80` | ≈ **1.0** | ≈ 1.0 | ≈ 1.0 |
| `geometry.range_scaling_deviation_from_brownian_5_80` | ≈ **0** | `\|β − 0.5\| > 0` | `\|β − 0.5\| > 0` |
| `statistics.generalized_hurst_h1_2_32` | ≈ **0.5** | > 0.5 | < 0.5 |
| `statistics.generalized_hurst_h2_2_32` | ≈ **0.5** | > 0.5 | < 0.5 |
| `statistics.generalized_hurst_h3_2_32` | ≈ **0.5** | > 0.5 | < 0.5 |
| `statistics.multifractal_spread_h1_minus_h3_2_32` | ≈ **0** (monofractal) | ≈ 0 if truly monofractal PP; > 0 if multifractal | ≈ 0 if truly monofractal AP; > 0 if multifractal |
| `statistics.wavelet_variance_scaling_exponent_1_4` *(on log-return series)* | ≈ **0** (returns uncorrelated across scales) | > 0 (positive autocorrelation carries variance to coarser scales) | < 0 |
| `distribution.variance_ratio_max_deviation_from_unity_2_16` | ≈ **0** (`VR(τ) ≡ 1` under random-walk null) | > 0 | > 0 |
| `distribution.variance_ratio_scale_std_2_16` | ≈ **0** | > 0 | > 0 |
| `distribution.variance_ratio_signed_extreme_2_16` | ≈ **1** | > 1 (VR > 1 across scales) | < 1 (VR < 1 across scales) |
| `regime.hurst_cross_window_std_32_64_128` | ≈ **0** (all three estimates → 0.5) | ≈ 0 if truly stationary self-similar PP | ≈ 0 if truly stationary self-similar AP |
| `regime.hurst_cross_window_range_32_64_128` | ≈ **0** | ≈ 0 | ≈ 0 |
| `regime.higuchi_fd_cross_window_std_25_50_100` | ≈ **0** (Brownian FD ≈ 1.5 at every window) | ≈ 0 if scale-stationary | ≈ 0 if scale-stationary |
| `regime.self_similarity_score` | ≈ **1.0** (all sub-scores → 1 by construction) | close to 1.0 if PP is truly scale-invariant; drops as scale-inhomogeneity grows | same reasoning as PP |
| `regime.self_similarity_flag` | **1** | 1 if the process is scale-invariant *and* passes the score-threshold gate | 1 under the same conditions |

**How to read this table.**
- Values marked **bold** are analytical closed-form expectations that
  Brownian motion satisfies exactly (in expectation) and that anchor
  the corresponding golden test in §8.
- The BM column is the mathematical *null hypothesis* against which the
  module is calibrated. Every feature's normalisation choice targets
  "= 1" or "= 0" for BM so composites are interpretable.
- PP and AP columns describe *directions* of deviation. Note the
  crucial architectural point: **self-similarity itself does not
  require Brownian-ness.** A pure fractional Brownian motion with
  `H ≠ 0.5` is still self-similar; `self_similarity_score` remains
  high; only the *scaling exponents themselves* move away from their
  Brownian anchor. This distinction is what allows L3 (future) to
  discriminate between "no trend, no memory" (BM) and "persistent
  trend, still self-similar" (PP) — both are internally consistent
  scaling regimes, and only their exponents identify which.
- The BM canonical values become **explicit test targets in §8** —
  every golden test that ships with the module tests a Brownian input
  against its canonical BM value.

**Consequence for future golden tests.** Follow-up work in v0.8+ may
add PP-specific and AP-specific goldens using
`fractional_brownian_motion(H=0.7)` and `H=0.3` synthetic inputs to
check the directional predictions of the PP and AP columns above.
These are not required for this ship (Book 1 Ch. 9 minimum is met by
the 6 BM-anchored goldens in §8) but are named here as follow-up work.

---



- **`fractal_relationships`**: 5 + 5 + 3 + 5 + 3 = **21 features**, 5 Perspectives.
- **L1 additions**: 2 (`hurst_32`, `higuchi_fd_25`).
- **Grand-total Registry after this ship**: `642 + 21 + 2 = 665 features` (L1 = 519, L2 = 146).
- Feature counts are **not targeted** per project-owner directive — they follow from mathematical completeness under the Three-Scale Rule.

---

## 6. Why Layer 1 cannot answer this question

L1 measurements are single-scale, single-methodology statements about
the market. Every existing L1 feature — including the multi-window
Hurst/FD/DFA — is `M(w=W)` for one `W` at a time. The question of
this module is **not** "what is `M(W)`" but **"how does `M` depend on
`W`?"** — a question about the *function* `M(·)`, not any of its
individual evaluations.

Formally:

- `hurst_rs(close, 64)` at time `t` is L1 — one measurement, one scale.
- `hurst_rs(close, 128)` at time `t` is L1 — a different measurement.
- `std({hurst_rs(·, 32), hurst_rs(·, 64), hurst_rs(·, 128)})` is a
  **relationship between three L1 measurements**. It is not a
  measurement of the market; it is a measurement of the *scale-stability
  of an L1 measurement*. Book 1 Ch. 5 places such quantities at L2.

Same reasoning for the scaling exponents: `α` in `Var[r_τ] ∝ τ^α`
cannot be computed with a single τ (or two). It is a **relationship**
across the whole scale set.

---

## 7. Why it belongs specifically in Layer 2 (and not L1 or L3)

- **Not L1.** No feature is a direct measurement of price, return, or
  volatility at a single scale. Every output requires ≥ 3 inputs at
  distinct scales.
- **Not L3.** L3 (Market Understanding) is *interpretation*: the market
  is exhausted, the market is accumulating, the regime has flipped. No
  feature here says "regime broke" or "market is efficient". Feature IDs
  are formula-descriptive (see DEC-009).
- **L2 explicitly.** Book 1 Ch. 5 lists **"Fractal Relationships"** by
  name under Layer 2 exemplars, alongside Momentum-of-Trend, Trend
  Relationships, Compression/Expansion, Market Structure, Swing
  Dynamics, Relative Strength. This module carries the exact name.

---

## 8. Golden tests (analytical, closed-form)

All golden tests use synthetic inputs for which the answer is derivable
in closed form or is asymptotic. Minimum ≥ 1 per module (Book 1 Ch. 9);
this module ships with **6**:

| Test | Rationale |
|---|---|
| `test_fr_variance_scaling_of_brownian_is_one` | Simulated i.i.d. Gaussian returns → `Var[r_τ] = τ σ²` → `variance_scaling_exponent_2_64 → 1.0` (within tolerance). |
| `test_fr_multifractal_spread_of_monofractal_is_near_zero` | Same monofractal Brownian input → `H(1) ≈ H(2) ≈ H(3)` → `multifractal_spread_h1_minus_h3` ≈ 0 (below a small tolerance). |
| `test_fr_variance_ratio_of_random_walk_max_deviation_is_small` | Same monofractal input → `VR(τ)` clusters near 1 → `variance_ratio_max_deviation_from_unity_2_16 < 0.5` (loose, but Brownian-consistent). |
| `test_fr_hurst_cross_window_std_bounds` | Output is a std of at most 3 real numbers each bounded in `[0, 1]` (Hurst) → the std lies in `[0, 0.5]` at every finite bar. |
| `test_fr_self_similarity_score_bounds` | Composite is a mean of quantities in `[0, 1]` → output ∈ `[0, 1]` at every finite bar. |
| `test_fr_self_similarity_flag_is_binary` | Flag ∈ `{0, 1}` (integer-valued) at every finite bar. |

Plus a **module purity assertion** in `backend/tests/backend_test.py`
mirroring the pattern used for `trend_relationships` and
`momentum_of_trend`:

- `test_fractal_relationships_no_direct_ohlcv` — grep the module
  source; assert zero `df["open" | "high" | "low" | "close" | "volume"]`
  substrings, and count `l1_series(` occurrences ≥ number of registered
  features.
- `test_fractal_relationships_three_scale_rule` — for every registered
  feature, assert `len(f.params["scales"]) ≥ 3` (or the equivalent
  scale-list key documented in the module's own registration helper).

After this ship: golden count `30 → 36` (30 existing + 6 new).

---

## 9. Decision-Engine integration plan (details in sibling doc)

Preview — full analysis lives in `FRACTAL_RELATIONSHIPS_DE_REVIEW.md`
per DEC-012.

- **New signal · `FractalCoherence` (L2, direction-neutral).**
  Reads exclusively `fractal_relationships.*` — same lane-clean pattern
  as `Entropy` and `Structure`.
- **Direction: always 0.** Project-owner directive: `FractalCoherence`
  is a confidence-modulator, not a directional peer. It will not
  influence position sizing or risk this ship; that decision is
  revisited once multiple L2 modules are producing evidence in
  production (v0.8+).
- **Strength: `self_similarity_score` ∈ [0, 1].**
- **Confidence:** `self_similarity_score` scaled to `[0.30, 1.00]`; +15%
  bonus if `self_similarity_flag == 1` (capped at 1.0).
- **Evidence rows:** 5 features (`self_similarity_score`,
  `self_similarity_flag`, `variance_scaling_exponent_2_64`,
  `multifractal_spread_h1_minus_h3_2_32`,
  `variance_ratio_max_deviation_from_unity_2_16`).
- **Weight budget:** `FractalCoherence = 0.03` (first-ship weight; small
  because direction-neutral). Redistribution: `Entropy 0.03 → 0.02`
  (−0.01), `Structure 0.05 → 0.03` (−0.02) — both are pre-existing
  direction-neutral confidence-modulators, so the direction-neutral
  budget stays balanced and directional weights are untouched. Sum
  remains **1.00 exactly**.

**Point-10 preview:** Signals ✅, Weight Learner ✅ (free-inclusion),
Confidence ✅ (its primary role), Explanations ✅ (free), Analogues ⏸
(deferred to v0.8 versioned z-space bump), Position Sizing ⏸ (owner
directive: not yet), Risk ⏸ (same), Recommendation Quality ✅ (adds
scale-invariance evidence no other signal supplies).

---

## 10. Non-goals

- **No temporal derivatives of scaling exponents.** "How does the
  variance-scaling exponent evolve over time?" is a legitimate
  question, but it is the *`momentum_of_trend`* class of question
  applied to an L2 quantity. If ever needed, it belongs in a future
  `fractal_dynamics` module, not here.
- **No behavioural interpretations.** "The market is efficient",
  "long memory has broken", "the regime has flipped" — all are L3
  concepts. This module refuses to encode any of them in a feature ID.
  L3 modules will read these features as *evidence*, and will
  themselves be responsible for the interpretation.
- **No two-scale-only features.** Enforced by the Three-Scale Rule
  (§2). `slope_ratio_20_50`, `slope_20_50_agreement`, etc. belong in
  `trend_relationships` and are intentionally not replicated here.
- **No pairwise cross-symbol similarity.** That is `relative_strength`
  (already shipped v0.6).
- **No signal-level directional recommendation.** The DE signal
  `FractalCoherence` is direction-neutral by explicit owner directive
  and this spec commits to that.

---

## 11. Pushback / risks called out

1. **Multi-scale Hurst / FD prerequisites in L1.** The two additive
   registrations (`hurst_32`, `higuchi_fd_25`) touch L1. They are
   *additive*, use existing engines, and follow the exact same
   registration pattern as `hurst_64/128` and `higuchi_fd_50/100`.
   Book-1 risk: none (formula-descriptive, no new math, no new
   interpretive concept). Docs, tests, and CHANGELOG entries are all
   updated in the same commit. Rejected alternative: computing these
   values inside the L2 module without registering them — rejected on
   Registry-as-source-of-truth grounds (Book 1 Ch. 8: "Registration is
   the moment at which a feature becomes real").
2. **Computational cost.** Rolling `.apply` with a log-log OLS fit at
   `W = 128` over `|S| = 6` scales is `O(N · W · |S|) ≈ O(768 N)`. For
   `N = 1000` bars this is ~1e6 ops per feature; with 21 features the
   worst-case is ~2e7 ops per compute call. Measured against the
   existing bench (compute of the 12-module snapshot takes ~800 ms on
   this container), the incremental cost is acceptable. Mitigations
   available if needed: (a) share the intermediate per-τ variance
   series across features that use the same scale set; (b) cache
   inside `df.attrs`. Both are behind-the-scenes optimisations
   invisible to the Registry.
3. **Numerical stability at short warm-up.** All estimators return
   `NaN` while inside the largest scale's warm-up window (`W = 128` for
   variance-family; `W = 256` for wavelet). This is normal and matches
   the existing convention of `price.geometry.hurst_128` (NaN for the
   first 128 bars). No feature "leaks" a value before its warm-up is
   complete.
4. **Overlap risk with `compression_expansion`.** The existing
   `compression_expansion` module measures the *ratio* of short-window
   volatility to long-window volatility — a **two-scale** quantity.
   The Three-Scale Rule prevents `fractal_relationships` from replaying
   that computation. The families here are all `≥ 3` scales and
   answer a strictly larger question (does variance follow a *power*
   law of scale, not just: is short-scale variance smaller than
   long-scale variance).
5. **Interpretive-name discipline.** Every draft ID went through a
   naming pass. An earlier draft used `fractal_coherence_score` /
   `fractal_coherence_flag`; the project-owner review flagged
   "coherence" as leaning toward interpretation. Renamed to
   `self_similarity_score` / `self_similarity_flag` — names that
   describe the exact mathematical property being measured (whether
   the process satisfies `X(τ) ∝ τ^H` across the whole scale set) and
   carry no market-state judgement. The L5 signal remains named
   `FractalCoherence` because the *signal* is a user-facing
   interpretation of the underlying mathematics, and signal names may
   be interpretive per DEC-009.

---

## 12. Forward-compatibility with Layer 3

This module is written with the following L3 consumers in mind
(per project-owner directive). All are legitimate L3 concepts and
must not leak into this module's feature IDs. The mapping below is
**advisory only** — it documents which of *this module's* outputs will
naturally serve as evidence for which L3 concept, so the L3 design
does not require re-architecting `fractal_relationships`.

| L3 concept (future) | This module's evidence |
|---|---|
| Regime persistence | Low `hurst_cross_window_std` + high `self_similarity_score` → the persistence regime is scale-invariant, i.e., not confined to a single lookback. |
| Regime transition | Sharp drop in `self_similarity_score`, or `variance_ratio_signed_extreme` crossing zero — signalled by L3 as a candidate transition boundary. |
| Trend continuation | `variance_scaling_exponent > 1` **and** `range_scaling_exponent > 0.5` **and** `self_similarity_flag == 1` — scale-consistent super-diffusion. |
| Trend exhaustion | `multifractal_spread` rising over time while `self_similarity_score` falling — L3 reads both as a joint "single-scale explanation is breaking down" signal. |
| Market complexity | `multifractal_spread_h1_minus_h3_2_32` directly. Large spread = heterogeneous scaling laws at different moment orders — the canonical multifractal signature. |
| Structural stability | `self_similarity_flag` directly; L3 aggregates it with other stability signals. |

**Design constraint honoured**: L3 will consume these features through
the same Registry-bridge pattern that L2 uses to consume L1 (design
tracked in the `L3_ACCESS_CONTRACT.md` doc, deferred to Session 8 per
main-agent recommendation). No feature in this module needs an L3-only
side-channel; all outputs are first-class Registry features accessible
by any layer.

---

## 13. Rollback plan

If any part of the module misbehaves after ship:

1. **Signal-only rollback** — set `FractalCoherence` weight to `0.0`
   in `SIGNAL_WEIGHTS`. The signal still fires and appears in
   evidence, contributes zero to the score. Reversible in seconds
   without a code change.
2. **Feature-level rollback** — remove `from ... import fractal_relationships`
   in `atlas_core/layers/l2_relationships/__init__.py`. The 21 module
   features vanish from the Registry; the two L1 additions
   (`hurst_32`, `higuchi_fd_25`) remain harmless (they are additional
   windows of an already-golden engine).
3. **Full rollback** — revert the version bump (v0.7.2 → v0.7.1).
   Zero DB-schema changes; recommendations continue to load.

Documented at commit time in the CHANGELOG entry.

---

## 14. Sign-off checklist (must be true when Phase 8 ends)

- [ ] `fractal_relationships.py` consumes L1 exclusively via
      `_l1_bridge.l1_series` (no `df["…"]` reads).
- [ ] Every registered feature carries `params["scales"]` with
      `len(scales) ≥ 3` (Three-Scale Rule).
- [ ] 6 new golden tests pass; 36/36 golden tests overall.
- [ ] 23/23 backend pytests pass; new module-purity assertion added.
- [ ] `SIGNAL_WEIGHTS` sums to 1.00 exactly (13 → 14 signals).
- [ ] `FractalCoherence` evidence rows contain only
      `fractal_relationships.*` IDs.
- [ ] Frontend header shows `v0.7.2 · L1+L2 · 665 FEATURES` (subject
      to final counts).
- [ ] `docs/CHANGELOG.md`, `PROJECT_CONTEXT.md`, `HANDOVER.md`,
      `ROADMAP.md`, `KNOWN_LIMITATIONS.md`, `ARCHITECTURE.md` all in
      sync.
- [ ] `docs/L2_SPECS/FRACTAL_RELATIONSHIPS_DE_REVIEW.md` present.
- [ ] `docs/ENGINES.md` and `docs/PERSPECTIVES.md` shipped alongside.

---

*Author: main agent — Session 7, Priority 3 (Phase 1).
Reviewed against Book 1 Ch. 5 (L2 exemplars — "Fractal Relationships"
is named verbatim), Ch. 6 (Invariants 6.3, 6.4, 6.5, 6.7),
Ch. 8 (Registry as single source of truth), Ch. 9 (validation gate),
Ch. 10 (engine-vs-module separation). Follows DEC-012 spec-first
workflow and DEC-006 upward-flow contract.*

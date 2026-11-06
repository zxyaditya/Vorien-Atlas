# L2 Module Specification — `momentum_of_trend`

> **Ship version:** v0.7.0-alpha (Session 7 · Priority 1).
> **Layer:** 2 (Relationships) — Book 1 Ch. 5.

---

## 1. Purpose

Measure how already-measured **trend properties** of the market evolve over time.
This is *not* price momentum. Price momentum lives at L1 (`price.motion.*`).
Here we take an **existing L1 trend measurement** — a linear-regression slope,
an ADX, an Aroon oscillator, a trend-intensity index — and study how *that
measurement* is itself changing. In Book-1 terms, this is the temporal
relationship of a trend measurement to itself.

---

## 2. Mathematical question

Given a Layer-1 trend measurement `T(t)` — where `T` is any registered feature
whose intrinsic property is "trendness" of price (slope, directional strength,
intensity) — quantify:

| Quantity                    | Formula                                       |
|-----------------------------|-----------------------------------------------|
| Velocity of trend           | `v_w(t) = (T(t) − T(t − w)) / w`              |
| Acceleration of trend       | `a_w(t) = v_w(t) − v_w(t − w)`                |
| Direction persistence       | consecutive-bar count of `sign(v_w) == sign(v_w[-1])` capped at `w` |
| Velocity stability          | `std_{k=w}(v_w)`                              |
| Velocity magnitude rank     | rolling percentile rank of `|v_w|` over `w`   |
| Cross-source velocity agreement | fraction of chosen sources whose `sign(v_w)` matches, per bar |

All quantities are computed **from a registered L1 series only**, via
`_l1_bridge.l1_series(df, feature_id)`. The module never re-implements a
trend measurement, never reads OHLCV directly.

---

## 3. Inputs

Consumed **only through the Registry** (Book 1 Invariant 6.4), via
`_l1_bridge.l1_series`:

| Symbol | Feature ID                          | What it measures                        |
|--------|-------------------------------------|-----------------------------------------|
| `S1`   | `price.motion.lr_slope_20`          | 20-bar linear-regression slope of close |
| `S2`   | `price.regime.adx_14`               | Wilder Directional Strength (14-bar)    |
| `S3`   | `price.regime.aroon_osc_14`         | Aroon Up − Aroon Down (14-bar)          |

Three orthogonal representations of "trendness". Rationale: LR-slope captures
raw magnitude and sign, ADX captures unsigned strength, Aroon-Osc captures
recent-high vs recent-low bias.

---

## 4. Outputs (registered features)

For each source `S ∈ {S1, S2, S3}` and each derivative window `w ∈ {10, 20}`:

| Feature ID                                                        | Perspective  | Formula                                     |
|-------------------------------------------------------------------|--------------|---------------------------------------------|
| `momentum_of_trend.motion.<src>_velocity_{w}`                     | Motion       | `v_w(S)`                                    |
| `momentum_of_trend.motion.<src>_acceleration_{w}`                 | Motion       | `v_w(v_w(S))`                               |
| `momentum_of_trend.statistics.<src>_velocity_std_{w}`             | Statistics   | `std_{k=w}(v_w(S))`                         |
| `momentum_of_trend.regime.<src>_direction_persistence_{w}`        | Regime       | consecutive bars with `sign(v_w)` unchanged |
| `momentum_of_trend.position.<src>_velocity_abs_rank_{w}`          | Position     | percentile rank of `|v_w|` over `w`         |

= 3 sources × 2 windows × 5 derivatives = **30 features**.

Plus two **Relative-perspective** cross-source alignment features at `w=20`:

| Feature ID                                                       | Perspective | Formula                                     |
|------------------------------------------------------------------|-------------|---------------------------------------------|
| `momentum_of_trend.relative.velocity_sign_agreement_20`          | Relative    | mean over `{S1,S2,S3}` of `1[sign(v_20) == mode_sign]` |
| `momentum_of_trend.relative.velocity_agreement_slope_adx_20`     | Relative    | `sign(v_20(S1)) * sign(v_20(S2))` (pairwise agreement) |

**Total: 32 features. Perspectives populated: Motion, Statistics, Regime, Position, Relative — 5 Perspectives.**

---

## 5. Why Layer 1 cannot answer this question

L1 modules measure the market. They can measure "what is the trend right
now" (`price.motion.lr_slope_20` already exists). They **cannot** measure
"how is the trend changing" without comparing two moments of a trend
measurement to each other — that comparison is a *relationship*, and Book 1
places relationships at L2. Formally:

- `lr_slope_20(t)` is a measurement (L1).
- `Δ_w lr_slope_20 = lr_slope_20(t) − lr_slope_20(t − w)` is a relationship
  between two L1 measurements at times `t` and `t − w`, which is not itself a
  new measurement of the market — it is a *statement about how a measurement
  evolves*.

Restating in Book-1 language: measurement precedes interpretation
(Invariant 6.5). Momentum-of-trend does not interpret the trend (it does not
say "trend is exhausted"); it measures the *relationship* between two
already-measured trend values. That is precisely Layer 2.

---

## 6. Why it belongs specifically in Layer 2

- Book 1 Ch. 5 lists **Momentum of Trend** verbatim under "Layer 2 —
  Relationships".
- The module answers a class of question of the form
  *"how does one measurement change with respect to itself over time?"* — the
  archetypal L2 relationship (temporal relationship of an L1 measurement).
- It does not produce a market state or a decision (that would be L3 or L5).
- It has no direct OHLCV dependency: every input is a Registry lookup.

---

## 7. Golden tests (analytical, closed-form)

| Test                                          | Rationale                                                                                 |
|-----------------------------------------------|-------------------------------------------------------------------------------------------|
| `test_mot_velocity_of_constant_slope_is_zero` | On a strictly linear close (`c = a + b·t`), `lr_slope_20` is constant → velocity ≈ 0.     |
| `test_mot_velocity_sign_flips_on_v_shape`     | On a V-shaped close (down then up), the slope crosses zero mid-series → sign of velocity of the slope must flip at least once. |
| `test_mot_direction_persistence_bounds`       | Direction-persistence output must be integer in `[0, w]`.                                 |
| `test_mot_velocity_sign_agreement_in_unit_interval` | `velocity_sign_agreement_20 ∈ [0, 1]` at every finite point.                        |

≥ 4 golden tests for one new module — comfortably above the ≥1 required by
Book 1 Ch. 9.

---

## 8. Decision Engine integration

Point-10 evaluation follows in `MOMENTUM_OF_TREND_DE_REVIEW.md`. Short
version: momentum_of_trend feeds a **new L2 signal `TrendMomentum`** in the
Decision Engine that reads 4 velocity/acceleration/persistence features and
outputs a directional strength. Rationale: the existing `Momentum` signal
reads L1 price-motion; it therefore cannot distinguish "price still rising
but trend weakening" from "price rising and trend accelerating". A
trend-of-trend signal completes the picture. Weight budget shifted from the
L1 `Momentum` signal.

---

## 9. Non-goals

- No prediction. No smoothing that constitutes interpretation.
- No cross-scale trend agreement (`slope_20` vs `slope_50`) — that is
  **Trend Relationships** (Session 7 Priority 2) and lives in a different
  module by design.
- No fractal self-similarity of trends — that is **Fractal Relationships**
  (Priority 3).

---

*Author: main agent — Session 7, Priority 1.
Reviewed against Book 1 Ch. 5 (Layer 2 exemplars: Momentum, Trend, Swing
Dynamics, Relative Strength, Market Structure, Compression and Expansion,
Fractal Relationships), Ch. 6 (Invariants 6.3, 6.4, 6.5), Ch. 9 (validation
gate).*

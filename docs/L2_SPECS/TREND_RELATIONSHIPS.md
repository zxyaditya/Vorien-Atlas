# L2 Module Specification — `trend_relationships`

> **Ship version:** v0.7.1 (Session 7 · Priority 2).
> **Layer:** 2 (Relationships) — Book 1 Ch. 5.

---

## 1. Purpose

Measure how **multiple independent trend measurements agree, disagree,
reinforce or contradict each other** across different methodologies and
timescales.

This module is complementary to `momentum_of_trend` (v0.7.0). The
distinction — stated by the project owner at the start of Session 7 P2 and
enforced here — is:

| Module | Answers | Kind of relationship |
|---|---|---|
| `momentum_of_trend` | *"How does a trend measurement evolve over time?"* | **Temporal** — same measurement at `t` vs `t − k` |
| `trend_relationships` | *"How do multiple independent trend measurements agree, disagree, reinforce or contradict each other across different methodologies and timescales?"* | **Cross-measurement / cross-scale** — different measurements or different scales at the same `t` |

There is zero mathematical overlap between the two modules: the temporal
axis is exclusive to `momentum_of_trend`, and the cross-source / cross-scale
axis is exclusive to `trend_relationships`.

---

## 2. Mathematical question

Given a family of L1 trend measurements `{T_i}` — each a rolling function of
price that summarises trend along some axis (magnitude, direction, strength,
quality) — quantify:

| Quantity | Formula sketch |
|---|---|
| Cross-scale sign agreement | `sign(T_20) * sign(T_50) ∈ {-1, 0, +1}` |
| Cross-methodology sign agreement | `sign(lr_slope_20) * sign(ema_slope_20)`; and the same for aroon_osc_14 |
| Directional consensus score | `mean_{T_i ∈ signed} 1[sign(T_i) == mode(sign(T_i))]  ∈ [0, 1]` |
| Directional consensus sign | the majority sign itself `∈ {-1, 0, +1}` |
| EMA-cascade alignment | fraction of adjacent pairs in `{EMA10, EMA20, EMA50, EMA100}` correctly ordered for "up" *or* "down" cascade `∈ [0, 1]` |
| EMA-cascade signed | `+1` if fully up-ordered, `−1` if fully down-ordered, else fractional |
| EMA span normalized | `(EMA10 − EMA100) / close`  (magnitude of cascade, signed) |
| Slope cross-scale ratio | `lr_slope_20 / lr_slope_50` (safe divide) |
| Slope cross-scale divergence | `(lr_slope_20 − lr_slope_50) / (|lr_slope_50| + ε)` |
| Strength-methodology correlation | rolling corr over 60 bars of `ADX_14` and `lr_r2_20` |
| Consensus rolling mean | rolling mean of consensus_score over 60 bars |
| Consensus percentile rank | rolling percentile rank over 60 bars |

All quantities are computed **from registered L1 series only**, via
`_l1_bridge.l1_series(df, feature_id)`. The module never re-implements a
trend measurement, never reads OHLCV columns directly. This is Invariant 6.4
of Book 1 and is enforced by pytest (see the module purity assertion added
alongside this ship).

---

## 3. Inputs (all via Registry)

Direct measurements (all `price.*` L1 features already shipped):

| Symbol | Feature ID | Family | What it measures |
|---|---|---|---|
| Slope short  | `price.motion.lr_slope_20`      | LR-slope    | Signed magnitude of trend at 20-bar scale |
| Slope long   | `price.motion.lr_slope_50`      | LR-slope    | Signed magnitude of trend at 50-bar scale |
| EMA-slope    | `price.motion.ema_slope_20`     | EMA-slope   | Alt. trend direction proxy (methodology B) |
| Aroon        | `price.regime.aroon_osc_14`     | Aroon       | Recent-high vs recent-low bias (methodology C) |
| ADX          | `price.regime.adx_14`           | ADX         | Unsigned directional strength (methodology D) |
| R² short     | `price.geometry.lr_r2_20`       | LR-R²       | Trend quality / straightness at 20-bar scale |
| EMA levels   | `price.motion.ema_10/20/50/100` | EMA levels  | Cascade ordering |
| Close        | via EMA-100 and EMA-10 already in Registry (used for the *normalized* span; the raw `close` used only implicitly through registered EMAs — no direct df["close"] read) |

**Trend methodologies represented: 4** — LR-slope, EMA-slope, Aroon,
ADX. Book 1 §5 explicitly recommends multi-methodology confirmation:
"a trend confirmed by multiple independent measurements is stronger evidence
than the same trend measured once."

---

## 4. Outputs (registered features)

Total: **20 features · 5 Perspectives** (Relative, Geometry, Regime,
Statistics, Position).

### 4.1 Relative — cross-scale / cross-methodology agreement (7 features)

| Feature ID | Formula |
|---|---|
| `trend_relationships.relative.slope_cross_scale_agreement_20_50` | `sign(lr_slope_20) · sign(lr_slope_50) ∈ {-1, 0, +1}` |
| `trend_relationships.relative.slope_lr_ema_agreement_20`         | `sign(lr_slope_20) · sign(ema_slope_20)` |
| `trend_relationships.relative.slope_aroon_agreement_20_14`       | `sign(lr_slope_20) · sign(aroon_osc_14)` |
| `trend_relationships.relative.slope_ratio_20_50`                 | safe-div `lr_slope_20 / lr_slope_50` (clipped to ±10) |
| `trend_relationships.relative.slope_divergence_20_50`            | `(lr_slope_20 − lr_slope_50) / (|lr_slope_50| + ε)` |
| `trend_relationships.relative.short_long_slope_sign_diff_20_50`  | `sign(lr_slope_20) − sign(lr_slope_50) ∈ {-2, −1, 0, +1, +2}` |
| `trend_relationships.relative.methodology_sign_span_20`          | `max_i(sign(T_i)) − min_i(sign(T_i))` across `{lr_slope_20, ema_slope_20, aroon_osc_14}` — 0 iff all sources agree in sign |

### 4.2 Geometry — EMA-cascade ordering (4 features)

| Feature ID | Formula |
|---|---|
| `trend_relationships.geometry.ema_cascade_score_10_20_50_100`  | fraction of adjacent pairs in `(EMA10, EMA20, EMA50, EMA100)` correctly ordered for up-cascade — output in `[0, 1]` |
| `trend_relationships.geometry.ema_cascade_signed_10_20_50_100` | `+1` if fully up-ordered (EMA10 > EMA20 > EMA50 > EMA100), `−1` if fully down-ordered, `frac(up_pairs − down_pairs)/3` otherwise |
| `trend_relationships.geometry.ema_cascade_score_10_20_50`      | same as above but on 3 EMAs |
| `trend_relationships.geometry.ema_span_normalized_10_100`      | `(EMA10 − EMA100) / EMA100` — signed magnitude of cascade span |

### 4.3 Regime — multi-source directional consensus (3 features)

| Feature ID | Formula |
|---|---|
| `trend_relationships.regime.directional_consensus_score_20` | `mean_{T_i} 1[sign(T_i) == mode]` across signed sources `{lr_slope_20, ema_slope_20, aroon_osc_14}` — in `[1/3, 1]` |
| `trend_relationships.regime.directional_consensus_sign_20`  | the modal sign itself `∈ {−1, 0, +1}` |
| `trend_relationships.regime.all_sources_agree_flag_20`      | `1` iff every signed source has the same non-zero sign at bar `t`, else `0` |

### 4.4 Statistics — cross-methodology strength & rolling consensus (3 features)

| Feature ID | Formula |
|---|---|
| `trend_relationships.statistics.adx_r2_agreement_60`             | rolling Pearson correlation of `ADX_14` and `lr_r2_20` over 60 bars — do "strength" methodologies co-move? |
| `trend_relationships.statistics.consensus_score_rolling_mean_60` | 60-bar rolling mean of `directional_consensus_score_20` |
| `trend_relationships.statistics.consensus_score_rolling_std_60`  | 60-bar rolling std of `directional_consensus_score_20` — stability of trend clarity |

### 4.5 Position — rolling percentile rank (3 features)

| Feature ID | Formula |
|---|---|
| `trend_relationships.position.consensus_score_rank_60`   | percentile rank of `directional_consensus_score_20` over 60 bars |
| `trend_relationships.position.ema_cascade_score_rank_60` | percentile rank of `ema_cascade_score_10_20_50_100` over 60 bars |
| `trend_relationships.position.slope_ratio_abs_rank_60`   | percentile rank of `|slope_ratio_20_50|` over 60 bars |

---

## 5. Why Layer 1 cannot answer this question

L1 measurements are single-methodology, single-scale statements about the
market. `lr_slope_20` and `ema_slope_20` are independent measurements; both
are L1. But **the question "do these two measurements agree?" cannot be
phrased without both being on the table simultaneously.** By definition,
"agreement between measurements" is a relationship between measurements —
which is Book 1 Ch. 5's operational definition of Layer 2.

Formally:
- `sign(lr_slope_20)` alone is L1 (it is a monotonic function of an L1 series).
- `sign(lr_slope_20) · sign(ema_slope_20)` is a *product of two L1 signals*.
  The product is not a measurement of the market; it is a measurement of
  the coherence between two measurements of the market. That is a
  relationship, and therefore L2.

The same reasoning applies to cross-scale features:
`sign(lr_slope_20) · sign(lr_slope_50)` compares the same methodology at
two different windows — again a relationship, again L2.

---

## 6. Why it belongs specifically in Layer 2 (and not L1 or L3)

- **Not L1**: no feature here is a direct measurement of price. Every
  input is itself an L1 measurement; every output is a function of ≥ 2 L1
  inputs. Book 1 Ch. 5: "L2 features answer *how* measurements interact."
- **Not L3**: L3 is Behaviour — what the market *is doing* (accumulating,
  distributing, exhausting). This module does not classify behaviour; it
  reports the geometry of agreement between measurements. No feature says
  "trend is exhausted" or "market is accumulating". Book 1 Ch. 5 places
  agreement/coherence explicitly at L2.
- **Book-1 exemplars for L2** in Ch. 5 include "Momentum of Trend, Trend
  Relationships, Fractal Relationships, Compression and Expansion, Market
  Structure, Swing Dynamics, Relative Strength." **Trend Relationships is
  named verbatim.** This module carries that name.

---

## 7. Golden tests (analytical, closed-form)

| Test | Rationale |
|---|---|
| `test_tr_slope_agreement_on_pure_trend` | On a strictly linear close, `lr_slope_20`, `lr_slope_50`, and `ema_slope_20` all have positive slope for a rising line → `directional_consensus_score_20` equals `1.0` at every finite bar. |
| `test_tr_ema_cascade_score_bounds_and_full_up` | On a strictly increasing close, EMA10 > EMA20 > EMA50 > EMA100 → `ema_cascade_score_10_20_50_100` == 1.0 and `ema_cascade_signed_10_20_50_100` == +1 at the tail. Also assert the score is always in `[0, 1]`. |
| `test_tr_cross_scale_agreement_on_v_shape` | A V-shaped close reverses direction mid-series; the sign of `lr_slope_20` flips before `lr_slope_50` does, so `slope_cross_scale_agreement_20_50` must contain at least one `-1` value in the transition band. |
| `test_tr_methodology_sign_span_bounds` | `methodology_sign_span_20 ∈ {0, 1, 2}` at every finite bar (three signed sources; max span between −1 and +1 is 2). |
| `test_tr_consensus_score_range` | `directional_consensus_score_20 ∈ [1/3, 1.0]` at every finite bar (with 3 sources, minimum agreement rate is 1 source out of 3 = 0.333…). |

5 goldens — well above the ≥1 required by Book 1 Ch. 9.

---

## 8. Decision-Engine integration plan (details in DE-review doc)

Preview:

- **New signal · `TrendAlignment` (L2)** — 13 signals total after this ship.
- Reads exclusively `trend_relationships.*` features.
- Direction from `directional_consensus_sign_20`.
- Strength from `ema_cascade_score_10_20_50_100`.
- Confidence anchored on `directional_consensus_score_20` × `all_sources_agree_flag_20` (perfect agreement is the highest-confidence regime; partial agreement produces moderate confidence; disagreement produces low confidence).

**Weight budget**: `TrendAlignment` gets `0.05` — first-ship weight, observe
before promoting. Redistribute from Trend (0.16 → 0.14) and Momentum
(0.12 → 0.11) → sum unchanged. See sibling review doc.

**Point-10 assessment** (full doc: `TREND_RELATIONSHIPS_DE_REVIEW.md`):
Signals ✅, Weight Learner ✅ (free), Confidence ✅, Explanations ✅ (free),
Analogues ⏸ (deferred, versioned space), Position Sizing ⏸ (this module
does not measure risk), Risk ⏸ (same), Recommendation Quality ✅ (adds
independent evidence).

---

## 9. Non-goals

- No *temporal* derivative of trend — that is `momentum_of_trend` (Priority 1, shipped).
- No self-similarity across scales in vol/range — that is `fractal_relationships` (Priority 3, next).
- No pairwise similarity between different symbols — that is `relative_strength` (already shipped v0.6).
- No behavioural interpretation ("trend exhaustion", "impulse", …) — those are L3 and are out of scope.

---

## 10. Pushback / risks called out

- **Risk of overlap with `market_structure`**: `market_structure` uses
  swings/HH/LL/BOS; it does not use slopes, EMAs, ADX or Aroon. No overlap.
- **Risk of `slope_ratio_20_50` blowing up when the long-scale slope
  crosses zero**: mitigated by (a) `ε = 1e−12`, (b) clipping the ratio
  to `[−10, +10]`. Documented in the module docstring; asserted in the
  `test_tr_methodology_sign_span_bounds` golden.
- **Risk that "all_sources_agree_flag" is interpretive**: renamed from an
  earlier draft "trend_coherence_flag" precisely to avoid interpretation;
  the current name states only the mathematical event (all sources have
  the same non-zero sign at bar `t`).

---

*Author: main agent — Session 7, Priority 2.  Reviewed against Book 1
Ch. 5 (L2 exemplars — "Trend Relationships" is named verbatim), Ch. 6
(Invariants 6.3, 6.4, 6.5), Ch. 9 (validation gate).*

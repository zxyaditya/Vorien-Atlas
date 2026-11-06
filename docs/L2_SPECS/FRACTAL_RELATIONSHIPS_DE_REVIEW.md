# Decision-Engine Review — `fractal_relationships`

> **Point-10 review** for the L2 module shipped in Session 7 Priority 3.
> Follows the workflow established in `MOMENTUM_OF_TREND_DE_REVIEW.md`
> and `TREND_RELATIONSHIPS_DE_REVIEW.md`, codified in DEC-012.

---

## 1. Recommendation summary

| Consumer | Verdict | What we do this ship |
|---|---|---|
| **Signals** | ✅ Integrate | Add a new `FractalCoherence` signal (**direction-neutral**, L2). Reads exclusively `fractal_relationships.*`. |
| **Weight Learning** | ✅ Free | `SIGNAL_FUNCS` already drives the walk-forward logistic fit; the new signal is included automatically. |
| **Historical Analogues** | ⏸ Defer | Analogue z-space is versioned. Two concrete candidates to add at the v0.8 schema bump are documented below. |
| **Confidence** | ✅ Direct — primary role | `self_similarity_score` is, by construction, a scale-invariance confidence quantity. The signal's primary role is confidence-shaping. |
| **Position Sizing** | ⏸ Defer (project-owner directive) | Not integrated this ship. Revisit once multiple L2 modules have generated evidence in production. |
| **Risk** | ⏸ Defer (project-owner directive) | Same as sizing. `multifractal_spread` is a candidate future risk input (regime-uncertainty proxy) but stays out of this ship. |
| **Explanations** | ✅ Free | Existing deterministic evidence templating handles the new signal without changes. |
| **Recommendation Quality** | ✅ Direct | Adds an evidence dimension no other signal supplies: whether the market's statistical laws are **scale-consistent** across at least three observation scales. Complements — does not duplicate — `Trend`, `TrendMomentum`, `TrendAlignment`, `Structure`, `Entropy`. |

---

## 2. New signal · `FractalCoherence` (L2, direction-neutral)

### Purpose

Answer *"Do the market's statistical laws (variance-scaling, generalised
Hurst, variance-ratio, R/S Hurst, fractal dimension, range-scaling,
wavelet-variance) all describe the same self-similar process across
scales — and if so, how cleanly?"* This is a **meta-confidence
question** about the internal consistency of Atlas's own multi-scale
measurements. No other signal in the engine asks it.

### Reads (all L2 · `fractal_relationships.*`, five features)

| Feature | Role |
|---|---|
| `fractal_relationships.regime.self_similarity_score` | Primary confidence quantity (∈ [0, 1], mapped to [0.30, 1.00]) |
| `fractal_relationships.regime.self_similarity_flag` | Confidence bonus (+15% if flag == 1, capped at 1.0) |
| `fractal_relationships.geometry.variance_scaling_exponent_2_64` | Contextual evidence for evidence rows — direction of scale-diffusion |
| `fractal_relationships.statistics.multifractal_spread_h1_minus_h3_2_32` | Contextual evidence — degree of multifractality |
| `fractal_relationships.distribution.variance_ratio_max_deviation_from_unity_2_16` | Contextual evidence — envelope of variance-ratio departure |

Lane-clean by construction: every read is a `fractal_relationships.*`
feature ID. Per-signal purity assertion in
`backend/tests/backend_test.py` will enforce this at every future ship.

### Direction — always 0 (owner directive)

```
d = 0   # direction-neutral by explicit project-owner decision, Session 7 P3.
```

Rationale (verbatim from the owner's Phase-1 approval): *"Treat
FractalCoherence primarily as a direction-neutral confidence and
structural-consistency signal. Do not allow it to directly influence
position sizing or risk management yet."*

Architectural consequence: this signal contributes zero to the voter's
`directional_score`; its weight enters only the confidence and
strength aggregation paths (identical treatment to `Entropy` and
`Volatility`).

### Strength

```
strength = self_similarity_score            # ∈ [0, 1]
```

Strength is *how* self-similar the market currently is. High = the
scaling laws hold cleanly across ≥ 3 scales; low = single-scale
statistics fail to extrapolate to nearby scales.

### Confidence

```
score = self_similarity_score               # ∈ [0, 1]
flag  = self_similarity_flag                # ∈ {0, 1}

# Map [0, 1] score → [0.30, 1.00] confidence
conf = 0.30 + 0.70 * score

# Unanimity bonus: +15% if the flag fires, capped at 1.0
if flag >= 0.5:
    conf = min(1.0, conf + 0.15)
```

Semantics: a market whose statistical laws are internally consistent
across scales earns more of the voter's confidence budget. A market
that reports contradictory scaling exponents at different windows
earns less. This is the archetypal role of a direction-neutral
confidence signal.

### Evidence rows (deterministic templating)

The deterministic explainer will produce five bullets, one per feature
in the reads list. Their `argument` strings will state the *value* and
its *deviation from the Brownian canonical* (see spec §5.6), never a
market-state interpretation. Examples:

- `self_similarity_score = 0.82 (≥ 0.75 threshold; scale-invariant)`
- `variance_scaling_exponent = 1.12 (Brownian = 1.0; slightly super-diffusive)`
- `multifractal_spread = 0.04 (Brownian = 0; near-monofractal)`

The `weight` field on each evidence row will use `strength × weight`
so the explainer's "top evidence" pick chooses the row that most
strongly contributed to the signal's confidence lift.

---

## 3. Weight budget

### Change to `SIGNAL_WEIGHTS` (voter.py)

Current (v0.7.1, 13 signals, sum = 1.00 exactly):

```
Trend            0.14
Momentum         0.11
TrendMomentum    0.03
TrendAlignment   0.05
Regime           0.12
Structure        0.05   ← reduces
MeanReversion    0.06
Volume           0.10
Volatility       0.03
Liquidity        0.03
Microstructure   0.10
MarketStructure  0.15
Entropy          0.03   ← reduces
                 ————
                 1.00
```

Proposed (v0.7.2, 14 signals, sum = 1.00 exactly):

```
Trend            0.14
Momentum         0.11
TrendMomentum    0.03
TrendAlignment   0.05
Regime           0.12
Structure        0.03   ← was 0.05, redistributes 0.02
MeanReversion    0.06
Volume           0.10
Volatility       0.03
Liquidity        0.03
Microstructure   0.10
MarketStructure  0.15
Entropy          0.02   ← was 0.03, redistributes 0.01
FractalCoherence 0.03   ← NEW (0.02 from Structure + 0.01 from Entropy)
                 ————
                 1.00
```

### Rationale for source of the 0.03 budget

`FractalCoherence` is a **direction-neutral confidence-modulator**.
The clean choice is to draw its budget exclusively from other
direction-neutral confidence-modulators, not from directional signals.
The current voter has three such: `Structure` (Hurst / choppiness /
fractal-dimension based, 0.05), `Entropy` (spectral/permutation
entropy, 0.03), `Volatility` (0.03), `Liquidity` (0.03).

- `Structure 0.05 → 0.03` (−0.02): `Structure` reads *single-scale*
  Hurst / FD / choppiness. `FractalCoherence` reads the *cross-scale
  consistency* of those same estimators. The two are complementary,
  not redundant — but `FractalCoherence` subsumes half of what
  `Structure` was carrying alone (namely: is the single-scale estimate
  trustworthy?). A 0.02 shift is warranted.
- `Entropy 0.03 → 0.02` (−0.01): a small give-back from the smallest
  confidence-modulator. Entropy remains a distinct signal (spectral
  entropy of returns), separately worth its own weight.

Directional weights (`Trend`, `Momentum`, `TrendMomentum`,
`TrendAlignment`, `Regime`, `MeanReversion`, `Volume`, `Microstructure`,
`MarketStructure`) are **untouched**. This preserves the current
directional balance intact while opening a small confidence-shaping
slot for the new signal.

### Weight-sum invariant

`sum(SIGNAL_WEIGHTS.values()) == 1.00` (within 1e-9). Enforced by an
assertion in `backend/tests/backend_test.py` that already ships and
will simply be re-run against the new 14-signal map.

### Rollback

Setting `FractalCoherence = 0.0` and restoring `Structure = 0.05`,
`Entropy = 0.03` returns the voter to its v0.7.1 configuration
without a code change. The new signal continues to fire and appear in
evidence, contributing zero to the score.

---

## 4. Explicit non-integrations (with rationale)

### Historical Analogues — deferred

`decision_engine/analogues.py` uses a fixed 19-dimensional z-space of
L1-heavy features. Adding L2 dimensions requires a versioned schema
bump (planned v0.8 per `KNOWN_LIMITATIONS.md` §3 and the identical
deferral in `TREND_RELATIONSHIPS_DE_REVIEW.md`).

**Two concrete candidates to add at the v0.8 schema bump:**

1. `fractal_relationships.regime.self_similarity_score` — the module's
   headline composite; captures the entire scale-invariance status of
   the current bar in one number.
2. `fractal_relationships.statistics.multifractal_spread_h1_minus_h3_2_32`
   — captures the *multifractal* dimension of similarity, which
   `self_similarity_score` alone does not.

These two additions would raise the analogue z-space from 19 → 21
dimensions. The candidate list from prior modules
(`directional_consensus_score_20`, `ema_cascade_signed_10_20_50_100`,
`velocity_of_slope from momentum_of_trend`) remains open. All are
tracked in a single v0.8 schema-bump plan.

### Position Sizing — deferred (owner directive)

Project-owner directive at Session 7 Priority 3 kickoff:
*"Do not allow it to directly influence position sizing or risk
management yet. Let's first understand its behaviour in production."*
Fully honoured. `decision_engine/risk.py` and the sizing formula
remain unchanged.

The theoretical case for future integration exists:
`self_similarity_score` and `multifractal_spread` are natural
regime-uncertainty proxies (low similarity ≈ scale-inhomogeneous
market ≈ ambiguous regime). But the owner's rule stands: observe
first, integrate later, and only under weight-learner or backtest
evidence.

### Risk — deferred (owner directive, same reasoning)

Not touched. `assess_risk()` continues to read `volatility.*`,
`price.regime.hurst_*`, `price.regime.choppiness_*`, and the ATR/VaR/
Ulcer/Hurst quantitative risk battery. Zero change.

### Weight Learner — free (no config change needed)

`decision_engine/weight_learner.py` iterates over `SIGNAL_FUNCS`
directly. Adding one entry to that list is enough. The walk-forward
logistic fit will start including `FractalCoherence` from the next
`/api/decision/learned_weights` call. The learner is univariate on
`direction × strength` per signal; because our direction is 0, the
contribution `direction × strength = 0` — which is *exactly* what we
want for a direction-neutral signal (the learner will assign it
`β ≈ 0` — no weight — reflecting that it does not directionally
predict returns). This is the correct behaviour for a
confidence-modulator inside a directionally-scored learner.

### Explanations — free

`decision_engine/explainer.py` is deterministic templating. It reads
each signal's `evidence[*].argument` string and picks the highest-weight
row. The new signal's evidence rows will be picked up automatically.
No template change required.

### Recommendation Quality — direct improvement

Adding this signal answers a question that was previously unanswerable
inside the Decision Engine: *"Should I trust the single-scale evidence
that all other signals are showing me?"* Precedent from earlier
sessions (v0.5 removing `Volatility`'s leaked reads from `price.*`;
v0.7.1 orthogonalising `TrendAlignment` against `Trend`) proved that
adding a signal answering a genuinely-new question improves
recommendation quality more than reweighting existing signals ever
does. `FractalCoherence` sits in that same design lineage.

---

## 5. Book-1 compliance verification

Applied to the new signal in this ship:

| Check | Result |
|---|---|
| Signal reads from exactly one Atlas module? | ✅ Yes — every entry in the reads list is `fractal_relationships.*`. Enforced by a per-signal purity assertion in the regression suite. |
| No L5 concept inside `atlas_core/`? | ✅ Yes — the signal lives in `decision_engine/signals.py`. `fractal_relationships` inside `atlas_core/` never reads a signal, never has a "score", never has a "flag" that is anything other than mathematical. |
| No feature-ID interpretive names? | ✅ Yes — after the Phase-1 rename (`self_similarity_*` replacing `fractal_coherence_*`), every feature ID in the module is formula-descriptive per DEC-009. The **signal name** `FractalCoherence` is L5 and permitted to be interpretive. |
| Weight-sum still 1.00 exactly? | ✅ Yes — see §3. |
| Rollback plan documented? | ✅ Yes — §3 (signal weight → 0) and spec §13 (feature-level or full-version rollback). |

---

## 6. Sign-off

- Voter total weight after this ship: **1.00 exactly**.
- Existing 13 signals: **all preserved**. Only 2 have weight
  adjustments (`Structure` −0.02, `Entropy` −0.01), well within the
  ±0.02 per-signal cap this project respects.
- Regression: `TestDecisionRecommendV07` (or the v0.7.2-renamed
  successor) will expect **14 signals** and the new `FractalCoherence`
  name. Per-signal purity assertion for `FractalCoherence` evidence
  will assert every evidence row's `fid` starts with
  `fractal_relationships.`.
- Book 1 compliance: the new signal consumes L2 only (upward flow);
  no L1 math re-implemented; no L5 code inside `atlas_core/`;
  `fractal_relationships` code-audit confirms zero direct OHLCV reads.

*Author: main agent, Session 7 Priority 3, Phase 2.
Reviewer: repository. Awaits Phase 3 (implementation) approval before
any code is written.*

# Layer 3 — Market Understanding — Mathematical Specification

> Version: v0.8.0 (Session 8 milestone) · Book 1 Ch. 5.
>
> This spec is the single overarching contract for **all L3 modules**.
> Every L3 module conforms to the state grammar defined in §3 and the
> access contract defined in §2. Per-module mathematical detail lives
> inline in the code (in the same style as `market_structure.py`
> registrations), because L3 modules are structurally uniform — they
> differ only in which L2 relationships they compose.

---

## 1. Book 1 anchor

Book 1 Ch. 5 defines Layer 3 as **Market Understanding**:

> *"Layer 3 answers: what market environment currently exists? Its
> content is contextual states built from many interacting
> relationships. Examples: Accumulation, Distribution, Trend
> Continuation, Trend Exhaustion, Range Formation, Breakout
> Environment, Mean Reversion Environment, Liquidity Sweeps, Market
> Regimes. Its outputs are contextual interpretations of interacting
> relationships."*

Book 1 Ch. 8 confirms: *"A 'Range Formation' or 'Trend Exhaustion' flag
belongs to L3 — contextual interpretation of L2 relationships."*

L3 is the **first layer where interpretation is permitted** (Book 1
Principle I). L1 measures; L2 relates; **L3 interprets**. L4 will
compress and encode; L5 will decide.

---

## 2. Access contract (DEC-014)

Information flows upward (Book 1 Invariant 6.4). L3 features access
lower layers **exclusively** through a parallel bridge:

```
atlas_core/layers/l3_market_understanding/_layer_bridge.py
  l1_series(df, feature_id)                   → pd.Series
  l2_series(df, feature_id, context=None)     → pd.Series
```

- **`l1_series`** — identical semantics to `l2_relationships._l1_bridge.l1_series`. Provided at the L3 layer so caches do not couple across layers.
- **`l2_series`** — computes an L2 feature on demand. Honours `df.attrs["_atlas_context"]` (DEC-007) when the target L2 feature requires peer data. Returns an all-NaN series with the correct index if the L2 feature cannot compute (soft-fail; matches DEC-007 discipline).
- **Cache key**: `(id(df), feature_id)`. Flushed by the orchestrator on entry and exit of every `compute_features` call (matches DEC-011).
- **No direct OHLCV access**: L3 modules must never read `df["close"]`, `df["high"]`, etc. Enforced by a registered pytest.

L3 does **not** import from `decision_engine/` or from a hypothetical
L4/L5 (Book 1 Invariant 5). L3 imports from `atlas_core.engines` only
for the state-kernel primitives (§3).

---

## 3. State grammar (DEC-015)

Every L3 feature is one of exactly six *shapes*. Each state family
publishes the full set:

| Shape | Perspective | Range | Meaning |
|---|---|---|---|
| `score` | position | [0, 1] | Continuous strength of a state at bar *t* |
| `flag` | regime | {0, 1} | Discrete on/off after hysteresis |
| `duration` | motion | ℕ | Consecutive bars the flag has been on |
| `transition` | motion | {−1, 0, +1} | +1 on entry bar, −1 on exit bar, 0 otherwise |
| `confidence` | statistics | [0, 1] | Agreement across the evidence set |
| `active_code` | regime | ℤ ≥ 0 | Winner-take-all state code per family (0 = none) |

The state kernel (`_state_kernel.py`) provides the primitives that
produce these shapes from evidence:

```python
weighted_score(evidence, weights)      → pd.Series in [0, 1]
hysteresis_flag(score, on, off)        → pd.Series in {0, 1}
duration(flag)                         → pd.Series in ℕ
transition(flag)                       → pd.Series in {−1, 0, +1}
agreement_confidence(signs)            → pd.Series in [0, 1]
winner_take_all(scores_dict)           → dict[state_name → flag], + active_code
zscore_clip(series, lookback, clip=3)  → normalised in [0, 1]
sigmoid(series, gain=1.0)              → in [0, 1]
```

These primitives are **not engines yet** (Book 1 Ch. 10 discovery
discipline). They live inside `l3_market_understanding` until an
identical need is proven in L4. If L4 needs them, we promote to
`engines/state.py`.

### Winner-take-all invariant

Within a state family that publishes an `active_code`, at most one
`flag` is 1 at any bar *t*. Enforced by:
- Runtime: `winner_take_all` picks the argmax score; ties broken by
  family-defined priority order documented per module.
- Validation Framework: the new property gate `mutual_exclusivity`
  (v0.8.0) certifies this against canonical fixtures.

---

## 4. Module hierarchy (v0.8.0)

Five modules ship in the L3 milestone, mapped 1-to-1 to Book 1's L3
exemplar families:

| Module | States | Winner-take-all? | Direction meaning |
|---|---|---|---|
| `trend_state` | trend_continuation · trend_exhaustion · trend_reversal | Yes | Signed by the underlying trend polarity |
| `range_state` | range_formation · breakout_environment · range_expansion | Yes | Direction-neutral |
| `participation_state` | accumulation · distribution · mean_reversion | Yes | +1 accum / −1 dist / 0 MR |
| `liquidity_state` | sweep_up · sweep_down · liquidity_neutral | Yes | Sweep-up ⇒ bearish exhaustion, Sweep-down ⇒ bullish exhaustion |
| `market_regime` | trending_quiet · trending_volatile · ranging_quiet · ranging_volatile | Yes | Direction-neutral, structural |

Every module publishes:
- One `score.<state>` per state (perspective: `Position`).
- One `regime.<state>_flag` per state (perspective: `Regime`).
- One `motion.<state>_duration` per state (perspective: `Motion`).
- One `motion.<state>_transition` per state (perspective: `Motion`).
- One `statistics.<state>_confidence` per state (perspective: `Statistics`).
- One `regime.active_state_code` at the module level.
- One `statistics.active_state_confidence` at the module level.

Feature-count budget per module: 5 shapes × 3 states + 2 module-level = 17 features → ~85 L3 features across the milestone.

---

## 5. Naming discipline

- L3 IDs use interpretive vocabulary (approved by Book 1 Ch. 5).
- `<module>.<perspective>.<state>_<shape>` — e.g. `trend_state.position.trend_exhaustion_score`.
- Module-level: `<module>.<perspective>.active_state_<code|confidence>`.
- No L1/L2 lookalikes: `state`, `regime`, `phase`, `environment`, `sweep` are L3-only tokens.

---

## 6. Mathematical composition (per family)

Each module's `_compose_evidence(df)` reads the specific L2 (occasionally L1) feature IDs it needs via `l2_series` / `l1_series`, then hands them to `weighted_score` with per-state weight vectors. The weights are hand-authored — this is **not** learned; learning is L5 (Book 1 Inv-5.6).

### 6.1 `trend_state`

Evidence:
- L2 `trend_relationships.regime.directional_consensus_score_20` (agreement of trend measures)
- L2 `trend_relationships.geometry.ema_cascade_score_10_20_50_100`
- L2 `momentum_of_trend.motion.lr_slope_20_velocity_20` (trend acceleration)
- L2 `momentum_of_trend.motion.adx_14_velocity_20`
- L1 `price.geometry.hurst_64` (persistence anchor — allowed as an L1 anchor)

States:
- `trend_continuation` — high consensus **and** positive acceleration **and** Hurst > 0.5.
- `trend_exhaustion` — high consensus **but** decelerating (negative velocity of slope) **and** Hurst approaching 0.5.
- `trend_reversal` — consensus flipping (sign change), transient state on the transition bar.

### 6.2 `range_state`

Evidence:
- L2 `compression_expansion.expansion.short_long_ratio` (present at L1 as `volatility.expansion.short_long_ratio`; also mirrored)
- L2 `compression_expansion.regime.compression_flag_20`
- L1 `price.geometry.straightness_50` (low straightness ⇒ ranging)
- L1 `price.regime.choppiness_14` (high ⇒ ranging)
- L2 `market_structure.regime.structure_regime_k5` (0 ⇒ range-bound)

States:
- `range_formation` — low expansion, high choppiness, near-zero structure regime.
- `breakout_environment` — compression flag on **and** structure change happening (BOS flag).
- `range_expansion` — expansion ratio > 1 **and** ADX still low.

### 6.3 `participation_state`

Evidence:
- L1 `volume.regime.pv_confirmation_20`
- L1 `volume.regime.signed_ema_20`
- L2 `market_structure.motion.bos_k5` (structural break sign)
- L2 `momentum_of_trend.motion.lr_slope_20_velocity_20` (whether price is rising / falling)
- L1 `volume.position.pct_rank_100`

States:
- `accumulation` — rising volume, sideways-to-up price velocity, positive PV confirmation.
- `distribution` — rising volume, sideways-to-down price velocity, negative PV confirmation.
- `mean_reversion` — z-score extreme (from L1 `price.statistics.zscore_20`) with weak PV confirmation.

### 6.4 `liquidity_state`

Evidence:
- L2 `market_structure.motion.bos_k5` (recent break)
- L1 `price.magnitude.high` extrema vs prior pivot (via `market_structure` pivot values)
- L1 `microstructure.expansion.execution_imbalance_20`
- L1 `microstructure.geometry.wick_difference_ratio` (wick asymmetry marks sweeps)

States:
- `sweep_up` — new local high beyond a pivot **and** upper wick dominant (rejection).
- `sweep_down` — new local low beyond a pivot **and** lower wick dominant (rejection).
- `liquidity_neutral` — neither sweep active.

Direction interpretation (in DE): sweep_up = bearish (upside stop-hunt), sweep_down = bullish (downside stop-hunt).

### 6.5 `market_regime`

Evidence:
- L1 `price.regime.adx_14` (trending strength)
- L1 `price.regime.choppiness_14` (ranging strength)
- L1 `volatility.regime.tercile_200` (quiet / volatile)
- L2 `trend_relationships.regime.directional_consensus_score_20`

Four regimes (winner-take-all):
- `trending_quiet` — ADX high, choppiness low, tercile in {1, 2}, consensus high.
- `trending_volatile` — ADX high, tercile = 3.
- `ranging_quiet` — choppiness high, tercile in {1, 2}.
- `ranging_volatile` — choppiness high, tercile = 3.

Ties are broken by the module-defined priority order: trending_quiet > trending_volatile > ranging_quiet > ranging_volatile.

---

## 7. Validation contract

Every L3 feature registers with `FeatureValidation(bridge="l3", ...)`. Coverage:

- **Universal gates** (all L3 features): `determinism`, `length_invariance`, `no_future_leakage`, `nan_input_behavior`, `degenerate_constant`.
- **Property gates** (declared per feature):
  - `bounded[0,1]` on every `score` and `confidence` feature.
  - `bounded[0,1]` (as {0,1}) on every `flag` feature.
  - **New at v0.8.0: `mutual_exclusivity`** — for every state family that publishes `active_state_code`, at any bar t at most one `flag_<state>` = 1.
- **Registry-wide gates**: `unique_formula_hash` (SHA-1) already applies. `no_duplicate_values` monitors L3 like L1/L2.
- **Golden identities** (declared): each module ships ≥ 1 analytical golden — e.g. `trend_state`: pure Brownian input ⇒ `trend_continuation_score` < 0.5 (Hurst ≈ 0.5, no directional persistence).

---

## 8. Decision Engine integration

Five new DE signals ship in the L3 milestone (one per module):

| Signal | Direction | Strength driver | Confidence driver |
|---|---|---|---|
| `TrendState` | polarity of trend consensus | active_state_score (of continuation) | active_state_confidence |
| `RangeState` | 0 (direction-neutral) | range_formation_score | active_state_confidence |
| `ParticipationState` | +1 if accumulation active, −1 if distribution active, 0 if MR | active_state_score | active_state_confidence |
| `LiquidityState` | +1 if sweep_down active, −1 if sweep_up active, 0 otherwise | max(sweep_up_score, sweep_down_score) | active_state_confidence |
| `RegimeState` | 0 (direction-neutral) | 1 − (uncertainty across the 4 regime scores) | active_state_confidence |

Signals live inside `decision_engine/signals.py` following the same shape as the existing 15 signals (name, direction, strength, confidence, evidence rows). No new voter changes — the voter aggregates 20 signals with the same weight-normalisation logic (uniform 1/N default, learned optional).

Total DE signals after v0.8.0: **20** (was 15).

---

## 9. Not in scope for v0.8.0

- **Learned state boundaries.** Hysteresis thresholds are hand-authored. Any adaptive threshold logic that trains on price is L5, not L3.
- **State-transition Markov models.** Book 1 places these at L4 (Representation).
- **Cross-timeframe state agreement.** L4 concern (meta-features).
- **State-conditioned voter weights in the DE.** Roadmap for v0.9+.

---

*Author: main agent, Session 8 milestone. Reviewed against Book 1 Ch. 5 & Ch. 8. See DEC-014 (L3 access contract) and DEC-015 (state kernel primitives).*

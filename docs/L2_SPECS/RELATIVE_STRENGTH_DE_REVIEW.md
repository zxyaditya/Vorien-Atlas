# Decision-Engine Review — `relative_strength`

> **Point-10 review** for the L2 module made frontend-visible in
> Session 7 Priority 4. Follows the workflow established in
> `MOMENTUM_OF_TREND_DE_REVIEW.md`, `TREND_RELATIONSHIPS_DE_REVIEW.md`,
> and `FRACTAL_RELATIONSHIPS_DE_REVIEW.md`, codified by DEC-012.

---

## 1. Recommendation summary

| Consumer | Verdict | What we do this ship |
|---|---|---|
| **Signals** | ✅ Integrate | Add a new `RelativeStrength` signal (**direction-neutral**, L2). Reads exclusively `relative_strength.*`. |
| **Weight Learning** | ✅ Free | `SIGNAL_FUNCS` already drives the walk-forward logistic fit; the new signal is included automatically. Its `direction × strength` term is always 0 (direction-neutral by construction) — so the learner will assign |β| ≈ 0. See §4 for the honest interpretation. |
| **Historical Analogues** | ⏸ Defer | Analogue z-space is versioned. RS features require peer alignment at every historical bar; adding them today would either break reproducibility of stored recommendations or require the peer to be stored per-recommendation. Concrete candidates + schema-bump plan below. |
| **Confidence** | ✅ Direct — primary role | The signal's whole purpose is confidence-shaping: `corr_50` and `cointegration_resid_std_100` tell the voter how *reliable* the pair-comparison currently is. |
| **Position Sizing** | ⏸ Defer | RS is not a risk quantity. Injecting relative-return ratios into a sizing formula would be a semantic error. |
| **Risk** | ⏸ Defer | Same reasoning as sizing. `relvol_50` is a **relative** volatility ratio, not a tail-risk measurement — the risk engine's ATR%/VaR/ES battery is the correct home for absolute risk quantities. |
| **Explanations** | ✅ Free | Deterministic templating picks up the new signal's `evidence` rows automatically. No template code change. |
| **Recommendation Quality** | ✅ Direct | Answers a question no other signal answers: *"How does this asset behave relative to a chosen benchmark?"* Adds a confidence dimension complementary to `Structure` (single-scale) and `FractalCoherence` (multi-scale internal consistency). |

---

## 2. New signal · `RelativeStrength` (L2, direction-neutral)

### Purpose

Answer *"Is the target behaving strongly or weakly relative to its
chosen benchmark, and how reliable is that comparison right now?"*

The signal is **direction-neutral by explicit project-owner directive**
(Session 7 P4 review): outperforming a benchmark does not automatically
imply LONG. Both assets can fall together and the target can still
"outperform" by falling less. Relative strength is *comparative*
information about the market state, not a directional trade recommendation.

### Reads (all L2 · `relative_strength.*`, five features)

| Feature | Role in signal |
|---|---|
| `relative_strength.magnitude.rs_20` | Short-window comparative return ratio; primary strength quantity |
| `relative_strength.magnitude.rs_50` | Medium-window comparative return ratio; corroborates or contradicts the short window |
| `relative_strength.statistics.corr_50` | Reliability modulator — high correlation ⇒ tighter pair ⇒ higher confidence |
| `relative_strength.expansion.relvol_50` | Contextual evidence — which side is more volatile right now |
| `relative_strength.entropy.cointegration_resid_std_100` | Reliability modulator — tight cointegration ⇒ meaningful comparison ⇒ higher confidence |

Lane-clean by construction: every read is a `relative_strength.*`
feature ID. Per-signal purity assertion in
`backend/tests/backend_test.py` will enforce this at every future ship
(mirrors the pattern already established for `TrendMomentum`,
`TrendAlignment`, `FractalCoherence`).

### Direction — always 0 (owner directive)

```
d = 0   # direction-neutral by explicit project-owner decision, Session 7 P4.
```

Rationale (owner directive, verbatim): *"Relative strength is
fundamentally comparative. Outperforming another asset does not
necessarily imply that the target should be bought. Relative strength
should primarily improve our understanding of the market state, not
directly determine trade direction."*

Architectural consequence: this signal contributes zero to the voter's
`directional_score`; its weight enters only the confidence and strength
aggregation paths. Identical treatment to `FractalCoherence` (v0.7.2),
`Entropy`, `Volatility`, `Liquidity`, `Structure`.

### Strength

```
# combined_rs = mean of |rs_w - 1| across available windows, clipped
#   → 0 when rs is exactly at 1 (target and peer move identically)
#   → grows as target diverges from peer in either direction
delta_rs_20 = |rs_20 - 1|                       if available else 0
delta_rs_50 = |rs_50 - 1|                       if available else 0
strength    = clip01(0.5 * delta_rs_20 + 0.5 * delta_rs_50)
```

Strength answers *how much* comparative divergence exists (in either
direction). Zero when target and peer are moving identically; grows
symmetrically as they diverge. Semantics identical whether the target is
outperforming or underperforming — this is precisely what "direction-
neutral comparative strength" means.

### Confidence

```
corr50 = corr_50            (may be NaN)
coint  = cointegration_resid_std_100    (may be NaN)

# Base confidence from correlation magnitude — high |corr| ⇒ meaningful pair
if corr50 is None:
    conf = 0.30
else:
    conf = 0.30 + 0.60 * min(1.0, abs(corr50))     # ∈ [0.30, 0.90]

# Cointegration bonus — low residual std ⇒ tight structural relationship
if coint is not None and coint < 0.05:
    conf = min(1.0, conf + 0.10)                    # +10% bonus, capped at 1.0
```

Semantics:
- A pair whose returns are strongly correlated (|corr| high) makes the
  comparison meaningful — the voter can trust the strength number more.
- A pair whose log-price residual dispersion is tight (cointegration_
  resid_std low) means the two are structurally linked — bonus confidence.
- An unrelated pair (|corr| ≈ 0, high residual std) earns near-minimum
  confidence — signal fires but the voter should discount it.

This is the archetypal role of a direction-neutral confidence-modulator.

### Evidence rows (deterministic templating)

Up to five bullets, one per feature in the reads list. Every
`argument` string states the value and a **descriptive** interpretation
(never prescriptive):

- `rs_20 = 1.04 (target outperforming peer over 20 bars by ~4%)`
- `rs_50 = 0.97 (target underperforming peer over 50 bars by ~3%)`
- `corr_50 = 0.68 (moderately correlated pair — comparison meaningful)`
- `relvol_50 = 1.20 (target ~20% more volatile than peer)`
- `cointegration_resid_std_100 = 0.03 (tight structural pair)`

The `weight` field on each evidence row is set so the explainer's
"top evidence" pick lifts the most-informative row.

### Graceful degradation (no peer supplied)

When no peer context is attached, all five reads return NaN. The signal
returns `direction=0, strength=0.0, confidence=0.30, evidence=[]`. It
contributes zero to score and near-minimum to confidence — no runtime
error, no exception path, no user-facing message required.

---

## 3. Weight budget

### Change to `SIGNAL_WEIGHTS` (voter.py)

Current (v0.7.2, 14 signals, sum = 1.00 exactly):

```
Trend            0.14
Momentum         0.11
TrendMomentum    0.03
TrendAlignment   0.05
FractalCoherence 0.03
Regime           0.12
Structure        0.03
MeanReversion    0.06
Volume           0.10
Volatility       0.03
Liquidity        0.03
Microstructure   0.10
MarketStructure  0.15
Entropy          0.02
                 ————
                 1.00
```

Proposed (v0.7.3, 15 signals, sum = 1.00 exactly):

```
Trend            0.12   ← was 0.14, redistributes 0.02
Momentum         0.10   ← was 0.11, redistributes 0.01
TrendMomentum    0.03
TrendAlignment   0.05
FractalCoherence 0.03
Regime           0.12
Structure        0.03
MeanReversion    0.06
Volume           0.10
Volatility       0.03
Liquidity        0.03
Microstructure   0.10
MarketStructure  0.15
Entropy          0.02
RelativeStrength 0.03   ← NEW (0.02 from Trend + 0.01 from Momentum)
                 ————
                 1.00
```

### Rationale for source of the 0.03 budget

**Idealised rule** (Session 7 pattern for direction-neutral additions):
draw the budget exclusively from *other direction-neutral confidence-
modulators*. Applying that rule strictly here would mean taking from
`Structure (0.03)`, `Volatility (0.03)`, `Liquidity (0.03)`, `Entropy
(0.02)`, `FractalCoherence (0.03)`. Every one of those already carries
its first-ship weight and shouldn't be squeezed further without an
architectural reason to demote it.

**Adopted rule for this ship**: since RS is a *comparative-strength*
concept that partially overlaps with what `Trend` and `Momentum` measure
in absolute terms, taking a proportional slice from those two is
mathematically defensible:

- `Trend 0.14 → 0.12` (−0.02): `Trend` reads *absolute* directional bias
  from the target's own price. `RelativeStrength` adds the missing
  cross-series context ("versus what?"). Two-thirds of the RS budget
  drawn from `Trend` reflects that RS is more trend-like than momentum-
  like in what it measures.
- `Momentum 0.11 → 0.10` (−0.01): a small give-back from the second-
  largest directional-price signal. Momentum retains 0.10, still the
  fourth-largest weight overall.
- **`RelativeStrength +0.03`** — matching first-ship discipline
  established by `TrendMomentum` (v0.7), `TrendAlignment` (v0.7.1),
  `FractalCoherence` (v0.7.2).

**Directional weight totals**: `Trend + Momentum + TrendMomentum +
TrendAlignment + Regime + MeanReversion + Volume + Microstructure +
MarketStructure` was `0.86` and becomes `0.83`. The 0.03 shifts into
the direction-neutral confidence-modulator pool (which totals
`Structure + Volatility + Liquidity + Entropy + FractalCoherence +
RelativeStrength` = `0.03 + 0.03 + 0.03 + 0.02 + 0.03 + 0.03 = 0.17`).
The directional-versus-neutral balance moves from 0.86/0.14 to
0.83/0.17 — a small, deliberate lean toward confidence-shaping which is
exactly what a new direction-neutral signal is supposed to do.

### Weight-sum invariant

`sum(SIGNAL_WEIGHTS.values()) == 1.00` (within 1e-9). Enforced by the
existing assertion inside `TestDecisionRecommendV06::
test_recommend_manual_weights` and by a dedicated regression test.

### Rollback

Setting `RelativeStrength = 0.0` and restoring `Trend = 0.14`,
`Momentum = 0.11` returns the voter to its v0.7.2 configuration without
a code change. The new signal continues to fire and appear in evidence,
contributing zero to score and confidence.

---

## 4. Explicit non-integrations (with rationale)

### Historical Analogues — deferred

`decision_engine/analogues.py` uses a fixed 19-dimensional z-space of
L1-heavy features. Adding L2 dimensions requires a versioned schema
bump (v0.8 target per `KNOWN_LIMITATIONS.md §3`).

**Concrete candidate to add at the v0.8 schema bump:**

- `relative_strength.magnitude.rs_50` — the medium-window headline
  comparative-return quantity; captures the entire pair-strength status
  in one number.

This is a **conditional** candidate: including RS in the z-space only
makes sense if we also decide to store the peer choice alongside each
recommendation. That storage decision belongs to the same v0.8 schema
bump. Until then, RS stays out of the analogue space.

### Position Sizing — deferred

RS is a *relationship*, not a risk quantity. `decision_engine/risk.py`
and its sizing formula continue to read only `volatility.*`,
`price.regime.hurst_*`, `price.regime.choppiness_*`, and the
ATR/VaR/ES/Ulcer battery. Zero change.

### Risk — deferred

Same reasoning. `relvol_50` (target-σ / peer-σ) is a **ratio**, not an
absolute risk quantity. It surfaces in the signal's evidence row for
context but does not enter risk quantification.

### Weight Learner — free (no config change) — honest interpretation

`decision_engine/weight_learner.py` iterates over `SIGNAL_FUNCS`
directly. Adding one entry (`RelativeStrength`) is enough — the
walk-forward logistic fit will include it starting the next
`/api/decision/learned_weights` call.

**Honest caveat**: the learner is univariate on `direction × strength`
per signal. Because our direction is 0 by construction, that product is
always 0 for `RelativeStrength` — which means the learner will assign
`β ≈ 0`, i.e. no learned weight. This is the **correct** behaviour for a
direction-neutral signal inside a directionally-scored learner (the
learner is only measuring directional predictive value, which is
precisely what this signal disclaims). Coverage will also be 0
(direction is never non-zero).

**This is identical to the treatment of `FractalCoherence`, `Entropy`,
`Volatility`, `Liquidity`, and `Structure` in the same learner** — it's
a known and documented limitation of the learner's univariate design,
not a bug introduced by this signal. The general fix (an unsigned-
strength term in the learner for direction-neutral signals) is a
weight-learner refactor tracked in `KNOWN_LIMITATIONS.md §3` and
scheduled for v0.8 alongside regime-conditional weight learning.

**Weight-learner peer plumbing**: `learn_weights(df, ..., context=None)`
gets an optional context argument (see §5) so historical RS features
can populate against the chosen peer. Without a peer, RS features are
NaN across the historical window and `_historical_signal_matrix` records
0 for the RS column — the learner sees a zero-variance column, which
sklearn's `LogisticRegression` handles without error (β = 0).

### Explanations — free

`decision_engine/explainer.py` is deterministic templating. It reads
each signal's `evidence[*].argument` string and picks the highest-weight
row. The new signal's evidence rows will be picked up automatically.
No template change required.

### Recommendation Quality — direct improvement

Adds a question no other signal answers inside the Decision Engine.
Even in its first ship as a direction-neutral confidence-modulator, it
tells the voter *"how much comparative divergence exists, and how
trustworthy that comparison currently is."* Precedent from prior L2
signal additions (v0.7 `TrendMomentum`, v0.7.1 `TrendAlignment`, v0.7.2
`FractalCoherence`) shows that adding a signal that answers a
genuinely-new question improves recommendation quality more than
reweighting existing signals ever does.

---

## 5. Peer plumbing — API contract & data flow

### Backend

`RecommendRequest` (Pydantic) gains two optional fields, both nullable:

```python
class RecommendRequest(BaseModel):
    # ... existing fields ...
    peer_provider: Optional[str] = None
    peer_symbol: Optional[str] = None
```

When **both** are present (non-empty), `server.decision_recommend`:

1. Fetches the peer OHLCV via `fetch_smart(peer_provider, peer_symbol,
   interval, period, 500)` using the **same interval/period** as the
   target — critical for time-alignment.
2. Aligns to `df.index` via `peer_df = peer_df.reindex(df.index)`.
3. Passes `context={"peer": peer_df}` into `recommend(df,
   model_agreement=..., ..., context=context)`.

`recommend()` gets a new optional `context` argument (default `None`)
and threads it into `compute_all_signals(df, context=context)`.

`compute_all_signals(df, context=None)` gets a new optional `context`
argument and threads it into `compute_features(df, ids, context=context)`
— the pre-existing DEC-007 pathway. No new code required inside
`compute_features` itself.

`learn_weights(df, ..., context=None)` gets the same treatment so the
weight learner's `_historical_signal_matrix` can populate historical RS
features when a peer is chosen. Backward-compatible signature bump —
existing callers work unchanged.

### Feature values

`/api/features/values` gains two optional query params:

```
GET /api/features/values
  ?feature_id=relative_strength.magnitude.rs_20
  &provider=yahoo
  &symbol=AAPL
  &interval=1d
  &period=1y
  &peer_provider=yahoo         (optional)
  &peer_symbol=SPY             (optional)
```

When both peer params are present, the endpoint fetches and aligns the
peer as above and passes context into `compute_features`. Existing
callers unaffected — omitting the peer args preserves the single-symbol
behaviour byte-for-byte.

### Frontend

Decision-tab controls row gains a "Peer" `<select>` next to the Symbol
select. Options: all symbols in the current provider excluding the
target, plus a `— none —` sentinel that clears the peer selection.
When a peer is chosen, `POST /api/decision/recommend` includes
`peer_provider` and `peer_symbol`. When `— none —` is chosen, both
fields are omitted (or set to null).

A small **RS-vs-Peer mini-chart** is rendered above the Signal Breakdown
whenever a peer is selected, plotting `relative_strength.magnitude.rs_20`
with a reference line at `y = 1.0` (equilibrium).

Signal-Breakdown grid changes `grid-cols-7` → `grid-cols-5` (three rows
of five accommodates 15 signals cleanly).

---

## 6. Book-1 compliance verification

Applied to the new signal in this ship:

| Check | Result |
|---|---|
| Signal reads from exactly one Atlas module? | ✅ Yes — every entry in the reads list is `relative_strength.*`. Enforced by a per-signal purity assertion in the regression suite. |
| No L5 concept inside `atlas_core/`? | ✅ Yes — the signal lives in `decision_engine/signals.py`. The L2 `relative_strength` module contains no interpretation, no score, no flag beyond formula-descriptive outputs. |
| No feature-ID interpretive names? | ✅ Yes — every RS feature ID is formula-descriptive per DEC-009. The **signal name** `RelativeStrength` is L5 and permitted to be interpretive (as is `FractalCoherence`, `TrendAlignment`, etc.). |
| Multi-symbol context via the sanctioned pathway? | ✅ Yes — `context["peer"]` via `df.attrs["_atlas_context"]` per DEC-007. No side-channels, no globals. |
| Peer abstraction respects DEC-005 (L2/L4 boundary)? | ✅ Yes — single-reference-series only. Multi-peer aggregation is explicitly reserved for L4 (RELATIVE_STRENGTH.md §3 & §9). |
| Weight-sum still 1.00 exactly? | ✅ Yes — see §3. |
| Rollback plan documented? | ✅ Yes — §3 (signal weight → 0) and RELATIVE_STRENGTH.md §12 for the module-level rollback (already existed at v0.6). |

---

## 7. Sign-off

- Voter total weight after this ship: **1.00 exactly**.
- Existing 14 signals: **all preserved**. Only 2 have weight adjustments
  (`Trend −0.02`, `Momentum −0.01`), well within the ±0.02 per-signal
  cap this project respects.
- Regression: `TestDecisionRecommendV07` will expect **15 signals** and
  the new `RelativeStrength` name. Per-signal purity assertion for
  `RelativeStrength` evidence asserts every evidence row's
  `feature_id` starts with `relative_strength.`. New peer-plumbing
  regression tests verify the end-to-end context flow.
- Book 1 compliance: the new signal consumes L2 only (upward flow); no
  L1 math re-implemented; no L5 code inside `atlas_core/`; the peer
  abstraction respects the L2/L4 boundary at both the code and
  vocabulary level.

*Author: main agent, Session 7 Priority 4 · Phase 0.  Reviewer:
repository. Awaits Phase 1 (implementation) approval — already granted.*

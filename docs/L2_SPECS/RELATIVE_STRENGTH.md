# Relative Strength — L2 Module Specification

> **DEC-012 retrofit spec.** The `relative_strength` module was shipped
> at v0.6 before DEC-012 was adopted. This file is authored now (v0.7.3)
> so the module reaches the same specification-first standard the three
> Session-7 L2 modules already meet. The math is unchanged; this file
> documents it against the DEC-012 template so future sessions have a
> permanent artefact to audit against.

---

## 1. Purpose

Measure the target symbol's price behaviour **relative to a single
reference series** — a peer, an index, a sector proxy, or the market
itself — over one or more windows. The module answers *relationship*
questions between two independent L1 price measurements; it does **not**
interpret those relationships as trading decisions.

Non-interpretive by construction. All twelve features are formula-
descriptive per DEC-009. Interpretation of what "relatively strong"
means for a position is Layer-5 territory (Decision Engine).

## 2. Mathematical question

*"How does the target's price behaviour compare to a single reference
series over a chosen window — in return ratio, log-price spread,
co-movement, sensitivity, dispersion, lead/lag, and cointegration?"*

Governing axis: **pairwise cross-series relationship** between the
target's L1 close and one reference's L1 close.

## 3. Inputs

### Registry feature IDs (upward flow — Invariant 6.4)

| ID | Layer | Role |
|---|:-:|---|
| `price.magnitude.close` (via `_l1_bridge.l1_series`) | L1 | Target close series |

### Multi-symbol context (DEC-007)

The module reads the reference close series from
`df.attrs["_atlas_context"]["peer"]` — a `pd.DataFrame` with a `close`
column, aligned to `df.index`.

**Reserved context-key vocabulary** (locked in this spec to prevent
future misuse):

| Key | Status | Owner |
|---|:-:|---|
| `"peer"` | **In use** — a single reference `DataFrame` (peer / index / sector ETF / market proxy) | L2 `relative_strength` |
| `"basket"` | **Reserved for L4** — a `List[DataFrame]` of universe members | Future L4 module |
| `"universe"` | **Reserved for L4** — a `Dict[str, DataFrame]` keyed by symbol | Future L4 module |
| `"index_set"` | **Reserved for L4** — set of indices for market-regime work | Future L4 module |
| `"sector_set"` | **Reserved for L4** — sector-classification map | Future L4 module |

L2 `relative_strength` reads **only** `"peer"`. Any L4 module that
requires aggregation across a universe will introduce a new module and
use a new reserved key — never overload `"peer"`. This preserves DEC-005
(Cross-Asset stays at L4) at the vocabulary level.

**Soft-fail contract** (DEC-007 + existing code): when the context is
missing or contains no peer, every feature returns `NaN` for its full
length. Single-symbol callers see no failure — they simply see NaN in
the `relative_strength.*` columns. This is invariant across the module.

## 4. Outputs — the 12 features

All twelve features shipped in v0.6 are documented here at their current
formula-descriptive names. Every ID is unique in the Registry (silent
SHA-1 guardrail, DEC-003).

| ID | Perspective | Family | Formula | Params |
|---|:-:|:-:|---|---|
| `relative_strength.magnitude.rs_20` | Magnitude | relative_return | `(a_t/a_{t-20}) / (b_t/b_{t-20})` | window=20 |
| `relative_strength.magnitude.rs_50` | Magnitude | relative_return | `(a_t/a_{t-50}) / (b_t/b_{t-50})` | window=50 |
| `relative_strength.magnitude.rs_100` | Magnitude | relative_return | `(a_t/a_{t-100}) / (b_t/b_{t-100})` | window=100 |
| `relative_strength.geometry.log_spread` | Geometry | log_spread | `ln P_a − ln P_b` | — |
| `relative_strength.statistics.corr_20` | Statistics | correlation | `corr(r_a, r_b, w=20)` | window=20 |
| `relative_strength.statistics.corr_50` | Statistics | correlation | `corr(r_a, r_b, w=50)` | window=50 |
| `relative_strength.relative.beta_20` | Relative | beta | `cov(r_a, r_b) / var(r_b)` over w=20 | window=20 |
| `relative_strength.relative.beta_50` | Relative | beta | `cov(r_a, r_b) / var(r_b)` over w=50 | window=50 |
| `relative_strength.expansion.relvol_20` | Expansion | vol_ratio | `σ_a / σ_b` over w=20 | window=20 |
| `relative_strength.expansion.relvol_50` | Expansion | vol_ratio | `σ_a / σ_b` over w=50 | window=50 |
| `relative_strength.motion.leadership_50` | Motion | leadership | `argmax_{L∈[−3..+3]} |corr(a_t, b_{t−L})|` over w=50 | window=50, lags=±3 |
| `relative_strength.entropy.cointegration_resid_std_100` | Entropy | cointegration_residual | `std(resid(ln a ~ ln b))` over w=100 | window=100 |

Every feature reads the target close via `_l1_bridge.l1_series` (upward
flow) and the reference close via `context["peer"]["close"]`.

## 5. Why the layer below cannot answer this question

L1 measures **one series at a time**. It cannot express a relationship
between two independent series; that requires a comparison operation
which is by definition L2. A composite feature such as "AAPL beta vs
SPY over 50 bars" is not a measurement of AAPL alone or of SPY alone —
it is a relationship between the two. Placing it at L1 would violate
Invariant 6.1 ("every feature answers one mathematical question") and
would give AAPL price the semantics of "AAPL vs a chosen peer", which
is context-dependent and not a property of AAPL itself.

## 6. Why it belongs specifically to this layer

Book 1 Ch. 5 lists Relative Strength explicitly under **Layer 2 —
Relationships**. Book 1 also lists Cross-Asset (multi-peer, universe-
wide dispersion, cross-sectional ranking) under **Layer 4 —
Representation**. The mathematically defensible boundary between the
two is *cardinality of the reference*: one reference ⇒ L2 pairwise
relationship; a set ⇒ L4 aggregation.

`relative_strength` sits exactly at that boundary and only on the L2
side. This is codified by DEC-005 ("Book-1-strict Session 6: Market
Structure at L2, Cross-Asset deferred to L4, minimum Relative Strength
at L2") and by REJ-002 (rejection of Cross-Asset as an L1 module).

## 7. Golden tests

Existing (behaviour verified at v0.6 ship, still passing at v0.7.2):

- Feature registration silently blocks duplicate formulas (DEC-003
  guardrail, module-wide).
- Every feature returns NaN across the whole series when no peer
  context is provided (soft-fail contract, verified by the fact that
  `/api/decision/recommend` without a `peer_symbol` produces a
  fully-formed response with `relative_strength.*` = None).

Planned in this ship (v0.7.3):

- **`test_rs_identity_when_target_equals_peer`** — for a target
  synthetic series `a`, computing `relative_strength.magnitude.rs_20`
  and `relative_strength.statistics.corr_50` with `peer = a` should
  give `rs_20 ≡ 1.0` (up to numerical tolerance) and
  `corr_50 → 1.0`. Analytical, known-answer, module-purity anchor.

Bumps the Golden Test suite from 36 → **37**.

## 8. Decision-Engine integration plan (sketch)

Full detail lives in `RELATIVE_STRENGTH_DE_REVIEW.md` (sibling file).
Headlines:

- **New L5 signal `RelativeStrength` — direction-neutral** (owner
  directive, Session 7 P4). Reads five features exclusively from
  `relative_strength.*`. Contributes zero to the voter's
  `directional_score`; participates only in confidence shaping and
  evidence rows.
- **First-ship weight: 0.03.** Budget drawn *exclusively* from other
  direction-neutral confidence-modulators (Trend −0.02, Momentum −0.01)
  — see DE review §3 for the exact rationale. Directional weights are
  untouched.
- **Peer plumbing**: `RecommendRequest` gains optional
  `peer_provider` / `peer_symbol` fields (both strings, both nullable).
  When present, the backend fetches the peer OHLCV, aligns to the
  target's index, and passes `context={"peer": peer_df}` down through
  `recommend → compute_all_signals → compute_features`.
- **Analogues z-space**: **defer** — same reasoning as the three prior
  Session-7 DE reviews (versioned schema bump lives in v0.8).
- **Risk / sizing**: **defer** — RS is not a risk quantity; injecting
  it into sizing would be a semantic error.
- **Explainer / evidence rows**: **free** — deterministic templating
  already picks up new signals automatically.

## 9. Non-goals

Explicitly out of scope for this module, to prevent future scope creep:

- **Basket / universe / peer-set aggregation** — mean-basket, median-
  basket, cross-sectional ranks, leadership across a set, dispersion
  regimes. These are Layer 4 per Book 1 Ch. 5 and per DEC-005.
  If we need them, we create a new L4 module and a new reserved
  context key (see §3). We do **not** genericise `relative_strength`.
- **Index / sector / market as first-class semantic roles** — the
  module treats every reference series identically. If we want to
  differentiate "target vs sector benchmark" from "target vs peer
  stock", we do that in the Decision Engine (`RelativeStrength`
  signal's evidence text), not in the L2 math.
- **Automated peer selection** — the peer is chosen by the caller
  (frontend user picks a symbol). Auto-peer-detection is L4
  (universe-based) or L5 (heuristic) work, not this module's job.
- **Time-varying peer** — the peer DataFrame is a single reference
  DataFrame, held fixed for one compute call. Dynamic peer rotation
  belongs to a future L4 rotation module.
- **Direction interpretation** — RS features do not carry a
  "bullish/bearish" flag. Direction is a Layer-5 interpretation and
  lives inside the Decision Engine.

## 10. Pushback / risks called out

- **The single-peer abstraction is deliberate.** See the sibling
  architectural review in the v0.7.3 CHANGELOG entry and this spec's
  §3+§9. Any future proposal that would blur the L2/L4 boundary by
  passing a peer *set* through this module must first amend Book 1 or
  overturn DEC-005.
- **Direction-neutral by first-ship discipline.** Making RS
  directional in v1 would risk conflating "outperformed peer" with
  "buy the target". Book 1's principle that interpretation lives at
  L5 (and specifically at the signal-formula level, not the feature-ID
  level) is respected: we ship the signal direction-neutral this cycle;
  a directional variant may be reconsidered in a later ship if the
  weight learner or a backtest surfaces predictive value.

## 11. Cross-references

- Precedent modules (post-DEC-012, Session 7):
  `MOMENTUM_OF_TREND.md`, `TREND_RELATIONSHIPS.md`,
  `FRACTAL_RELATIONSHIPS.md`.
- Governing ADRs: DEC-005 (L2/L4 boundary), DEC-006 (`_l1_bridge`),
  DEC-007 (multi-symbol context via `df.attrs`), DEC-008 (engine
  reuse), DEC-009 (naming discipline), DEC-012 (spec-first).
- Sibling: `RELATIVE_STRENGTH_DE_REVIEW.md` — the Point-10 Decision-
  Engine analysis.

## 12. Change history

- **v0.6** — module shipped with 12 features. No spec at ship time
  (predates DEC-012).
- **v0.7.3** — this specification authored as a DEC-012 retrofit.
  No math change; documentation-only for the module itself. A new
  `RelativeStrength` L5 signal ships in the same version — its full
  design lives in `RELATIVE_STRENGTH_DE_REVIEW.md`.

*Author: main agent, Session 7 Priority 4 · Phase 0.  Reviewer:
repository. Awaits Phase 1 (implementation) approval — already granted.*

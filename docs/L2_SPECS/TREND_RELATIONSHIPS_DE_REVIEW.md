# Decision-Engine Review — `trend_relationships`

> **Point-10 review** for the L2 module shipped in Session 7 Priority 2.
> Follows the workflow established in `MOMENTUM_OF_TREND_DE_REVIEW.md` and
> codified in DEC-012.

---

## 1. Recommendation summary

| Consumer                | Verdict     | What we do this ship                                     |
|-------------------------|-------------|----------------------------------------------------------|
| **Signals**             | ✅ Integrate | Add a new `TrendAlignment` signal (directional, L2). Complements `Trend` (L1) and `TrendMomentum` (L2 temporal). |
| **Weight Learning**     | ✅ Free      | `SIGNAL_FUNCS` list already drives the walk-forward logistic fit — new signal is included automatically. |
| **Historical Analogues**| ⏸  Defer   | Analogue z-space is versioned. Add `directional_consensus_score_20` and `ema_cascade_signed_10_20_50_100` at v0.8 when we bump the schema. Documented as pending. |
| **Confidence**          | ✅ Direct    | Consensus + all-agree flag are, by construction, confidence variables. Signal confidence is anchored on them. |
| **Position Sizing**     | ⏸  Defer   | Sizing depends on risk (ATR%, Ulcer, Hurst). Trend agreement is directional, not a risk quantity. |
| **Risk**                | ⏸  Defer   | Same as sizing. However, we note a *future* use: when the cascade is broken (`ema_cascade_score ≈ 0.5`), sizing could optionally be dampened as a "regime uncertainty" penalty. Deferred to a full sizing rewrite in v0.8. |
| **Explanations**        | ✅ Free      | Existing evidence templating handles the new signal automatically. |
| **Recommendation Quality** | ✅ Direct | Adds genuinely independent evidence: it is the only signal in the engine whose entire raison d'être is "multiple methods agree/disagree". This is exactly the kind of evidence that Book 1 Ch. 5 calls for. |

---

## 2. New signal · `TrendAlignment` (L2)

### Purpose
Answer *"Do multiple independent trend measurements agree on direction
and, if so, how cleanly?"* — a question no other signal in the engine
currently answers directly.

### Reads (all L2 · `trend_relationships.*`)
| Feature                                                              | Role                                                        |
|----------------------------------------------------------------------|-------------------------------------------------------------|
| `trend_relationships.regime.directional_consensus_sign_20`           | Primary direction vote (dominant weight)                    |
| `trend_relationships.regime.directional_consensus_score_20`          | Confidence base (∈ [1/3, 1], mapped to [0.3, 1.0])          |
| `trend_relationships.regime.all_sources_agree_flag_20`               | Confidence multiplier bonus (unanimity → +20%)              |
| `trend_relationships.geometry.ema_cascade_signed_10_20_50_100`       | Strength contributor (cleanliness of cascade, ∈ [-1, +1])   |
| `trend_relationships.geometry.ema_cascade_score_10_20_50_100`        | Additional strength contributor (fraction of ordered pairs) |

### Formula (pseudocode)
```
cons_sign   = tr.regime.directional_consensus_sign_20         # ∈ {-1, 0, +1}
cons_score  = tr.regime.directional_consensus_score_20        # ∈ [1/3, 1]
agree_flag  = tr.regime.all_sources_agree_flag_20             # ∈ {0, 1}
casc_signed = tr.geometry.ema_cascade_signed_10_20_50_100     # ∈ [-1, +1]
casc_score  = tr.geometry.ema_cascade_score_10_20_50_100      # ∈ [0, 1]

# Direction: consensus sign is authoritative; if consensus is zero, fall
# back to the cascade sign (only if cascade is unambiguous).
d = int(cons_sign) if cons_sign != 0 else (
    +1 if casc_signed > 0.34 else -1 if casc_signed < -0.34 else 0
)

# Strength: cascade cleanliness weighted with sign-consistency.
# If direction and cascade sign agree, cascade strength adds; if they
# disagree, cascade contribution is halved (partial evidence).
sign_ok = 1.0 if d != 0 and np.sign(casc_signed) == d else 0.5
strength = clamp01(0.5 * (2*cons_score - 2/3) + 0.5 * abs(casc_signed) * sign_ok)

# Confidence: consensus_score maps [1/3,1] → [0.30,1.00];
#   unanimity flag adds +20% (capped).
conf = clamp01(0.30 + 0.70 * (cons_score - 1/3) / (2/3))
if agree_flag >= 0.5:
    conf = min(1.0, conf + 0.20)
```

`sign_ok` handles the important edge case: consensus can say "up" while
the EMA cascade is broken; we should not present the cascade as full
strength evidence in that regime. Halving is not silent — the evidence
row for cascade explicitly reports the value.

### Weight budget (voter)
Redistribute 0.05 to make room for `TrendAlignment(0.05)`:
- `Trend 0.16 → 0.14` (−0.02)
- `Momentum 0.12 → 0.11` (−0.01)
- `TrendMomentum 0.05 → 0.03` (−0.02) — TrendMomentum is temporal;
  TrendAlignment is cross-source. Both are new L2 signals with weight 0.05
  after Priority 1; here we rebalance the L2-trend allocation so both
  survive without inflating total weight.

Sum unchanged. Alternative considered: shift from Structure (0.05) — rejected because Structure is a direction-neutral confidence-shaping signal, not a directional peer.

---

## 3. Explicit non-integrations (with rationale)

### Analogues — deferred
The K-NN analogue space in `analogues.py` uses a 19-dimensional z-space of L1-heavy features. Adding L2 dimensions is architecturally correct but changes historical similarity results, invalidating any stored recommendation's `top_k`. The right time to introduce L2 dimensions is a versioned schema bump (target: v0.8). Two concrete candidates to add then: `directional_consensus_score_20` and `ema_cascade_signed_10_20_50_100`. Documented here so v0.8 does not forget.

### Position Sizing — deferred
Sizing is a risk operation. Trend agreement is a directional-clarity operation. Blending the two silently would break the clean separation between "direction/strength" (signals) and "risk-adjusted position" (sizing). Kept apart on purpose.

### Risk — deferred with note
See sizing. However: `ema_cascade_score ≈ 0.5` is a measurable
"regime uncertainty" state. In v0.8 we may pass a *cascade-uncertainty*
factor into sizing as a *dampener only* (never a boost). Documented as a
future-work note; not shipped in this release.

---

## 4. Rollback plan

If `TrendAlignment` proves noisy:
1. Set weight `0.0` in `SIGNAL_WEIGHTS` — signal still fires and appears in evidence, contributes zero to score.
2. Remove from `SIGNAL_FUNCS` — safe; the `trend_relationships.*` features remain available for L3 / analogues / risk-uncertainty use.

No DB schema changes required for either step.

---

## 5. Sign-off

- Voter total weight after this ship: sums to 1.00 exactly.
- Existing 12 signals: **all preserved**. Only 3 have weight adjustments (Trend, Momentum, TrendMomentum), each within ±0.02.
- Regression: `TestDecisionRecommendV07` updated to expect 13 signals and the new `TrendAlignment` name.
- Book 1 compliance: the new signal consumes L2 only (upward flow); no L1 math re-implemented; no L5 code inside `atlas_core/`; `trend_relationships` code-audit confirms zero direct OHLCV reads.

*Author: main agent, Session 7 Priority 2. Reviewer: repository.*

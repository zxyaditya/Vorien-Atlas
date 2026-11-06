# Decision-Engine Review — `momentum_of_trend`

> **Point-10 review** for the L2 module shipped in Session 7 Priority 1.
> Per user directive: *"For every new Layer 2 capability, evaluate how it can
> improve Signals / Weight Learning / Analogues / Confidence / Position
> Sizing / Risk / Explanations / Recommendation Quality. Do not automatically
> integrate every feature. Justify every integration. If a Layer 2
> representation is not yet useful inside the Decision Engine, document why."*

---

## 1. Recommendation summary

| Consumer                | Verdict     | What we do this ship                                     |
|-------------------------|-------------|----------------------------------------------------------|
| **Signals**             | ✅ Integrate | Add a new `TrendMomentum` signal (directional, L2).      |
| **Weight Learning**     | ✅ Free      | Weight learner already loops over `SIGNAL_FUNCS` — new signal is auto-included, no code change. |
| **Historical Analogues**| ⏸  Defer   | Analogues use a 19-dim z-space. Extending it changes prior similarity results — do only under a versioned analogue-space bump (v0.8). Documented as pending. |
| **Confidence**          | ✅ Indirect  | `direction_persistence` boosts the new signal's own confidence. The overall voter agreement metric will also benefit implicitly. |
| **Position Sizing**     | ⏸  Defer   | Sizing reads risk features (ATR%, Ulcer, Hurst). Trend-velocity does not modify risk. Not applicable this ship. |
| **Risk**                | ⏸  Defer   | Same as sizing — momentum_of_trend does not measure risk. |
| **Explanations**        | ✅ Free      | Existing deterministic templating iterates over each signal's `evidence` — new signal's evidence rows are automatically formatted. |
| **Recommendation Quality** | ✅ Direct | The existing `Momentum` signal reads L1 price-motion; it cannot distinguish "trend accelerating" from "trend stalling". Adding the L2 read closes that gap. |

---

## 2. New signal · `TrendMomentum` (L2)

### Purpose
Answer the question: *"Beyond the raw price movement, is the underlying
trend of the market gaining or losing strength right now, and do multiple
trend representations agree on that answer?"*

### Reads (all L2 · `momentum_of_trend.*`)
| Feature ID                                                             | Role in signal                                       |
|------------------------------------------------------------------------|------------------------------------------------------|
| `momentum_of_trend.motion.lr_slope_20_velocity_20`                     | Primary directional vote (weight 0.40)               |
| `momentum_of_trend.motion.adx_14_velocity_20`                          | Secondary vote — unsigned strength change (weight 0.20; direction from slope-velocity sign) |
| `momentum_of_trend.relative.velocity_sign_agreement_20`                | Confidence booster (agreement in `[0,1]` → confidence base) |
| `momentum_of_trend.regime.lr_slope_20_direction_persistence_20`        | Persistence bonus for `strength` (long runs strengthen the signal) |

### Formula (pseudocode)
```
v_slope  = m.motion.lr_slope_20_velocity_20
v_adx    = m.motion.adx_14_velocity_20        # strength-of-trend change
agree    = m.relative.velocity_sign_agreement_20   # ∈ [0, 1]
persist  = m.regime.lr_slope_20_direction_persistence_20  # ∈ [0, 20]

direction = sign(v_slope + 0.5 * v_adx * sign(v_slope))
strength  = clamp01(|v_slope|*scale + (persist/20)*0.3)
confidence = clamp01(0.4 + 0.6 * agree)
```

Direction is driven by the LR-slope velocity. ADX-velocity acts as a
strength-of-trend modifier that only reinforces (never overrides) the
slope-velocity sign — this preserves the interpretive clean separation
between "trend direction" and "trend strength".

### Weight budget (voter)

Redistribute 0.05 of the existing weights (Trend −0.02, Momentum −0.02,
Structure −0.01) to make room for a **0.05 weight** on `TrendMomentum`. Not
0.10+: this is a first-ship signal; observe before promoting. Weight
totals remain ≈ 1.00. Manual weights are the default; users can still opt
into the learned weights via the existing toggle, which will discover the
right weight per regime once the walk-forward backtest ships in v0.8.

---

## 3. Why NOT integrate into every DE input

- **Analogues (K-NN)**: expanding the 19-dim z-space breaks the reproducibility of previously-saved recommendations. The space needs a versioned schema (v0.8 target). Adding momentum_of_trend dimensions here now would invalidate every stored recommendation's `analogues.top_k`.
- **Risk / sizing**: trend velocity is orthogonal to tail-risk measures (VaR / ES / ATR%). Injecting it into sizing would be a semantic error — it would push sizing based on a directional-strength property, which is what signals already do.
- **Explainer**: templating already covers new signals for free. No dedicated string needs to be authored.
- **Weight learner**: no code change — the rolling logistic regression already fits over `direction × strength` of every signal in `SIGNAL_FUNCS`. `TrendMomentum` joins the fit automatically at next `/api/decision/learned_weights` call.

---

## 4. Rollback plan

If `TrendMomentum` proves noisy in production:
1. Set its weight to `0.0` in `SIGNAL_WEIGHTS` (voter.py). The signal still fires and appears in evidence, but contributes nothing.
2. Optionally remove from `SIGNAL_FUNCS` — safe because it consumes L2 features that are still registered and available to other consumers.

No database schema changes are required for either step.

---

## 5. Sign-off

- Signal weight budget re-verified: total = 1.00.
- Existing 11 signals unaffected in code (only weights shifted for 3 of them by ≤ 0.02).
- Regression: 11 → 12 signals; `TestDecisionRecommendV06` will need to accept 12 signal names (see the pytest patch alongside this ship).
- Book 1 compliance: the new signal consumes L2 only (upward flow); no L1 math re-implemented; no L5 code inside `atlas_core/`.

*Author: main agent, Session 7 Priority 1.  Reviewer: repository (this
document is the reviewer of record until the project owner overrules).*

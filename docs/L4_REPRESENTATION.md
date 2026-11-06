# Layer 4 — Representation — Mathematical Specification

> Version: v0.9.0 (Session 9 milestone) · Book 1 Ch. 5.
>
> Single overarching spec for **all L4 modules**, following the same
> pattern as `L3_MARKET_UNDERSTANDING.md`. L4 modules differ only in
> which L1/L2/L3 features they compose and along which axis they
> compress / interact / encode.

---

## 1. Book 1 anchor

Book 1 Ch. 5 defines Layer 4 as **Representation**:

> *"Layer 4 answers: how should this market understanding be represented
> for intelligent systems? Content: interface between Atlas and
> ML/statistical consumers; organises, compresses, structures.
> Examples: cross-module interactions, meta features, feature
> embeddings, dimensionality reduction, feature selection, multi-scale
> representations, state encodings."*

Book 1 Ch. 8: *"A meta-feature combining trend + volatility +
microstructure into a single embedding belongs to L4."*

L4 is the **Atlas ↔ ML handshake**. It produces ML-ready inputs.
L5 (the Decision Engine and future Learning System) consumes L4.

## 2. Boundaries (what L4 IS NOT)

- **Not supervised learning.** Book 1 Inv-5.6: no ML models
  (gradient-boosted trees, random forests, DNNs, transformers, RL,
  Bayesian). PCA / rolling z-score / one-hot / interaction / entropy
  proxies are pure mathematics — deterministic closed-form
  transformations, no labels, no gradients. Allowed.
- **Not target-encoded.** Any encoding that uses the label is L5.
- **Not prediction, sizing, execution.** All L5.
- **Not state classification.** L3.
- **Not raw measurement / relationship.** L1 / L2.

## 3. Access contract (DEC-016)

L4 accesses lower layers exclusively via
`atlas_core/layers/l4_representation/_layer_bridge.py`:

```
l1_series(df, feature_id)                 → pd.Series
l2_series(df, feature_id, context=None)   → pd.Series
l3_series(df, feature_id)                 → pd.Series
```

Same identity-keyed cache mechanics as the L2/L3 bridges. Flushed on
entry and exit of every `compute_features` call (DEC-011). No direct
OHLCV access from L4 modules — enforced by pytest.

## 4. L4 kernel (`_representation_kernel.py`)

Layer-local primitives (Book 1 Ch. 10 discovery discipline; not
promoted to `engines/` until reuse is observed):

```
rolling_zscore(s, window)              → pd.Series
interaction(a, b, op)                  → pd.Series  op ∈ {product, ratio, min, max, absdiff, sign_agree}
one_hot(code_series, k)                → list[pd.Series]  (k dense flags)
quantile_bin(s, k, lookback)           → pd.Series  ordinal encoding
rolling_rank(s, window)                → pd.Series  in [0, 1]
rolling_entropy(s, window, bins)       → pd.Series  Shannon entropy of histogram
rolling_dispersion(s, window)          → pd.Series  σ / |μ|
rolling_pca(M, k, lookback)            → (pcs_ts: pd.DataFrame[k], evr_ts: pd.DataFrame[k])
                                         deterministic; roll-forward; no future leakage
```

All primitives are NaN-preserving on partial windows and degrade
gracefully on degenerate inputs.

## 5. Module hierarchy (v0.9.0)

Five modules ship in the L4 milestone, mapped 1-to-1 against Book 1's
L4 exemplar families:

| Module | Book 1 exemplar family | # features | Winner-take-all? |
|---|---|---|---|
| `cross_module_interactions` | Cross-module interactions | ~20 | No |
| `meta_features` | Meta features | ~15 | No |
| `state_encodings` | State encodings | ~15 | No |
| `multi_scale_representations` | Multi-scale representations | ~15 | No |
| `embeddings` | Feature embeddings + dimensionality reduction | ~10 | No |

**Feature selection** — Book 1 lists it as an L4 example but its
"learned importance" variant is L5, and the "deterministic dispersion"
variant is thin. Deferred to v0.9.1 or later.

## 6. Composition per module

### 6.1 `cross_module_interactions`
Reads L1 × L2, L2 × L3, and L3 × L1 combinations.

Representative features:
- `motion.trend_x_volume_signed_20` = sign(L1 trend) × L1 volume z-score
- `relative.regime_x_liquidity_20`  = L1 ADX × L1 liquidity tercile
- `geometry.state_x_volatility_20`  = L3 `market_regime.statistics.active_state_confidence` × L1 volatility tercile
- `motion.structure_x_momentum_agree_20` = sign(L2 BOS) × sign(L2 slope-velocity)
- `relative.trend_state_x_participation_state` = signed cross of the two L3 direction-bearing families

### 6.2 `meta_features`
Statistics of L2/L3 outputs — "features about features".

Representative features:
- `statistics.l3_confidence_mean_20`  = rolling mean over five L3 active_state_confidences
- `statistics.l3_confidence_std_20`   = rolling std of same
- `entropy.l3_flag_entropy_20`        = Shannon entropy of the L3 flag distribution
- `position.l2_consensus_mean_20`     = rolling mean of L2 directional_consensus_score_20
- `regime.l3_family_agreement_score`  = fraction of L3 families whose direction agrees

### 6.3 `state_encodings`
Deterministic (label-free) encodings of L3 states and L1/L2 continuous features.

Representative features:
- One-hot flags for each of the 5 L3 module `active_state_code`s (already exist at L3; L4 provides the ordinal encoding + rank encoding)
- `position.rank_100` of curated L2 features (rolling percentile rank)
- `clustering.quantile_bin_20` of curated L1 features (5-bin ordinal encoding)

### 6.4 `multi_scale_representations`
Same primitive summarised across ≥ 3 scales.

Representative features:
- `geometry.trend_consensus_mean_10_20_50`  = mean of L2 consensus at 3 windows
- `statistics.hurst_multi_scale_std_32_64_128` = cross-window std of L1 Hurst
- `clustering.multi_scale_direction_agreement`  = fraction of scales where sign agrees

### 6.5 `embeddings`
Rolling deterministic PCA of a curated 20-feature input matrix (mix
of L1, L2, L3 numerics) onto the top-5 components. Roll-forward with
`lookback = 250` bars.

Representative features:
- `geometry.pc1`, `pc2`, `pc3`, `pc4`, `pc5`
- `statistics.evr_1`, `evr_2`, `evr_3`, `evr_4`, `evr_5`

**The L4 → future Learning System handshake**: `L4_EMBEDDING_IDS` is
exported as a module constant so future work can consume a stable
z-space without re-hunting features.

## 7. Validation contract

- Universal gates run on every L4 feature (5 gates).
- Registry-wide gates cover L4 by construction (`unique_formula_hash`,
  `no_duplicate_values`, `three_scale_rule` — L4 has no
  `fractal_relationships`-family features so three-scale is a no-op
  for L4).
- **NEW property gate at v0.9.0: `orthogonality`** — for embedding PCs,
  certifies pairwise correlation ≈ 0 across canonical fixtures.
- Existing `bounded[0, 1]` reused on ordinal-encoded / one-hot
  features.
- `FeatureValidation(bridge="l4", ...)` — the `bridge` field is
  reserved; framework runner is layer-agnostic and needs no code
  change.

## 8. Decision Engine integration

Two new L4-derived signals added in v0.9.0 (both consume `l4_*` via
the standard SIGNAL_FEATURE_IDS path):

| Signal | Direction | Strength driver | Reads from |
|---|---|---|---|
| `CrossFlow` | Sign of `trend×volume` × `structure×momentum` interactions | Magnitude of interaction agreement | `cross_module_interactions.*` |
| `MetaConfidence` | 0 (direction-neutral) | `meta_features.regime.l3_family_agreement_score` | `meta_features.*` |

Voter weight budget: 0.05 drawn from Trend (−0.01), Momentum (−0.01),
Regime (−0.01), Structure (−0.01), Volume (−0.01). Sum invariant
preserved at 1.00.

**Embeddings do NOT get a DE signal**. They are the L4 → future
Learning System handshake, exposed as first-class Registry features
consumable via `/api/features/values` and `SIGNAL_FEATURE_IDS`. When
the analogue z-space is next versioned, `L4_EMBEDDING_IDS` becomes its
input pointer.

Total DE signals: **22** (was 20).

## 9. Not in scope for v0.9.0

- Feature-selection module (deferred).
- Analogue z-space bump from 19-dim (L1-heavy) to embedding-based (versioned schema bump; separate milestone).
- Regime-conditional voter weighting driven by `RegimeState` × embeddings (L5 milestone).
- Target-encoded / label-based encodings.
- Autoencoders, t-SNE, UMAP.

---

*Author: main agent, Session 9 milestone. Reviewed against Book 1 Ch. 5 & Ch. 8. See DEC-016 (L4 access contract). Book 1 Inv-5.6 not violated: L4 uses closed-form deterministic mathematics; no supervised learning, no labels, no gradients.*

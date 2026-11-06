# Atlas — Validation Framework Specification

> **Priority 5 · Session 7.** The mathematical-certification subsystem
> of Atlas. This is not a test suite. This is a permanent architectural
> component that every present and future feature plugs into.
>
> DEC-013 authorises the framework. This file is its specification.

---

## 1. Purpose

Turn "does this feature work?" from a per-test question into
**declarative metadata** carried by every feature in the Registry.

The framework's job:

1. Let every feature **declare** which mathematical guarantees it
   claims to satisfy.
2. **Prove** each declared claim automatically, on canonical inputs.
3. **Persist** the result as a first-class `ValidationProfile`
   attached to the feature — alongside `formula`, `params`,
   `perspective`, and every other metadata field.
4. Make **coverage cheap to grow**: adding a new feature adds one
   declaration line; every applicable gate runs automatically.

The objective is **not** bug detection. It is
**mathematical certification of every feature Atlas produces.**

## 2. Three-concept model

```
FeatureValidation (declaration)   ← authored at feature registration
         │
         ▼
ValidationRunner (execution)      ← runs gates against canonical fixtures
         │
         ▼
ValidationProfile (metadata)      ← attached to the feature; queryable;
                                    the certified truth about it
         │
         ▼
ValidationReport (aggregate)      ← Registry-wide view over profiles
```

`FeatureValidation` = **claim.**
`ValidationProfile` = **proof or absence of proof.**
`ValidationReport` = **the map of both.**

The three are strictly separated. A declaration without a proof is not
a certification; a proof without a declaration is a bug in the runner.

## 3. Why this belongs to `atlas_core/validation/`

Validation is **cross-cutting infrastructure**, not a Layer. It sits
alongside the Registry itself (SHA-1 formula-hash guardrail) as
foundational machinery. Book 1 Ch. 9 mandates validation gates without
placing them in the Layer hierarchy; DEC-013 codifies "validation is
infrastructure, not a Layer" as the framework's placement principle.

Consequence: **no new Layer** is introduced by this ship. The
framework code lives at `atlas_core/validation/`, joining the
pre-existing 36-golden module. No math crosses upward or downward.

## 4. Gate taxonomy

Four categories. Every gate implements the same signature:

```python
def gate(feature_def, ctx: GateContext) -> GateResult:
    # ctx exposes fixtures, tolerance defaults, and layer bridge access.
    # Returns GateResult(status, evidence, duration_ms).
```

### A · Universal gates — run against every feature automatically

Applied by the runner without any declaration required. A feature can
`exempt` itself from a universal gate only with a documented reason;
the exemption is preserved in the profile.

| Gate ID | What it proves |
|---|---|
| `determinism` | Same input → same output, `np.allclose(atol=1e-12, rtol=0)` on numeric; exact equality on flags/masks |
| `length_invariance` | `len(output) == len(input)` (Ch. 6 alignment discipline) |
| `no_future_leakage` | Perturbing bar `t+k` (k ≥ 0) does not change output at any `t` where `t < N − k` |
| `nan_input_behavior` | Behavior on NaN-injected input matches the declared `nan_behavior` (`propagate` \| `ignore` \| `recover`) |
| `degenerate_constant` | Behavior on all-equal input matches the declared `degenerate_value` (default: allowed to be NaN) |

### B · Property gates — opt-in via declaration

Applied only where the feature's `FeatureValidation.properties` block
declares them. The runner ignores properties the feature does not
claim.

| Property ID | Params | Verified how |
|---|---|---|
| `bounded` | `{lo, hi, tol=0}` | Every finite output ∈ `[lo − tol, hi + tol]` |
| `scale_invariant` | `{}` | `f(k · close) == f(close)` for k ∈ {0.5, 2, 10} within tolerance |
| `translation_invariant` | `{}` | `f(close + c) == f(close)` for c ∈ {−25, +50} within tolerance |
| `symmetric_in_peer` | `{}` (context-aware) | `f(a, peer=b) == f(b, peer=a)` within tolerance |
| `identity_when` | `{condition_id}` | Named condition (registered in `gates/properties.py`) proves the identity — e.g. `identity_when: peer_equals_target` for `rs(a, a) ≡ 1` |
| `monotonic_with` | `{input_property}` | Increasing the named input property does not decrease the output (checked on a synthetic ramp) |

### C · Registry-wide gates — run once per report, not per feature

| Gate ID | What it catches |
|---|---|
| `unique_formula_hash` | SHA-1 guardrail (already enforced at registration; surfaced in the report) |
| `no_duplicate_values` | Two features with different formulas producing numerically-identical output on the canonical Brownian fixture. Implemented via bucket-hash → verify within buckets (O(N), not O(N²)) |
| `three_scale_rule` | Every `fractal_relationships.*` feature carries `params["scales"]` with `len ≥ 3` (v0.7.2 guardrail, promoted from ad-hoc pytest to framework gate) |
| `context_isolation` | Features whose declaration includes `requires_context: {peer}` return all-NaN when context is missing |

### D · Analytical identities — module-level golden anchors

Named identities are declared per feature and verified by the runner.
This is where the **36 existing pytest goldens migrate** — they become
first-class declarations attached to their features, verifiable
through the same `ValidationRunner`.

Example (attached to `relative_strength.magnitude.rs_20`):

```python
identities=[
    Identity(
        name="rs_identity_when_peer_equals_target",
        condition="peer=target",
        expected="output ≡ 1.0",
        tolerance=1e-9,
    ),
]
```

## 5. `FeatureValidation` — the declaration

Attached (optionally) to every `FeatureDefinition` at registration. The
field is optional and backwards-compatible — existing features that
predate the framework simply carry `validation=None` and are subject
only to universal gates.

```python
@dataclass
class Identity:
    name: str                 # unique per feature
    condition: str            # human-readable description of the input condition
    expected: str             # human-readable description of the expected outcome
    tolerance: float = 1e-9
    # Concrete verification code lives in gates/properties.py registered by name.
    verifier: str = ""        # ID into the identity-verifier registry

@dataclass
class FeatureValidation:
    # --- Universal gates ---
    gates: List[str] = default(lambda: DEFAULT_UNIVERSAL_GATES)
    nan_behavior: str = "propagate"     # "propagate" | "ignore" | "recover"
    degenerate_value: Optional[float] = None  # None means "any" (typically NaN)
    exemptions: Dict[str, str] = default(dict)   # gate_id → written reason

    # --- Property gates (opt-in) ---
    properties: Dict[str, Dict] = default(dict)

    # --- Analytical identities ---
    identities: List[Identity] = default(list)

    # --- Book 1 invariants the feature commits to ---
    invariants: List[str] = default(list)   # e.g. ["6.4", "6.1"]

    # --- Author-stated preconditions ---
    assumptions: List[str] = default(list)  # e.g. ["≥ 50 bars", "close > 0"]

    # --- Complexity + stability metadata ---
    complexity: str = "O(n)"                 # "O(n)" | "O(n log n)" | "O(n^2)" | …
    stability: Dict[str, str] = default(dict)  # e.g. {"unstable_when": "σ ≈ 0"}

    # --- Multi-symbol context requirement ---
    requires_context: List[str] = default(list)  # e.g. ["peer"]

    # --- Layer-bridge declaration (forward-compatibility with L3+) ---
    bridge: str = "l1"                       # "l1" | "l2" | "l3" | "direct"
```

Design rules:

- **Declaration is descriptive, not prescriptive.** A feature that
  claims `bounded: [0, 1]` must actually be bounded; the runner
  verifies the claim, not the intent.
- **Silence is permission.** Undeclared properties are not tested.
  This prevents test-file bloat and lets features be honest about
  what they guarantee.
- **Exemption requires written reason.** A universal gate can be
  skipped only with an explicit exemption note. The note lives in the
  profile forever, auditable.
- **Assumptions modulate the runner.** The runner will not subject a
  feature declaring `assumptions=["close > 0"]` to a negative-price
  input. Prevents false-failures on inputs the feature never claimed
  to handle.

## 6. `ValidationProfile` — the metadata

Populated by the `ValidationRunner`. Attached to the feature (in
memory today; queryable via API). Not a test-run artefact — a
**permanent characteristic of the feature**, analogous to `formula` or
`perspective`.

```python
@dataclass
class GateResult:
    gate: str
    status: str        # "pass" | "fail" | "n/a" | "exempt" | "not_declared"
    evidence: Dict     # gate-specific detail (values, tolerances, seeds)
    duration_ms: float

@dataclass
class IdentityResult:
    identity: Identity
    status: str        # "pass" | "fail" | "skipped"
    max_deviation: Optional[float]
    duration_ms: float

@dataclass
class ValidationProfile:
    feature_id: str
    declaration: FeatureValidation            # the raw claim block

    # What has been proven:
    gate_results: List[GateResult]
    identity_results: List[IdentityResult]

    # Roll-up:
    invariants_committed: List[str]
    invariants_verified: List[str]
    coverage_score: float                     # fraction applicable + passed
    last_run: str                             # ISO-8601 timestamp

    # Runtime characterisation:
    complexity_declared: str
    complexity_measured_ms_per_1000_rows: Optional[float]

    # Soft-fail signals:
    warnings: List[str]
```

`coverage_score` is defined as:

```
coverage_score = (# gates passed) / (# applicable gates)
```

where "applicable" excludes explicit exemptions and gates the feature's
assumptions have opted-out of. A feature with all universal gates
passing and no declared properties scores `1.0` — universal certification.

## 7. `ValidationReport` — the aggregate

Computed view over all feature profiles. Cacheable. Exposed via:

- `GET /api/validation/report` — full Registry-wide report + rollups.
- `GET /api/validation/report?module=<module>` — filtered by module.
- `GET /api/validation/report?layer=1|2` — filtered by layer.
- `GET /api/validation/profile/{feature_id}` — one feature's profile.
- `GET /api/validation/golden` — **kept for backwards compatibility.**
  Internally a filter on `/api/validation/report` for the
  `identity_result.status == "pass"` subset.

Report includes:

- Registry-wide gates (`no_duplicate_values`, `three_scale_rule`, …).
- Per-module rollup: (# features, mean coverage, # warnings, # exemptions).
- Layer rollup.
- Timestamped last-run.

## 8. Runner

`atlas_core/validation/runner.py::ValidationRunner`:

```
for feature in registry.list():
    profile = ValidationProfile(feature_id=feature.id,
                                 declaration=feature.validation or FeatureValidation())

    # 8.1 Universal gates
    for gate in UNIVERSAL_GATES:
        if gate.id in profile.declaration.exemptions:
            profile.gate_results.append(GateResult(gate.id, "exempt", ...))
            continue
        result = gate.run(feature, ctx)
        profile.gate_results.append(result)

    # 8.2 Property gates
    for prop_id, prop_params in profile.declaration.properties.items():
        gate = PROPERTY_GATES[prop_id]
        result = gate.run(feature, ctx, prop_params)
        profile.gate_results.append(result)

    # 8.3 Identity verification
    for identity in profile.declaration.identities:
        result = identity_verifier(feature, identity, ctx)
        profile.identity_results.append(result)

    # 8.4 Book 1 invariant check (automatable ones only)
    profile.invariants_verified = check_invariants(feature)

    # 8.5 Rollup
    profile.coverage_score = compute_coverage(profile)
    profile.last_run = now_iso()

    profiles[feature.id] = profile

# Registry-wide gates run once
registry_wide_results = [gate.run(profiles, ctx) for gate in REGISTRY_WIDE_GATES]
```

Runner is **idempotent** and **cached** (TTL=60s by default). Re-running
against the same Registry snapshot must yield identical profiles —
the framework certifies its own determinism.

## 9. Canonical fixtures

`atlas_core/validation/fixtures.py`:

| Fixture ID | Contents | Purpose |
|---|---|---|
| `brownian` | 500 bars of geometric Brownian motion, σ=0.02, μ=0 | Baseline stochastic input; anchors Ch.5 canonical values |
| `trending` | 500 bars of positive-drift Brownian, μ=0.001 | For monotonicity + directional gates |
| `mean_reverting` | 500 bars of AR(1) with negative φ | For MeanReversion signals; degeneracy tests |
| `constant` | 500 bars of a single price | Degenerate-input tests |
| `nan_infested` | Brownian with 5% randomly-NaN closes | NaN-input behaviour tests |
| `two_pairs` | Two 500-bar Brownians (aligned index) | Multi-symbol context tests (peer / basket future L4) |

Fixtures are generated with fixed random seed → framework itself is
deterministic.

## 10. Migration of the 36 pytest goldens

Each of the 36 goldens becomes an `Identity` declared on its owning
feature. The runner verifies them through the same code path as any
other identity.

Legacy `/api/validation/golden` endpoint becomes a filter on the
report: pass_count / total for identities whose author flagged them
as `golden=True`. Backwards-compatible: the endpoint still returns
`{passed: N, total: N}`; the number stays at 36/36 after migration.

**No golden is deleted.** They are re-homed as first-class metadata.

## 11. Adoption pattern

For this ship (v0.7.4):

- **Universal gates run against all 665 features** — automatic; no
  declarations required.
- **Property declarations authored on ~20 representative features**,
  ≥2 per module. The pattern is set; every future feature is expected
  to declare its properties as part of the DEC-012 workflow. This is
  what "validation gets progressively easier" means operationally:
  each new feature costs one declaration line, and every applicable
  gate then runs for free.
- **Identities: all 36 goldens migrated in this ship.** Each identity
  attaches to its owning feature.
- **Registry-wide gates: all four run** once per report.

Future ships (v0.8+):

- Progressive coverage expansion — every DEC-012 module ships with
  full declarations from day one.
- Historical trend of coverage scores (once we have a persistence
  layer beyond the in-memory Registry).
- Runtime complexity spot-check comparing declared vs measured
  ms-per-1000-rows across two input sizes.

## 12. Forward-compatibility with L3+

The framework is **layer-agnostic by construction.** No universal or
property gate assumes L1 or L2 semantics. Every gate receives
`(feature_def, ctx)` and produces `(status, evidence)`. Consequences
for Session 8 and beyond:

- **`bridge` field on `FeatureValidation`** — a feature declares which
  bridge it consumes: `"l1"` (via `_l1_bridge`), `"l2"` (via the future
  `_l2_bridge`), `"l3"`, or `"direct"` (only permitted for L1). The
  runner uses this to select the correct fixture-plumbing at gate time.
  Today only `"l1"` and `"direct"` are populated; `"l2"` will start
  appearing when L3 modules arrive.
- **`_l2_bridge` (Session 8+, not implemented here)** — the analogue
  to `_l1_bridge` for Layer-3 consumers. Interface will mirror
  `_l1_bridge.l1_series(df, feature_id)`. Cache-flush discipline
  (DEC-011) applies identically. Registry stats will begin reporting
  L3 counts.
- **Categorical / regime outputs (probable at L3)** — property
  grammar will extend with `discrete: {states: N}` and
  `enum: {values: [...]}`. Placeholders reserved in the spec; not
  implemented until an L3 feature needs them (Principle VI: no
  speculation).
- **Multi-timeframe features (L3+)** — each timeframe validates
  independently. Fixtures at v0.8+ will add cross-timeframe versions
  as needed. Framework requires no change to accommodate them.
- **Cross-registry queries** — `ValidationProfile` is a proper
  dataclass; once the Registry migrates to Postgres (KNOWN_LIMITATIONS
  §6), profiles become SQL-queryable. Questions like "which features
  have `bounded: [0, 1]`?" or "which features have unresolved
  `warnings`?" become one-line queries.

**Zero L3 code ships with v0.7.4.** These are design-forward notes
only, per owner directive.

## 13. Non-goals

- **Interpretation of features.** The framework certifies mathematical
  properties, not meaning. "Is this feature useful for trading?" is a
  Layer-5 question and lives in the Decision Engine, not here.
- **Performance benchmarking beyond spot-checks.** The
  `complexity_measured_ms_per_1000_rows` field is a spot-check, not a
  benchmark suite. Full benchmarking is a separate v0.8+ concern.
- **Persistent storage of historical profiles.** Profiles are
  computed on demand (cached TTL=60s) in v0.7.4. Historical
  time-series of coverage lives in v0.8+ once the Registry moves to
  Postgres.
- **Auto-declaration by inference.** The framework will not attempt
  to infer property claims from the feature's source code. Every
  claim is authored by the feature owner. Silent inference would
  breach Book 1 Principle VII (every architectural decision must be
  explainable).

## 14. Success criteria for v0.7.4 ship

1. Every registered feature has a `ValidationProfile` accessible via
   `GET /api/validation/profile/{feature_id}`.
2. `GET /api/validation/report` returns a fully-populated report,
   grouped by module and layer.
3. All 665 features pass all universal gates OR carry a documented
   exemption. **Zero silent failures.**
4. All 36 existing goldens are re-homed as identities and continue to
   pass through the new runner. `GET /api/validation/golden` still
   returns `{passed: 36, total: 36}`.
5. ~20 features carry declared property gates covering `bounded`,
   `scale_invariant`, `translation_invariant`, `symmetric_in_peer`,
   `identity_when`, and `monotonic_with`.
6. Registry-wide gates `unique_formula_hash`, `no_duplicate_values`,
   `three_scale_rule`, and `context_isolation` run once per report.
7. Backend pytest count grows from 31 → **≥ 37** (framework
   regression tests).
8. Documentation drift closed across the full doc set.
9. Version bump v0.7.3 → v0.7.4 (additive infrastructure, no math).
10. `KNOWN_LIMITATIONS.md §7` (validation debt) shrinks meaningfully.

## 15. Cross-references

- **DEC-013** (in `DECISIONS.md`) — authorises the framework as a
  permanent architectural component and codifies "validation is
  infrastructure, not a Layer."
- Book 1 Ch. 9 — validation gate mandate.
- Book 1 Principle VI + DEC-008 — no speculative abstraction; the
  framework extracts patterns already duplicated across the 36
  goldens and the ad-hoc pytest audits.
- Book 1 Principle VII — every certification is explainable
  (declaration → runner → profile — every step machine-readable).
- DEC-011 — cache-flush discipline applies to every bridge; the
  runner respects it.
- DEC-012 — spec-first workflow; this file is the spec.

---

*Author: main agent, Session 7 · Priority 5 · Phase 0.
Reviewer: repository. Awaits Phase 1 approval — already granted by
project owner in Session-7 Priority 5 kickoff.*

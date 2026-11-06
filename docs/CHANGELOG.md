# Atlas — Changelog

> Every shipped version. Latest first.

---
## v1.0.1 · Open-Source Infrastructure Release (October 2026)

**Theme**: Prepare Atlas for public open-source release under Apache-2.0. Full forensic verification of features, mathematical ground-truth audit, elimination of local environment paths, and removal of artificial documentation padding.

### Added
- **`LICENSE`**: Official Apache-2.0 open-source license.
- **Audited Feature Registries**: Fully verified ground truth across 925 Atlas Core features (L1: 612, L2: 151, L3: 90, L4: 72) and 1,039 total platform features including perpetual swap derivatives (69) and options volatility surfaces (45).
- **Portable Lake & Store Paths**: Transitioned all storage fallbacks in `atlas_data_lake.py` and `whale_hunter` to environment-variable-backed defaults with cross-platform home directory fallbacks (`~/.atlas/`).

### Changed
- **`docs/` Suite Overhaul**: Completely rewrote and cleansed `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/FEATURE_HIERARCHY.md`, `docs/PROJECT_CONTEXT.md`, `docs/LEARNING_SYSTEM.md`, `docs/BACKTEST_ENGINE.md`, and `docs/KNOWN_LIMITATIONS.md`. Excised over 800 lines of artificial filler and synchronized all layer and module metrics with the codebase.
- **`Makefile`**: Updated root orchestrator to natively target `atlasnew/docker-compose.yml`.
- **Telemetry UI**: Sanitized UI indicators in `MarketSnapshotView.jsx` to reflect enterprise parquet data lake metrics.

---
## v1.0 · Polish Pass (July 2025)

**Theme**: turn the functional v1.0.0 milestone into a product that visually and behaviourally matches the ambition of a professional quantitative trading platform. **No new backend features. No new APIs.** Every change is frontend polish, live-data correctness, or performance.

### Changed — Design system (complete rewrite)

- **`frontend/src/index.css`** rewritten from scratch as a semantic-token light-theme design system. Off-white app background (`#fafbfc`), pure-white cards, soft shadows over hard borders, `Inter` for UI, `JetBrains Mono` for numbers, generous spacing scale, motion tokens (`--dur-fast/med/slow`, `--ease-out`), radius scale (4/6/10/14). Semantic colours: `--brand` (indigo/blue), `--pos` (emerald), `--neg` (crimson), `--warn` (amber). Every component now speaks tokens; no raw hex values in view files.
- New base primitives: `.panel`, `.metric-card`, `.atlas-table` (sticky header, hover rows, no vertical borders), `.pill`, `.badge`, `.btn` (+ `.btn-brand`, `.btn-pos`, `.btn-neg`, `.btn-ghost`, `.btn-trade-long`, `.btn-trade-short`), `.modal-*`, `.empty-state`, `.spinner`, `.skeleton`, `.tabs / .tab-btn.active`.
- Header redesigned: 26px gradient brand square, right-aligned status pill with a live-dot, tab navigation with active-state background + underline.

### Changed — Terminal (`components/atlas/TerminalView.jsx` rebuilt)

- **Deterministic chart lifecycle.** PriceChart uses a single chart instance guarded by a `ResizeObserver`; `chart.remove()` fires synchronously in the effect's cleanup, so provider / interval / symbol switches never leave a stale chart behind.
- **Late-fetch guard.** A `genRef` counter increments on every switch; any response returning after a switch is discarded. Fixes the "candle from previous symbol survives" class of bugs.
- **Live tail via polling** — `setInterval` polls `/api/market/ohlcv` every 8–60s (interval-adaptive) for the last 3–5 bars and applies them with `series.update()`, so the chart tail updates continuously without a re-fit or flicker.
- LIVE / STALE / ERROR status pill with `updated Ns ago` counter.
- New interval-picker segmented control (`5m 15m 30m 1h 4h 1d 1wk`), big price + 30-bar High / 30-bar Low / Range % / Avg volume / Composite Health strip, snapshot readout below.

### Changed — Paper Trading (`components/atlas/PaperView.jsx` rebuilt as trading workspace)

The old workspace was analytics-first. The new workspace is chart-first — a real trading terminal.

- **TOP**: Portfolio-value strip (Equity · Total P&L · Unrealized · Realized · Win Rate).
- **MID**: Grid — large live price chart LEFT, Atlas Recommendation panel RIGHT.
  - Recommendation panel loads `/api/decision/recommend` on symbol change and auto-populates side, stop, and TP from the `sizing` block.
  - Two big action buttons — green `.btn-trade-long` ▲ LONG, red `.btn-trade-short` ▼ SHORT — with hover / active / disabled affordances.
  - Size %, Stop-loss, Take-profit, and Note inputs are all user-editable before submit.
- **BOTTOM**: Tabbed panel — Open positions · Trade journal · Performance analytics. The equity curve moved into the analytics tab; positions and journal each own the full panel width.
- Trade Details modal rebuilt in the new light theme.
- CSV export, filters, Mark Now, Reset Account preserved verbatim.

### Changed — PriceChart (`components/atlas/primitives.jsx`)

- New `liveBar` prop applied incrementally via `series.update()`.
- Bar array de-duped by time (last write wins) — protects against provider quirks.
- All chart colours pulled from CSS custom properties at mount so any future theme changes are one edit.

### Changed — Performance

- New `frontend/src/components/atlas/cache.js` — in-memory TTL cache for `/api/market/symbols` and `/api/registry/stats` (5-minute TTL). These change once per deploy; no reason to hit them repeatedly.
- Heavy children wrapped in `React.memo`: Header, TerminalView, PredictionView, PaperView, Metric, DirectionPill.
- `useCallback` stabilises setters passed through props so memoized children don't re-render on every parent update.
- Removed duplicate abort-controllers in mount-only effects; loading no longer races the initial paint under React 18 StrictMode.

### Changed — All other views

- FeatureExplorer chart re-themed.
- RSMiniChart re-themed.
- About page rewritten (v1.0 · Polish Pass heading).

### Verified

- **Frontend Playwright end-to-end sweep** — all 8 tabs green. 65+ passes, 0 critical errors.
- **Paper Trading money path verified**: clicked ▲ LONG → "Opened LONG SYN-EQUITY · 102.2297 units @ 101.4808" → Open Positions table updated → Portfolio Summary refreshed.
- **Terminal live-update verified**: interval switching (1h → 4h → 1d) reloads cleanly with no stale candles; LIVE pill and `updated Ns ago` counter tick correctly.

### Not changed

- Backend, models, endpoints, subsystems — untouched. `/api/` still reports `version: 1.0.0` with 827 features (L1=519, L2=146, L3=90, L4=72).
- All 127 backend pytests still pass (last run in v1.0.0 milestone verification).
- No new dependencies.

---
## v1.0.0 — v1.0 Milestone (July 2025)

**Theme**: Atlas leaves prototype status. A complete, polished, production-ready v1.0 application: Paper Trading is now a first-class subsystem, Prediction is a full pro dashboard, App.js is properly split into reusable components, every subsystem end-to-end verified.

### Added — Paper Trading (NEW L5 sibling subsystem)

- **`/app/backend/paper_trading/`** — new module, DEC-021 lane-clean (never imports from `atlas_core`, `decision_engine`, or `learning_system`).
  - `contracts.py` — `PaperAccount`, `PaperPosition`, `PaperTrade` dataclasses. Every trade permanently snapshots the full 22-signal Atlas recommendation, ML advisor payload, analogues (v1 or v2), L3 regime, L4 embedding ids.
  - `engine.py` — `open_position`, `mark_to_market`, `check_tp_sl_hit`, `close_position`. Symmetric adverse slippage (long-entry pays uptick, long-exit pays downtick, symmetric for short). Per-side fees applied in bps.
  - `analytics.py` — `compute_metrics` (Sharpe / Sortino / Calmar / max DD / profit factor / expectancy / avg RR / win rate / avg holding / largest win/loss / total fees), `build_equity_curve`.
  - `store.py` — async Mongo persistence: `paper_accounts`, `paper_positions`, `paper_trades`.
  - `api.py` — 14 routes under `/api/paper/*`: meta, account (get/reset/settings), positions (open, list-open, mark, close), trades (list, get, CSV export), analytics.
- **Frontend — `components/atlas/PaperView.jsx`** (new 8th tab, "Paper"):
  - Portfolio Summary card grid (Equity, Total P&L, Realized, Unrealized, Win Rate, Max DD).
  - Equity Curve area chart (lightweight-charts).
  - Open Positions table with pending TP/SL and inline close.
  - Performance Statistics — 12 metrics (Sharpe, Sortino, Calmar, Profit Factor, Expectancy, Avg RR, Avg Win/Loss, Largest Win/Loss, Avg Holding, Total Fees).
  - Trade Journal — full history table with symbol / side / since / until filters, CSV export, per-row "View" opening a Trade Details modal (3-column layout: Execution / Outcome / Atlas Recommendation Snapshot; grid of all 22 signals at entry; analogue summary; risk block; journal note).
  - Open Position dialog — auto-populates side, stop, and TP from the current Atlas recommendation's `sizing.stop_pct` / `sizing.take_profit_pct`; user can override any field before submit.
  - "Mark Now" button — pulls latest close for every open position and auto-closes any TP/SL hit within the bar.
  - "Reset Account" — wipes positions & history, re-seeds $100k default.

### Added — Prediction Dashboard rebuild

- `POST /api/predict/compare` — new endpoint. Runs multiple models (XGBoost + RandomForest by default) on the same window and returns per-model direction, P(up), confidence, test accuracy, plus an `agreement` block with consensus (UP/DOWN/MIXED) and vote count.
- `POST /api/predict/train` — now returns an `expected_move` block: `{horizon_bars, sigma_pct, expected_move_pct, method}` computed as `mean|logret| · √horizon · confidence`.
- **Frontend — `components/atlas/PredictionView.jsx`** (rebuilt): current-prediction panel (big colored UP/DOWN, confidence %, test accuracy), probability distribution bar (green P(up) + red P(down)), expected move panel (directional %, 1σ range), model comparison table with consensus badge, feature importance bars, prediction history table filtered by symbol.

### Changed — Frontend structure

- **App.js split**: 1564 LOC → 88 LOC pure shell. All views extracted to `frontend/src/components/atlas/`:
  - `helpers.js`, `Header.jsx`, `primitives.jsx` (PriceChart, HealthArc, Metric, DirectionPill — now numeric + string aware, DonutContribution, EvidenceList, RSMiniChart), `DecisionView.jsx`, `TerminalView.jsx`, `FeatureExplorer.jsx`, `CorrelationView.jsx`, `PredictionView.jsx`, `LearningView.jsx`, `PaperView.jsx`, `About.jsx`.
- **CSS polish** — new modal system (backdrop / card / header / body / footer), `atlas-table` (sticky header, hover rows, uppercase caps), `metric-card`, `prob-bar` (green/red gradient halves), empty-state / spinner / error-state, `pill` variants (LONG/SHORT/UP/DOWN semantics), responsive breakpoints for narrow viewports.
- Header rewritten as `Header.jsx` — 8 tabs (Paper added), v1.0.0 subtitle.

### Changed — Versioning

- `atlas_core.__version__` → `"1.0.0"`.
- FastAPI title → `"Atlas Terminal API"` version `"1.0.0"`.
- `GET /api/` root → `{"version": "1.0.0", "registered_features": 827}`.
- `GET /api/paper/` → `{"version": "1.0.0", "supports": {...}}`.

### Registry

Unchanged. **827 features** total — L1=519, L2=146, L3=90, L4=72. No new features were added; v1.0 is a productisation milestone, not a feature-expansion milestone.

### Verified

- **Backend pytest: 127 / 127 pass in 97.8s** (115 previous + 12 new `TestPaperTradingV1`). Full report at `/app/v100_verification_report.md`.
- **Golden tests: 39 / 39.**
- **Frontend end-to-end (auto testing agent):** all 8 tabs verified interactively. Paper Trading flagship path (open dialog → auto-populate stop & TP from Atlas → submit → mark-now → auto-close on TP/SL → journal → details drawer with full snapshot) works flawlessly. One critical bug caught (missing `useMemo` import in `FeatureExplorer.jsx`) and fixed. Zero runtime errors, zero console errors, zero 4xx/5xx network errors.

### Decisions (see DECISIONS.md)

- **DEC-021**: Paper Trading is a Layer-5 sibling of Decision Engine and Learning System — it never imports from Atlas Core, never imports from `decision_engine`, never imports from `learning_system`. All recommendation payloads flow in as plain dicts at the FastAPI composition layer. Enforced by `TestPaperTradingV1.test_paper_never_imports_atlas_core_or_ml_siblings`.

---
## v0.13.1 — v1.0 Polish Pass (July 2025)

**Theme**: Feature freeze. Audit-only. No new capabilities, layers, models, brokers, indicators, or architecture. Five real UX bugs surfaced by walking every tab as a real end user; each has a targeted, minimal-diff fix. **All fixes verified by the automated frontend testing agent.**

### Fixed

- **Interval dropdown consistency across tabs.** Terminal offered `5m, 15m, 30m, 1h, 4h, 1d, 1wk` while Decision offered only `15m, 30m, 1h, 4h, 1d, 1wk`. If a user selected `5m` on Terminal and switched to Decision, the Decision dropdown visually rendered a different value than the shared `interval` state — a silent user-facing bug. Fixed by hoisting a single `INTERVAL_OPTIONS` constant at the top of `App.js` and using it in both tabs.
- **FeatureExplorer stale chart.** After selecting a feature, changing provider / symbol / interval on another tab left the feature-value chart showing stale data from the previous market context. Added a targeted `useEffect` in `FeatureExplorer` that refetches values when any of those change while a selection is active.
- **Prediction stale results.** Training on SYN-EQUITY then switching symbol used to leave a misleading result card on screen claiming to be about the previous symbol. A new `useEffect` in `PredictionView` clears the result on `provider / symbol / interval` change. The model dropdown intentionally does NOT clear the result — flipping models on the same market is a valid comparison flow.
- **Learning tab Refresh button.** Was `onClick={refresh}`, which meant React passed the click Event object into `refresh(signal)`, so axios received a bogus signal on every manual refresh. Wrapped in `() => refresh()`.
- **About tab stale test count.** Showed "Golden Tests: 36/36 · Backend regression: 31/31" — long-obsolete numbers. Updated to "Backend regression: 115/115 pytests pass (serial)".

### Verified

- Backend: **115/115 pytests pass serial**. No test changes, no regressions.
- Frontend: automated testing agent walked every tab, exercised each of the 5 reproduction scenarios, confirmed zero page errors, zero unhandled promise rejections, and the header still reads `v0.13.0 · L1+L2+L3+L4 · 827 FEATURES`.

### Not changed (deliberate, feature-freeze)

- No new capabilities. No new endpoints. No new models. No new indicators. No new tabs.
- Correlation and Prediction tabs still intentionally have no provider / symbol / interval dropdowns of their own — they follow the shared state driven by Decision and Terminal.
- `App.js` is still a single file. Component split remains deferred to a future refactor session.

---


## v0.13.0 — Session 13 Milestone · Broker-ready Live Engine + Neural Suite + Regime-Conditional Voter + Backtest Persistence (July 2025)

**Theme:** Cleanly move Atlas toward a stable v1.0 by prioritising
correctness, reliability, and architectural quality over feature count.
Five sub-milestones, one shipment.

Atlas Core is untouched (still 827 features · L1=519 · L2=146 · L3=90
· L4=72). DEC-017 preserved (regression-tested). DEC-018 satisfied
twice (Transformer + TFT added with zero framework change). DEC-019
preserved (advisor still additive / bounded / dissent-never-overrides).

### Added — DEC-020 · Broker-ready `LiveExecutionEngine`

- **`learning_system/backtest/broker/`** — new sub-package:
  - `base.py` — `BrokerAdapter` abstract contract. Immutable
    receipts (`BrokerOrder` / `BrokerPosition` / `BrokerAccount`).
    Mandatory idempotency via `client_order_id`. `dry_run` and
    `is_paper` safety flags at the adapter layer so they survive
    strategy bugs.
  - `simulated.py` — `SimulatedBrokerAdapter`. Deterministic
    in-memory broker used by tests and dry-runs. NOT a real broker;
    it exists so `LiveExecutionEngine` can be exercised end-to-end
    today without any credentials.
- **`learning_system/backtest/execution/live.py`** — rewritten from a
  stub into a real broker-driven implementation. Same
  `ExecutionEngine` contract as `PaperExecutionEngine`. Every
  `open_position` / `close_position` is translated into a broker
  order; the resulting fill (price + fees) is used as the trade's
  realised numbers.
- **`BacktestEngine.build(spec, broker_adapter=…)`** now accepts an
  optional broker adapter. `execution_mode="live"` without an adapter
  raises a helpful `NotImplementedError` explaining how to wire one
  in. When a `SimulatedBrokerAdapter` is provided, a full backtest
  runs against the live engine unchanged.
- Adding a real broker (Alpaca / IB / Binance / …) is a **single-file
  addition** of a concrete `BrokerAdapter` subclass; strategies do not
  change.

### Added — Transformer + TFT neural plug-ins (DEC-018)

- **`learning_system/models/neural/transformer_model.py`** — compact
  encoder-only Transformer with learned positional embedding, GELU
  activations, and last-token classification head. Registered as
  `kind="transformer"`. Gradient-sensitivity feature importances.
- **`learning_system/models/neural/tft_model.py`** — simplified
  Temporal Fusion Transformer with Variable-Selection Network + Gated
  Residual Network + interpretable multihead self-attention.
  Registered as `kind="tft"`.
- Both plug-ins satisfy the DEC-018 `BaseModel` contract exactly
  (`fit` · `predict_proba` · `feature_importances` · `to_disk` ·
  `from_disk`). Framework unchanged. **7 model kinds registered
  now**: `logreg`, `randomforest`, `gradientboost`, `xgboost`, `lstm`,
  `transformer`, `tft`.

### Added — Regime-conditional voter wiring in `recommend()`

- `decision_engine/recommender.py` accepts a new opt-in flag
  `use_regime_conditional_weights: bool`. When True, calls the
  existing `learn_regime_conditional_weights()`, detects the CURRENT
  L3 regime code from `market_regime.regime.active_state_code`, and
  votes with the per-regime weight vector for that code. Falls back
  to the global learned weights when the current regime has too few
  samples.
- Response now carries a new `regime_conditional` block with
  `active_regime_code`, `fallback`, and `n_regimes_available` — fully
  explainable.
- `POST /api/decision/recommend` gains the matching
  `use_regime_conditional_weights` field.
- Regression-tested that `use_regime_conditional_weights=False`
  (default) preserves v0.12.0 output shape bit-identically.

### Added — Backtest persistence + browsable history

- **`learning_system/registry/backtest_tracker.py`** — new Mongo
  collection `learning_backtests`. Every `POST /api/learning/backtest/run`
  is persisted (best-effort; a persistence failure never breaks the
  actual backtest).
- **`GET /api/learning/backtest/list`** — recent backtests, filterable
  by `model_id` and `symbol`; excludes bulky `equity_curve`/`trades`
  arrays for list-view speed.
- **`GET /api/learning/backtest/{id}`** — full backtest document.
- **`GET /api/learning/registry/stats`** — response now includes a
  `backtests: {n_backtests}` block.

### Added — Frontend integration (App.js still single-file)

- Header refreshed to **`v0.13.0 · L1+L2+L3+L4 · 827 FEATURES`**.
- Decision tab: **`Regime-conditional` checkbox** next to the existing
  learned-weights toggle. Active-regime + fallback readout under the
  recommendation card when the new weight source is in use.
- Learning tab: **Backtest History** panel below the selected-model
  actions. Auto-refreshes with the rest of the tab. Shows
  `backtest_id`, `symbol`, `interval`, total return %, Sharpe,
  max-DD %, and trade count for the last 15 runs.
- About tab copy updated: 22 signals · voter (manual / learned /
  regime-conditional) · Learning-System advisor · 7 model plug-ins ·
  BrokerAdapter contract.
- Interrupted Session-12 error-handling repair completed at the top
  of App.js: `App` root effect now uses `makeAbortable` + graceful
  fallback for `/market/symbols` and `/registry/stats`; every axios
  catch surfaces a user-visible error state rather than swallowing
  silently.

### Regression tests (`115/115 serial · was 100/100 at v0.12.0`)

- **`TestSession13Broker`** (5): `BrokerAdapter` abstract-contract
  audit, `SimulatedBrokerAdapter` idempotency on `client_order_id`,
  dry-run does not execute, `LiveExecutionEngine` end-to-end via
  `SimulatedBrokerAdapter`, `BacktestEngine.build(execution_mode="live",
  broker_adapter=…)` wires correctly.
- **`TestSession13NeuralPlugins`** (5): both new kinds registered,
  each satisfies the plug-in contract, each round-trips exactly via
  `to_disk` + `from_disk`.
- **`TestSession13RegimeConditionalRecommender`** (2): flag-off is
  bit-identical to v0.12.0; flag-on produces a `regime_conditional`
  block with `active_regime_code`.
- **`TestSession13BacktestPersistence`** (3): list endpoint exists,
  stats includes `backtests`, a run round-trips through Mongo and is
  retrievable by `backtest_id`.
- The pre-existing `test_live_engine_is_a_stub` was upgraded to
  `test_live_engine_requires_broker_adapter` — asserts the new
  architecture (helpful `NotImplementedError` without adapter · full
  operation with adapter).

### Not shipped this session (deferred, deliberate)

- **App.js component split** — file is now ~1500 LOC (grew by ~60 this
  session). Compiles cleanly, all six tabs are green in Playwright,
  no console errors, no unhandled promise rejections. The refactor
  buys clarity, not correctness; deferred to a future session that
  can dedicate the full budget to it.
- **Real broker adapters** — Alpaca / IB / Binance require
  credentials + external API playbooks. The DEC-020 interface is now
  in place; a real adapter is a single-file addition when a broker is
  approved.
- **Frontend read-only "browse experiments/backtests by id"** — the
  Learning tab now shows the last-15 history; a deep-link details
  drawer is deferred.
- **LightGBM / CatBoost plug-ins** — need PyPI deps.
- **Reproducibility harness · Postgres migration** — unchanged debt.

### Notes

- **Atlas Core untouched**. No L1/L2/L3/L4 changes. `atlas_core/__version__`
  stays at 0.9.0 (Book 1 Ch. 6.5 · Ch. 6.4 preserved).
- **`decision_engine/` and `learning_system/` still never import each
  other** — DEC-017 regression test still passes.
- **DEC-020** is the only new ADR this session. Every previous ADR is
  preserved.

---



## v0.12.0 — Session 12 Milestone · Backtest + Neural + Frontend (July 2025)

**Theme:** Three-in-one engineering milestone. **(1) Walk-forward
Backtesting Framework** — the missing measurement layer. Every future
improvement to Atlas is now quantifiable. **(2) Deep-learning plug-in
framework** — PyTorch (CPU) approved and installed; LSTM plug-in
registered; the DEC-018 model contract accepts neural nets without
architectural change. **(3) Frontend integration** — App.js exposes
the v0.10.0–v0.11.0 machinery: `ml_advisor` toggle, `analogue_schema`
selector, `ml_confidence_bonus` badge, `ml_dissent` warning, plus a
new **Learning tab** for experiments, model registry, walk-forward
backtest, and inference.

Atlas Core is untouched (still 827 features). DEC-017 preserved
(regression-tested). No new ADRs — DEC-018 already covers neural
plug-ins; DEC-019 already covers advisor integration.

### Added — Walk-forward Backtesting Framework

- **`learning_system/backtest/`** — new subsystem:
  - `contracts.py` — `BacktestSpec`, `StrategyPolicy`, `Trade`,
    `EquityPoint`, `BacktestResult` (all JSON-safe dataclasses).
  - `portfolio.py` — cash / open position / closed trades bookkeeping.
  - **`execution/base.py`** — `ExecutionEngine` ABC. **The same
    interface is used for paper backtesting today and future live
    trading — swap the concrete engine, everything else stays the
    same.**
  - `execution/paper.py` — `PaperExecutionEngine` — simulated fills
    at bar close with symmetric slippage + per-side fees.
  - `execution/live.py` — `LiveExecutionEngine` — interface stub;
    every method raises `NotImplementedError`. Reserved for future
    broker adapters (Alpaca / IB / Binance / …). Strategy code above
    will never change.
  - `strategy.py` — deterministic `Strategy.decide(prob_up, dir)`
    → `LONG | SHORT | CLOSE | HOLD` from explicit thresholds.
  - `metrics.py` — total_return_pct, annualised_return_pct, sharpe,
    sortino, max_drawdown_pct, calmar, n_trades, hit_rate, avg_win,
    avg_loss, profit_factor, final_equity. All finite floats.
  - `engine.py` — `BacktestEngine` walks time forward, batch-predicts
    the model, converts probabilities → actions → execution → records
    equity + trades. Force-closes at the last bar.

- **`POST /api/learning/backtest/run`** — API surface for the framework.

### Added — Deep-learning plug-in framework

- **PyTorch approved and installed** (`torch>=2.0.0`, CPU wheel via
  `https://download.pytorch.org/whl/cpu`, added to `requirements.txt`).
- **`learning_system/models/neural/lstm_model.py`** — first real
  neural plug-in. Registered as `kind="lstm"` via `@register_model`
  (DEC-018). Implements the full `BaseModel` contract:
  - `fit` — trains an LSTM classifier (deterministic given `seed`)
    on windowed feature sequences.
  - `predict_proba` — batch-predicts P(up); leading `seq_len` rows
    stay at 0.5 (insufficient history).
  - `feature_importances` — gradient-sensitivity of P(up) w.r.t.
    inputs at the last time-step, averaged over a probe batch.
  - `to_disk` / `from_disk` — round-trip serialisable via `joblib` +
    `state_dict`. Verified bit-equal predictions after reload.
- **`learning_system/models/neural/__init__.py`** — guards `import
  torch` so the rest of Atlas keeps working if PyTorch is uninstalled.
- **Framework unchanged.** `TrainingPipeline`, `Registry`,
  `InferencePipeline`, `BacktestEngine` all consume LSTM through the
  same DEC-018 interface with zero code change.

### Added — Frontend

- **Header** — refreshed from `v0.8.0 · L1+L2+L3 · 755 FEATURES`
  (stale since v0.9.0) to `v0.12.0 · L1+L2+L3+L4 · 827 FEATURES`.
- **Decision tab** — new controls:
  - `ML Advisor` checkbox → sets `ml_advisor: true` on
    `/api/decision/recommend`.
  - `Analogues` dropdown → `v1 (L1-heavy)` (default) or
    `v2 (L4 embed)` — sets `analogue_schema`.
  - `ml_confidence_bonus` badge (green) — shows when the bounded
    LS bonus fires; displays `+X.X% confidence from LS`.
  - `ml_dissent` warning banner (red) — shows the warning text
    verbatim when the dissent detector fires.
  - `ml_advisor` info line when the advisor is available but
    neither bonus nor dissent fires.
  - Analogue schema readout (`v1|v2` · N dims).
- **New "Learning" tab (`LearningView`)** — single-page dashboard:
  - Registry stats (models / experiments counts).
  - Train-new-experiment form (model kind dropdown includes `lstm`,
    label kind, horizon).
  - Stored models list (click to select).
  - Recent experiments list.
  - Selected-model actions: `Predict on current symbol` +
    `Walk-Forward Backtest`.
  - Backtest result grid (Return / Sharpe / Max DD / Hit Rate +
    trades / final equity / bars / execution mode).
- **No App.js component split this session** — the file remains
  single-file (~1300 LOC now); further modularisation deferred.

### Added — Tests

- `TestBacktestV012` (**6 tests**): execution-engine contract
  parity, paper round-trip PnL is realised, live-engine is a stub,
  strategy transitions are deterministic, backtest engine
  end-to-end on synthetic, `/api/learning/backtest/run` API.
- `TestDeepLearningV012` (**3 tests**): LSTM registered, LSTM
  satisfies plug-in contract, LSTM round-trip serialisation is
  bit-equal.

### Numbers

- **Registered features: 827** — Atlas Core still untouched
  (L1=519, L2=146, L3=90, L4=72).
- **Decision Engine signals: 22** — unchanged. Voter sum = 1.00.
- **Learning System models registered: 5** (was 4) — adds `lstm`.
- **Backend pytests: 100/100 pass serial** (was 91). Adds 9 new
  tests across `TestBacktestV012` (6) + `TestDeepLearningV012` (3).
- **New endpoints: 1** (`POST /api/learning/backtest/run`).
- **New API knobs on `/api/decision/recommend`: 0** (existing
  `ml_advisor`, `analogue_schema` from v0.11.0 now used by the UI).

### Not shipped (deliberate)

- Transformer / TFT / RL model plug-ins — deferred; the framework
  accepts them via `@register_model` without any code change.
- LightGBM / CatBoost plug-ins — deferred.
- Full App.js component split — the file is single-file; targeted
  additive edits shipped; split deferred to a dedicated session.
- Live-broker adapter under `learning_system/backtest/execution/live.py`
  — stub in place; concrete adapter deferred.
- Persisting backtest results to Mongo (currently returned directly).
- Wiring backtest metrics into the Decision Engine's confidence
  formula — deferred; requires its own ADR.

---

## v0.11.0 — Session 11 Milestone · DE ↔ LS Integration (July 2025)

**Theme:** The Learning System stops being a stand-alone framework and
starts making the Decision Engine measurably more intelligent — while
preserving every architectural invariant. Atlas Core is untouched;
DEC-017 (peer isolation) is preserved; every LS influence is bounded,
opt-in, and explicitly reported in the recommendation output. The LS
is an **advisor to** the Decision Engine, never a **replacement for**
it.

Authorised by **DEC-019** (DE ↔ LS integration protocol: additive ·
bounded · dissent-never-overrides · DE never imports LS). No new ADRs
in the frontend, no new Registry features (Atlas Core is untouched at
827 features).

### Added — Decision Engine ↔ Learning System integration

- **`decision_engine/voter.py`** — `vote()` accepts a new optional
  `ml_agreement: Dict | None` argument. When provided AND directions
  match, adds a bounded confidence bonus of `min(0.15, 0.30 * (agreement − 0.5))`.
  A new response key `ml_confidence_bonus` reports the bonus,
  direction match, LS agreement, model count, cap, and reason.
  When `ml_agreement` is absent (or `None`), the bonus is 0 and the
  voter is bit-identical to v0.10.0.
- **`decision_engine/recommender.py`** — accepts a new optional
  `ml_advisor: Dict | None` parameter that flows into `vote()` and
  drives the DEC-019 dissent detector. New response keys:
  * `ml_advisor` — the LS payload used (or `{available: False, …}`),
  * `ml_confidence_bonus` — from the voter,
  * `ml_dissent` — the dissent detector's verdict
    (`{fired: bool, voter_direction, ls_direction, probability_up,
     agreement, warning}`).
  Also accepts `analogue_schema: "v1"|"v2"`.
- **`decision_engine/analogues.py`** — schema is now versioned.
  `find_analogues(..., schema="v1")` (default) preserves the 19-dim
  L1-heavy space unchanged for back-compat. `schema="v2"` uses
  `L4_EMBEDDING_IDS` (v0.9.0 handshake constant) plus 5 curated L2/L3
  confidence features (`fractal_relationships.regime.self_similarity_score`,
  `trend_relationships.regime.directional_consensus_score_20`,
  `trend_state.statistics.active_state_confidence`,
  `range_state.statistics.active_state_confidence`,
  `market_regime.statistics.active_state_confidence`) — 15-dim
  representation combining L1+L2+L3+L4.
- **`decision_engine/weight_learner.py`** — new
  `learn_regime_conditional_weights()` partitions the historical
  signal matrix by the L3 `market_regime.regime.active_state_code`
  and fits **one interpretable LR per regime**. Every weight vector
  is a normalised `|β|`. Regimes with fewer than
  `min_samples_per_regime` samples fall back to the global vector
  (annotated `fallback="global"`). Fully deterministic and
  explainable — this is NOT a call into the LS.

### Added — API surface

| Route | Method | Purpose |
|---|---|---|
| `/api/decision/recommend` | POST | new params: `ml_advisor: bool = False`, `ml_advisor_kind: str?`, `ml_advisor_top_k: int = 3`, `analogue_schema: "v1"\|"v2" = "v1"`. When `ml_advisor: true`, the FastAPI layer fetches `DEBridge.model_ensemble_agreement_score` + `DEBridge.latest_calibrated_prob_up` and passes them as a plain-dict `ml_advisor` payload into `recommend()`. Fully backwards-compatible. |
| `/api/decision/regime_conditional_weights` | POST | new endpoint — 1 interpretable LR per L3 regime code. Fully deterministic. |

### Added — Tests

- `TestDeLsIntegrationV011` (**13 tests**): Book-1 no-cross-imports
  regression (DEC-017 preserved); voter bit-identical when advisor
  absent; bounded bonus + direction-gate; confidence saturation;
  dissent detector rules (fires / no-fire on voter uncertainty /
  no-fire without LS); analogues default schema stays v1; v2 uses
  L4 embeddings; regime-conditional weight-sum invariants; API
  round-trip without advisor; API round-trip with advisor + v2
  analogues; regime-conditional endpoint round-trip.

### Numbers

- **Registered features: 827** — unchanged. Atlas Core is untouched.
- **Decision Engine signals: 22** — unchanged. Voter sum = 1.00.
- **Backend pytests: 91/91 pass serial** in ~35 s (was 78/78 at v0.10.0).
  Adds `TestDeLsIntegrationV011` (13 tests).
- **New endpoints: 1** (`/api/decision/regime_conditional_weights`).
- **New API knobs on `/api/decision/recommend`: 4**
  (`ml_advisor`, `ml_advisor_kind`, `ml_advisor_top_k`, `analogue_schema`).

### Backwards compatibility

- **Existing frontend integrations are unaffected.** When the caller
  does NOT set `ml_advisor: true` and leaves `analogue_schema` at its
  default `"v1"`, every response field that existed at v0.10.0 is
  bit-identical. The three new response keys (`ml_advisor`,
  `ml_confidence_bonus`, `ml_dissent`) report the safe "not
  requested" / "not applicable" state.
- The existing `/api/decision/learned_weights` endpoint is unchanged.
- The existing `/api/ensemble/train` legacy endpoint is unchanged.
- The existing `find_analogues(df, k, horizon)` signature is unchanged;
  the new `schema` kwarg defaults to `"v1"`.

### Not shipped (deliberate)

- Deep-learning plug-ins in the Learning System — deferred (Session 12+).
- Frontend UI to expose `ml_advisor` / `ml_dissent` / regime-conditional
  weights / schema-v2 analogues — deferred; App.js remains a single-file
  ~1040-LOC bundle.
- LightGBM / CatBoost plug-ins — deferred.
- Online learning / RL / portfolio optimisation / multi-asset reasoning
  — designed-for through the DEBridge interface but not implemented.
- Wiring `ml_advisor` into the historical `/api/decision/history` view.

---

## v0.10.0 — Session 10 Milestone · Learning System (July 2025)

**Theme:** Ships the **complete Learning System framework** as a
sibling L5 subsystem to the Decision Engine. Atlas Core (L1–L4) is
untouched. Book 1 Inv-5.6 respected: ML lives outside `atlas_core/`.
The Learning System now owns the full ML lifecycle — datasets, labels,
splits, training, evaluation, model registry, experiment tracking,
inference — while remaining model-agnostic (DEC-018 plug-in contract).

Authorised by **DEC-017** (sibling L5 subsystem) and **DEC-018** (model
plug-in contract). Specified by `docs/LEARNING_SYSTEM.md`.

### Added — Learning System package

- **`/app/backend/learning_system/`** — new top-level L5 subsystem, peer
  to `decision_engine/`:
  - `contracts.py` — `DatasetSpec`, `SplitSpec`, `ModelSpec`,
    `ExperimentSpec`, `ExperimentResult`, `FoldMetrics`,
    `InferenceRequest`, `Prediction` + `to_json_safe` helper. All
    dataclasses; JSON-serialisable through `asdict()`.
  - `dataset/feature_matrix.py` — thin wrapper over
    `atlas_core.compute.compute_features` with strict NaN policies
    (`any` / `all` / `none`).
  - `dataset/labels.py` — 4 deterministic label kinds:
    `sign`, `quantile`, `vol_norm`, `triple_barrier`
    (López de Prado). All closed-form; no ML.
  - `dataset/splits.py` — 3 leakage-safe split kinds:
    `walk_forward`, `expanding` / `expanding_window`,
    `purged_kfold` (L-de-P; embargo around test block).
  - `dataset/builder.py` — `build_dataset` + `preview_dataset`
    → immutable `Dataset` with `fingerprint` (SHA-1 of spec + shape).
  - `models/base.py` — `BaseModel` abstract contract
    (`fit` / `predict_proba` / `predict` / `feature_importances` /
    `to_disk` / `from_disk`).
  - `models/__init__.py` — `MODEL_REGISTRY` + `register_model` +
    `instantiate`. Model-agnostic. The pipeline never mentions a
    concrete model class.
  - `models/sklearn_models.py` — plug-in wrappers for
    `LogisticRegression`, `RandomForestClassifier`,
    `GradientBoostingClassifier`. Registered as `logreg`,
    `randomforest`, `gradientboost`.
  - `models/xgboost_model.py` — plug-in wrapper for `XGBClassifier`
    (kind `xgboost`).
  - `models/neural/` — reserved namespace for LSTM / Transformer /
    TFT plug-ins when `torch` is approved. Empty at v0.10.0.
  - `training/metrics.py` — `accuracy`, `hit_rate`, `log_loss`,
    `brier`, `edge_rate`, `information_coefficient` (Spearman ρ).
  - `training/pipeline.py` — `TrainingPipeline` — orchestrates
    dataset build → split generation → per-fold fit + score →
    aggregate. Runs on any registered model kind. Runs inside
    `run_in_executor` when called from FastAPI so the event loop
    stays responsive.
  - `training/walk_forward.py` — `run_walk_forward` convenience.
  - `evaluation/evaluator.py` — stand-alone `evaluate(model, X, y)`
    for out-of-sample scoring.
  - `registry/model_registry.py` — `ModelRegistry`. Filesystem
    artifacts under `LEARNING_SYSTEM_ARTIFACT_ROOT`
    (default `/app/backend/learning_system/artifacts/`) via
    `joblib.dump`. Mongo metadata in `learning_models` collection.
    `save`, `get`, `list`, `best`, `load_model`, `stats`.
  - `registry/experiment_tracker.py` — `ExperimentTracker`. Mongo
    collection `learning_experiments`. `record`, `get`, `list`,
    `stats`.
  - `inference/pipeline.py` — `InferencePipeline`. Loads a model
    by `model_id`, rebuilds the feature matrix on the latest OHLCV,
    scores the last row, returns a `Prediction`.
  - `integration/decision_engine_bridge.py` — `DEBridge`. Read-only
    helpers: `latest_calibrated_prob_up`,
    `model_ensemble_agreement_score`. Not called by the DE at
    v0.10.0; wiring deferred.
  - `api.py` — FastAPI router mounted under `/api/learning/*`.

### Added — API surface (`/api/learning/*`)

| Route | Method | Purpose |
|---|---|---|
| `/api/learning/` | GET | meta + registered model / label / split kinds |
| `/api/learning/registry/stats` | GET | `{models, experiments}` |
| `/api/learning/models/registered` | GET | list of pluggable kinds |
| `/api/learning/datasets/preview` | POST | preview dataset shape + class balance |
| `/api/learning/experiments/run` | POST | full walk-forward experiment |
| `/api/learning/experiments` | GET | list past experiments |
| `/api/learning/experiments/{id}` | GET | experiment detail |
| `/api/learning/models` | GET | list persisted models |
| `/api/learning/models/best` | GET | top-N models by metric |
| `/api/learning/models/{id}` | GET | model metadata |
| `/api/learning/inference/predict` | POST | run a persisted model on fresh OHLCV |
| `/api/learning/bridge/prob_up` | GET | DE bridge — latest calibrated prob-up |
| `/api/learning/bridge/ensemble_agreement` | GET | DE bridge — top-K model agreement |

### Added — Tests

- `TestLearningSystemV010` (**15 tests**): label semantics (sign,
  triple_barrier); split invariants (walk_forward non-overlap,
  purged_kfold embargo); model plug-in uniformity across all 4
  registered kinds; model round-trip serialisation; metric bounds;
  end-to-end training pipeline; three API round-trips
  (meta / dataset preview / experiment run + persistence + inference);
  DEC-017 no-cross-imports; Inv-6.4 no upward-import from
  `learning_system` into `atlas_core`; Inv-5.6 Registry unchanged
  (no new features added at v0.10.0).

### Added — Documentation

- `docs/LEARNING_SYSTEM.md` — single overarching framework spec (same
  pattern as `L3_MARKET_UNDERSTANDING.md` and `L4_REPRESENTATION.md`).
- `docs/DECISIONS.md` — **DEC-017** (sibling L5 subsystem),
  **DEC-018** (model plug-in contract).
- `docs/PROJECT_CONTEXT.md`, `docs/HANDOVER.md`, `docs/CHANGELOG.md`
  synced. Per continuation-directive lightweight documentation policy,
  other docs (ARCHITECTURE, README, ROADMAP, KNOWN_LIMITATIONS,
  GOVERNANCE, BOOK1_DIGEST, ENGINES, PERSPECTIVES) **not re-synced**.

### Numbers

- **Registered features: 827** (unchanged; Atlas Core is untouched).
- **Learning System models registered: 4** (`logreg`, `randomforest`,
  `gradientboost`, `xgboost`).
- **Label kinds registered: 4** (`sign`, `quantile`, `vol_norm`,
  `triple_barrier`).
- **Split kinds registered: 4** (`walk_forward`, `expanding`,
  `expanding_window`, `purged_kfold`).
- **Decision Engine signals: 22** (unchanged — DEC-017 keeps the DE
  untouched at v0.10.0).
- **Backend pytests: 78/78 pass serial** in ~31 s (was 63). Adds the
  15-test `TestLearningSystemV010` class.

### Not shipped (deliberate)

- LightGBM / CatBoost — not registered (extra deps not approved yet;
  the plug-in contract lets them be added in one file).
- LSTM / Transformer / TFT / RL — deferred (needs `torch`; the
  `models/neural/` namespace is reserved).
- Regime-conditional voter weighting driven by
  `RegimeState` + `MetaConfidence` — separate milestone.
- Analogue z-space bump using `L4_EMBEDDING_IDS` +
  Learning-System predictions — separate milestone.
- Retiring `decision_engine/ml/*` and `decision_engine/weight_learner.py`
  — kept as-is for backwards compatibility.
- Frontend UI for the Learning System — App.js still single-file.
- Reproducibility harness (deterministic hash of `ExperimentResult`
  for cross-run identity) — deferred.
- Wiring `DEBridge` into the live Decision Engine outputs — must be
  justified case by case in a follow-up milestone.

---

## v0.9.0 — Session 9 Milestone · Layer 4 Representation (July 2025)

**Theme:** Ships Layer 4 (**Representation**) end-to-end in a single
milestone: the L4 access contract, a layer-local representation
kernel, five representation modules, the L4 decision-engine
integration, a new validation-framework property gate, a stable
L4→L5 handshake constant, and full test coverage. Book 1 Ch. 5
exemplars (cross-module interactions, meta features, feature
embeddings, dimensionality reduction, multi-scale representations,
state encodings) are now first-class Registry citizens and the
Atlas ↔ ML handshake is live.

Authorised by **DEC-016** (L4 access contract). Specified by
`docs/L4_REPRESENTATION.md`.

### Added — Layer 4 subsystem

- **`atlas_core/layers/l4_representation/`** — new layer:
  - `_layer_bridge.py` — DEC-016. Parallel to L2's `_l1_bridge` and
    L3's `_layer_bridge`, but L4-owned; exposes `l1_series(df, id)`,
    `l2_series(df, id, context=None)` **and** `l3_series(df, id)`
    with per-call identity-keyed caches (all three flushed by the
    orchestrator, matching DEC-011). Honours
    `df.attrs["_atlas_context"]` for peer-aware L2 lookups (DEC-007).
  - `_representation_kernel.py` — layer-local primitives (Book 1
    Ch. 10 discovery discipline; not promoted to `engines/` yet):
    `rolling_zscore`, `interaction` (product / ratio / min / max /
    absdiff / sign_agree), `one_hot`, `quantile_bin`, `rolling_rank`,
    `rolling_entropy`, `rolling_dispersion`, `rolling_pca`
    (deterministic, roll-forward, no future leakage).
  - `cross_module_interactions.py` (19 features) — L1 × L2, L2 × L3,
    L3 × L1 signed / magnitude interactions.
  - `meta_features.py` (15 features) — rolling means, std, entropy,
    consensus over L2/L3 outputs ("features about features").
  - `state_encodings.py` (14 features) — deterministic (label-free)
    ordinal, rank, and one-hot encodings of L3 states and curated
    L1/L2 numerics.
  - `multi_scale_representations.py` (14 features) — same primitive
    summarised across ≥ 3 scales (Hurst, slope, R/S, volatility,
    consensus).
  - `embeddings.py` (10 features) — rolling deterministic PCA of a
    curated ~20-feature L1+L2+L3 matrix onto the top-5 components
    (`pc1…pc5`) + explained-variance ratios (`evr_1…evr_5`),
    `lookback=250`.

  All 72 L4 features are layer=4, deterministic, closed-form.
  **No supervised learning, no labels, no gradients** (Book 1 Inv-5.6).

- **`L4_EMBEDDING_IDS`** exported from
  `atlas_core.layers.l4_representation.__init__` — stable pointer to
  the 10 embedding features. Future analogue z-space v2 and any
  Learning System consumer read from this constant so the L4→L5
  handshake never breaks silently.

### Added — Decision Engine integration (v0.9.0)

- **`decision_engine/signals.py`** grows to **22 signal extractors**
  (20 pre-existing + 2 new L4 signals):
  - `CrossFlow` — sign of trend×volume × structure×momentum
    interaction agreement. Reads from
    `cross_module_interactions.*`.
  - `MetaConfidence` — direction-neutral confidence driven by
    `meta_features.regime.l3_family_agreement_score`.
- **`decision_engine/voter.py`** — `SIGNAL_WEIGHTS` re-balanced for
  22 signals. Budget of 0.05 drawn from Trend / Momentum / Regime /
  Structure / Volume (−0.01 each) and split evenly between the two
  new L4 signals. Sum invariant preserved at **1.00**.
- **Embeddings do NOT get a DE signal.** They are the L4 → future
  Learning System handshake, exposed as Registry features consumable
  via `/api/features/values` and reserved for the analogue z-space
  bump.

### Added — Validation Framework (v0.9.0)

- **New property gate: `orthogonality`** — for embedding PCs,
  certifies that pairwise correlation of the top-k components is
  close to zero across the framework's canonical fixtures. Declared
  on `embeddings.geometry.pc1`. Gate lives in
  `atlas_core/validation/gates/properties.py`.
- **`declarations_v090.py`** — new declarations file with L4
  identities including the orthogonality claim on `pc1`.
- **`FeatureValidation(bridge="l4", ...)`** — the `bridge` field is
  now live at L4. Framework runner is layer-agnostic; no code change
  needed to route L4 declarations.
- **Registry-wide gates** — after 72 new L4 features,
  `unique_formula_hash`, `three_scale_rule`, and `context_isolation`
  remain **pass**. `no_duplicate_values` continues to fail on the
  ~20 legacy L1 duplicates already documented at v0.7.4 (targeted
  cleanup still pending, unchanged debt).

### Added — Tests

- `TestLayer4Representation` (10 tests): registration counts (72 /
  L4 = 4), per-module split (19 / 15 / 14 / 14 / 10), end-to-end
  compute on 400-bar synthetic OHLCV (≥ 67/72 features finite;
  every `embeddings.pc*` ≥ 30 % finite past the 250-bar PCA
  warm-up), L4-bridge isolation (DEC-016 analogue of DEC-011),
  DE-signal count 20 → 22 with `CrossFlow` and `MetaConfidence`
  present, voter weight-sum invariant, no-direct-OHLCV enforcement,
  orthogonality gate passes on `embeddings.geometry.pc1`,
  `L4_EMBEDDING_IDS` stability, rolling-PCA determinism, and
  registry-wide gates still green after L4.

### Documentation

- `docs/L4_REPRESENTATION.md` — single overarching L4 spec (same
  pattern as `L3_MARKET_UNDERSTANDING.md`). Records the boundary
  arguments (L4 is deterministic mathematics, not supervised
  learning), the access contract, the kernel primitives, the
  module hierarchy, the DE integration budget, and what is
  deliberately **not** in scope for v0.9.0 (feature-selection
  module, analogue z-space schema bump, regime-conditional voter
  weighting, target-encoded / label-based encodings, autoencoders /
  t-SNE / UMAP).
- `docs/DECISIONS.md` — **DEC-016** added: Layer-4 access contract
  via layer-owned `_layer_bridge`.
- `docs/PROJECT_CONTEXT.md`, `docs/HANDOVER.md`, `docs/CHANGELOG.md`
  synced. Per Session-8 owner directive, other markdown files
  (ARCHITECTURE, README, ROADMAP, KNOWN_LIMITATIONS, GOVERNANCE,
  BOOK1_DIGEST, ENGINES, PERSPECTIVES) are **not re-synced this
  milestone** — the codebase is the primary documentation for
  anything a fresh session cannot infer from the three synced docs
  above.

### Numbers

- **Registered features: 827** (L1 = 519, L2 = 146, L3 = 90, **L4 = 72**).
- **Decision Engine signals: 22** (was 20).
- **Voter weight sum: 1.00** (invariant preserved).
- **Backend pytests: 63/63 pass serial** in ~68 s (was 52). Adds the
  10-test `TestLayer4Representation` class + one implicit v0.9.0
  registration-count refresh.
- **Validation report** covers all 827 features; `n_features = 827`;
  registry-wide gates: 3 pass / 1 fail (legacy `no_duplicate_values`
  debt, unchanged).

### Not shipped (deliberate)

- Feature-selection module (deferred to v0.9.1+; the deterministic
  variant is thin; the label-based variant would be L5).
- Analogue z-space schema bump from 19-dim L1-heavy to
  embedding-based — separate milestone (versioned).
- Regime-conditional voter weighting driven by `RegimeState` ×
  embeddings — L5 milestone.
- LLM narrative explainer — deferred (requires Emergent LLM key).
- Frontend component split + L4 UI — deferred.
- Registry duplicate cleanup + reproducibility harness — deferred.

---

## v0.8.0 — Session 8 Milestone · Layer 3 Market Understanding (July 2025)

**Theme:** Ships Layer 3 (**Market Understanding**) end-to-end as a
single milestone: the L3 access contract, the state-authoring kernel,
five state modules, the L3 decision-engine integration, a new
validation-framework gate, and full test coverage — all in one
session. Book 1 Ch. 5 exemplars (accumulation, distribution, trend
continuation, trend exhaustion, range formation, breakout environment,
mean reversion, liquidity sweeps, market regimes) are now first-class
Registry citizens.

Authorised by **DEC-014** (L3 access contract) and **DEC-015** (state
kernel primitives). Specified by `docs/L3_MARKET_UNDERSTANDING.md`.

### Added — Layer 3 subsystem

- **`atlas_core/layers/l3_market_understanding/`** — new layer:
  - `_layer_bridge.py` — DEC-014. Parallel to L2's `_l1_bridge` but
    L3-owned; exposes `l1_series(df, id)` **and** `l2_series(df, id,
    context=None)` with per-call identity-keyed caches (both flushed
    by the orchestrator, matching DEC-011). Honours
    `df.attrs["_atlas_context"]` for peer-aware L2 lookups (DEC-007).
  - `_state_kernel.py` — DEC-015. Six primitives that produce every
    L3 shape: `weighted_score`, `hysteresis_flag`, `duration`,
    `transition`, `agreement_confidence`, `winner_take_all`, plus
    helpers `zscore_clip` and `sigmoid`. Layer-local; not promoted
    to `engines/` until L4 reuse is observed.
  - `trend_state.py` (17 features) — `trend_continuation`,
    `trend_exhaustion`, `trend_reversal`.
  - `range_state.py` (17 features) — `range_formation`,
    `breakout_environment`, `range_expansion`.
  - `participation_state.py` (17 features) — `accumulation`,
    `distribution`, `mean_reversion`.
  - `liquidity_state.py` (17 features) — `sweep_up`, `sweep_down`,
    `liquidity_neutral`. Direction interpretation in DE: sweep_up ⇒
    bearish rejection, sweep_down ⇒ bullish rejection.
  - `market_regime.py` (22 features) — 4-way regime:
    `trending_quiet`, `trending_volatile`, `ranging_quiet`,
    `ranging_volatile`.

  Each module publishes 5 uniform shapes per state (`score`, `flag`,
  `duration`, `transition`, `confidence`) plus 2 module-level
  features (`active_state_code`, `active_state_confidence`). Every
  family is **winner-take-all** — at most one flag active per bar.

- **90 new registered features** across L3. Total Registry:
  **755 features** (L1: 519 · L2: 146 · L3: 90).

### Added — Decision-Engine integration (v0.8.0)

- **5 new signals** in `decision_engine/signals.py`:
  - `TrendState` — directional, polarity from L2 consensus, state
    code translated to trend continuation / exhaustion / reversal
    directional bias.
  - `RangeState` — direction-neutral.
  - `ParticipationState` — +1 accumulation / −1 distribution / 0
    mean-reversion.
  - `LiquidityState` — +1 downside-sweep (bullish rejection) /
    −1 upside-sweep (bearish rejection) / 0 neutral.
  - `RegimeState` — direction-neutral, four-way regime classifier;
    intended for regime-conditional voter weighting in v0.9.

- **`decision_engine/voter.py`** — `SIGNAL_WEIGHTS` re-balanced to
  include the 5 new L3 signals (0.15 total budget). Weight budget
  drawn from adjacent signals whose information L3 states partially
  subsume: Trend −0.02, Momentum −0.02, Regime −0.03,
  MarketStructure −0.03, Microstructure −0.03, Volatility −0.01,
  Entropy −0.01. Invariant preserved: weights still total 1.00.
  See `docs/L3_MARKET_UNDERSTANDING.md` §8 for the full rationale.

- **Total DE signals**: 20 (was 15).

### Added — Validation Framework extension

- **`mutual_exclusivity`** — new property gate in
  `atlas_core/validation/gates/properties.py`. Certifies that at any
  bar *t*, at most one flag in a family is active (winner-take-all
  invariant). Auto-derives the family from the feature's module when
  declared without explicit `family_flags`. Runs against every
  fixture; passes for all 5 L3 modules on canonical fixtures.
- **`atlas_core/validation/declarations_v080.py`** — attaches
  `FeatureValidation(bridge="l3", ...)` declarations to representative
  L3 features:
  - Every module's `active_state_code` receives the
    `mutual_exclusivity` gate.
  - Every sampled `score`, `flag`, `confidence` (three per module)
    receives `bounded[0, 1]`.
- Framework recognises `bridge="l3"` (already reserved at v0.7.4);
  no runner-side changes required.

### Added — Regression coverage

- **`TestLayer3States`** in `backend/tests/backend_test.py` — 10
  tests covering:
  - Per-module registration counts (17 × 4 + 22).
  - Every L3 feature has `layer == 3`.
  - End-to-end compute correctness (all 90 features finite on
    synthetic OHLCV).
  - Winner-take-all mutual exclusivity for every family.
  - `active_state_code` consistency with per-state flags (in STATES
    order per module).
  - **L3 layer-bridge isolation** — two different DataFrames must
    produce different L3 output (guards against the L3 analogue of
    DEC-011).
  - Decision Engine now surfaces exactly 20 signals including the 5
    L3 state signals.
  - **No direct OHLCV access in L3 modules** — enforced by grep of
    module sources (Book 1 Invariant 6.4).
  - Framework's `mutual_exclusivity` gate passes for all 5 L3
    modules.
  - Registry-wide gates (`unique_formula_hash`, `three_scale_rule`,
    `context_isolation`) still pass after the L3 additions.

### Changed

- `atlas_core/compute/_orchestrator.py` — imports L3 modules for
  side-effect registration; flushes the L3 `_layer_bridge` cache on
  entry and exit of every `compute_features` call, parallel to L2's
  `_l1_bridge` (DEC-011 / DEC-014).
- `atlas_core/layers/__init__.py` — L3 added to the layer load order
  (L1 → L2 → L3).
- `atlas_core/__init__.py` — `__version__ = "0.8.0"`; also invokes
  `declarations_v080.attach_all(registry)` in the same best-effort
  block as v0.7.4 declarations.
- `backend/server.py` — root endpoint reports version `"0.8.0"`;
  FastAPI `title` / `version` bumped.
- `atlas_core/validation/runner.py` — `_CACHE` TTL bumped from 60 s
  to 600 s. Motivated by the report cold-build time growing to ~47 s
  as L3 features registered; 60 s TTL left almost no headroom for a
  serial test run to finish before the next cache miss. **Not** the
  end-to-end caching redesign scheduled for a later session — just a
  one-line config tweak to keep tests reliable.

### Regression coverage (v0.8.0)

- **52/52 backend pytests pass (serial, `-n 0`)** in ~25 s. Up from
  42 at v0.7.4. Adds `TestLayer3States` (10 tests) and updates a
  handful of pre-existing expectations (feature count 665 → 755;
  signal count 15 → 20; signal-names set gains 5 L3 entries;
  `SIGNAL_WEIGHTS` sum invariant unchanged at 1.00).
- **All framework gates** — universal, property, registry-wide —
  cover L3 features by construction. `context_isolation` still
  passes. `no_duplicate_values` still fails intentionally (surfacing
  the ~20 legacy Registry duplicates carried over from v0.7.4; L3
  did not introduce new duplicates by construction — every L3
  feature has a distinct formula).

### Book 1 compliance (verified)

- **Layer 3 answers *"What market environment currently exists?"*** —
  every L3 feature is a state, score, flag, duration, transition,
  or active-code; nothing is a raw measurement or relationship.
- **Info flows upward** (Inv-6.4) — L3 modules import only through
  `_layer_bridge`; enforced by a registered pytest.
- **No ML in atlas_core** (Inv-5.6) — L3 uses threshold-based
  classification with hand-authored weights; no learning.
- **Rule-1 uniqueness** — every L3 feature has a distinct formula;
  the SHA-1 guardrail catches accidents.
- **Interpretive vocabulary** (`accumulation`, `distribution`,
  `sweep`, `regime`) is Book-1-approved at L3 (Ch. 5).

### Migration notes (forward-looking)

- L4 (`Representation`) will reuse the state-kernel primitives if
  it produces meta-features from L3 states. When it does, primitives
  graduate from `_state_kernel.py` to `engines/state.py` per DEC-015
  and Book 1 Ch. 10 discovery discipline.
- L3 modules illustrate the **"discovery over pre-abstraction"**
  principle: the state-kernel primitives were extracted only after
  the shape of all five modules was concrete. No premature engines.

---

## v0.7.4 — Session 7 Priority 5 · Validation Framework (July 2025)

**Theme:** Fifth and final ship of Session 7. Turns Book 1 Ch. 9
validation from a hand-authored pytest collection into a permanent
**architectural subsystem**: every feature carries a first-class
`FeatureValidation` declaration; a `ValidationRunner` proves each
declared claim on canonical fixtures; a `ValidationProfile` becomes
persistent metadata attached to the feature (alongside `formula`,
`params`, `perspective`). Golden tests are unified with declared
identities — one mechanism, one runner, one report. Coverage now grows
by declaration, not by hand-writing tests.

Authorised by **DEC-013** (Validation Framework as permanent architectural
subsystem). Specified by `docs/VALIDATION_FRAMEWORK.md`.

The framework's **first live run surfaced a real bug** — a DEC-007
context leak inside `compute_features` where `df.attrs["_atlas_context"]`
persisted across successive compute calls, so a `context=None` call
still saw the previous peer. Root-caused, patched at
`atlas_core/compute/_orchestrator.py`, and locked in by a dedicated
in-process regression test class. Exactly the kind of failure a
mathematical-certification subsystem is supposed to surface.

### Added

- **`atlas_core/validation/`** — proper package (was a single-file
  golden runner):
  - `declaration.py` — `FeatureValidation`, `Identity`, `Invariant`
    dataclasses. What a feature **claims** to satisfy.
  - `profile.py` — `ValidationProfile` metadata. What has been
    **proven** for the feature.
  - `fixtures.py` + `fixture_matrices.py` — canonical inputs
    (trending, mean-reverting, degenerate-constant, all-zeros,
    NaN-infested, future-spike, small-N) that every applicable gate
    runs against.
  - `gates/universal.py` — 5 universal gates that run on every
    feature: `determinism`, `length_invariance`, `no_future_leakage`,
    `nan_input_behavior`, `degenerate_constant`.
  - `gates/properties.py` — property gates run when a feature
    declares them (e.g. `bounded[0,1]`, `symmetry`, `sign_invariance`).
  - `gates/registry_wide.py` — Registry-wide gates:
    `unique_formula_hash`, `no_duplicate_values`, `three_scale_rule`,
    **`context_isolation`** (DEC-007 side-channel guardrail).
  - `runner.py` — `ValidationRunner` — executes declarations against
    fixtures, produces `ValidationProfile` per feature.
  - `report.py` — aggregates all profiles into a Registry-wide
    `ValidationReport` with per-layer / per-module coverage rollups.
  - `declarations_v074.py` — first ~20 representative
    `FeatureValidation` declarations across L1 + L2, including the RS
    peer-context identities.
- **`FeatureDefinition.validation`** — optional first-class field on
  every feature. Backwards-compatible: features that carry
  `validation=None` are subject to universal gates only.
- **Two new API endpoints**:
  - `GET /api/validation/report` — full Registry-wide validation
    report (per-feature profile summaries, per-layer/module rollups,
    registry-wide gate results).
  - `GET /api/validation/profile/{feature_id}` — full `ValidationProfile`
    for a single feature (universal gates + declared-identity
    results + declaration metadata).
- **`GET /api/validation/golden`** — now framework-backed. Legacy
  goldens still appear as `source: "legacy"`; declared golden
  identities appear as `source: "framework+legacy"`. Total ≥ 36,
  passed == total.
- **`docs/VALIDATION_FRAMEWORK.md`** — the framework's specification
  (~465 lines). Placement principle ("validation is infrastructure,
  not a Layer"), the three-concept model, gate catalogue, declaration
  grammar, extension protocol.
- **`docs/DECISIONS.md` DEC-013** — codifies the framework as a
  permanent architectural subsystem alongside the Registry.
- **`backend/tests/backend_test.py::TestValidationFrameworkV074`** —
  8 tests certifying: endpoint shapes, universal-gate coverage of
  every feature, declared-identity execution, registry-wide gates
  (three-scale-rule + within-module unique-formula-hash +
  context-isolation), legacy-golden backwards compatibility,
  `FeatureDefinition.validation` field exposure, and the
  `context_isolation` gate specifically certifying the DEC-007 fix.
- **`backend/tests/backend_test.py::TestDEC007OrchestratorContextIsolation`**
  — dedicated in-process regression class (3 tests, bypasses HTTP)
  proving the DEC-007 orchestrator leak fix at the source:
  1. `df.attrs["_atlas_context"]` is cleared after any
     `compute_features(..., context={...})` call.
  2. A subsequent `compute_features(..., context=None)` on the same
     df returns all-NaN for RS features (would return finite values
     if the peer had leaked through `df.attrs`).
  3. Two calls with **different** peers on the same df return
     **different** RS series (would be identical if peer A leaked
     into the peer-B call).

### Fixed — DEC-007 orchestrator context leak (surfaced by the framework)

- **Symptom**: The framework's `context_isolation` registry-wide gate
  reported offenders on its first live run. A sequence of
  `compute_features(df, ids, context={"peer": P})` followed by
  `compute_features(df, ids, context=None)` — on the **same** df
  object — returned finite RS values in the second call. The peer
  was gone from the second call's arguments, but the second call
  still "saw" it via `df.attrs`.
- **Root cause**: `_orchestrator.compute_features` attached
  `df.attrs["_atlas_context"] = context` on entry when `context is
  not None` **but never popped the attribute afterward**. Any later
  call on the same df object with `context=None` inherited the stale
  peer through `df.attrs`. Violates DEC-007's contract that context
  is a per-call argument, not process state.
- **Fix** (`atlas_core/compute/_orchestrator.py`):
  1. On entry: unconditionally overwrite `df.attrs["_atlas_context"]`
     — populate when `context is not None`, else `pop` (never leave a
     stale value).
  2. In `finally`: unconditionally `pop("_atlas_context", None)` so
     the attribute cannot persist past the compute call under any
     control-flow path.
  3. Defensive copy of `df.attrs` on entry to guard against any
     shared-mapping aliasing between DataFrame objects.
- **Regression coverage**: certified by both the framework's
  registry-wide `context_isolation` gate (declarative) and by
  `TestDEC007OrchestratorContextIsolation` (imperative, in-process).

### Book 1 Ch. 9 debt — status

- **Duplicate-value detection** — ✅ shipped as registry-wide gate
  `no_duplicate_values`. Intentionally reports the ~20 genuine
  Registry duplicates that predate the framework as evidence for a
  targeted v0.8 cleanup pass. **Reporting these is expected behaviour**;
  the gate is doing its job. The Registry itself remains
  Rule-1-compliant (SHA-1 within-module uniqueness) — the duplicates
  the gate finds are cross-module numerical clones with distinct
  formulas, which the Rule-1 guardrail is not designed to catch.
- **Future-leakage detection** — ✅ shipped as universal gate
  `no_future_leakage`. Inserts a synthetic future spike into a
  canonical fixture; a feature that changes any *past* value in
  response is flagged.
- **Numerical-stability edge tests** — ✅ shipped as universal gate
  `degenerate_constant` (all-equal input) and `nan_input_behavior`
  (NaN-infested input). All-zeros is covered inside
  `nan_input_behavior`'s fixture rotation.
- **Three-Scale Rule** — ✅ enforced as registry-wide gate
  `three_scale_rule` (checks that every `fractal_relationships`
  feature references ≥ 3 scales).
- **Reproducibility harness** — deferred to v0.8; the framework's
  deterministic-fixture + deterministic-runner design lays the
  groundwork.

### Changed

- **`registry/registry.py`** — `FeatureDefinition` gains an optional
  `validation: FeatureValidation | None = None` field. Serialisation
  is backwards-compatible; `/api/registry/features/{id}` now exposes
  a light-summary `validation` dict when a declaration exists.
- **`GET /api/validation/golden`** — response gains a `source` field
  (`"framework+legacy"` when declared golden identities are folded in;
  `"legacy"` when only pytest-anchored goldens are counted). Total
  and passed remain backwards-compatible for the frontend.
- **`server.py`** — logs `Validation Framework cache warmed.` at
  startup once the framework has computed the initial report against
  canonical fixtures (one-shot; subsequent report requests are fast).
- **`docs/KNOWN_LIMITATIONS.md §7`** — collapsed. The old five bullets
  (duplicate-value, future-leakage, numerical-stability, reproducibility,
  golden-coverage-thinness) are re-expressed against the framework:
  four gates ship as universal / registry-wide; the ~20 duplicate
  offenders remain as v0.8 cleanup debt; goldens are now declarations,
  not orphan pytest tests.

### Migration notes (for future L3/L4 work)

- The framework is **layer-agnostic by construction**. No universal
  or property gate assumes L1 or L2 semantics.
- A `bridge` field on `FeatureValidation` is reserved for future
  `"l2"`, `"l3"`, `"l4"` values so L3 modules can declare their
  bridge access without framework changes.
- L3 modules plug in by importing `FeatureValidation`, declaring
  identities against `l2_series(df, ...)` inputs, and registering
  as usual.

### Regression coverage (v0.7.4)

- **42/42 backend pytests pass** (serial). Up from 31 at v0.7.3. Adds
  8 framework tests + 3 dedicated DEC-007 orchestrator tests.
- **36/36 legacy goldens** still pass. **39/39** in the unified view
  (`framework+legacy`, 3 declared-identity goldens folded in).
- All registry-wide gates pass (`unique_formula_hash`,
  `three_scale_rule`, `context_isolation`; `no_duplicate_values`
  intentionally reports the ~20 legacy Registry duplicates as
  expected evidence for v0.8 cleanup).

### Test infrastructure note

The default `pytest.ini` runs `-n 2 --dist loadscope`. Under this
configuration the ~24 s validation-report endpoint occasionally
starves concurrently issued lightweight endpoints via ingress
502-gateway timeouts. **Serial verification (`-n 0`) is the
authoritative signal (42/42 pass in ~20 s).** A follow-up to cache
the report response is scheduled for v0.7–v0.8 infrastructure work.

---

## v0.7.3 — Session 7 Priority 4 · Relative Strength frontend integration (July 2025)

**Theme:** Fourth of Session 7. Makes the previously-shipped L2
`relative_strength` module visible end-to-end: peer-symbol picker on
the Decision tab, a new **direction-neutral** `RelativeStrength`
Decision-Engine signal, `relative_strength.*` evidence in every
recommendation with a peer, an RS-vs-Peer mini-chart, and — crucially —
a **DEC-012 retrofit** so the module now meets the same
specification-first standard the three Session-7 L2 modules already
carry.

The `relative_strength` L2 module itself was shipped at v0.6 with 12
features; **no math changed** at v0.7.3. This is a Layer-5 + Layer-4
(server API + frontend) integration release plus documentation.

### Architectural review of the peer abstraction (owner-requested)

Before implementation, we reviewed whether `context={"peer": DataFrame}`
is the right single-benchmark abstraction or whether it should be
generalised (index / sector / basket / market). Verdict recorded in
`RELATIVE_STRENGTH.md §3 & §9`:

- **The abstraction is already correct at L2 today AND naturally
  extensible for L4 tomorrow.** Cases 1–4 (one peer / index / sector
  ETF / market proxy) are mathematically the *same* operation — a
  target and one reference — and the current interface supports all
  four with zero code change. Case 5 (basket / peer-set aggregation) is
  L4 per Book 1 Ch. 5 and DEC-005, and belongs to a new future module,
  not to `relative_strength`.
- **Vocabulary lock-in**: today `"peer"` is legal; `"basket"`,
  `"universe"`, `"index_set"`, `"sector_set"` are reserved for future
  L4 modules. Documented in the spec so future sessions do not
  accidentally overload `"peer"`.
- **Adopted rule**: no dataclass wrapper, no generic `BenchmarkContext`
  protocol, no speculative abstraction. Book 1 Principle VI + DEC-008
  respected.

### Added

- **`docs/L2_SPECS/RELATIVE_STRENGTH.md`** — **DEC-012 retrofit**
  specification (12 sections). Documents the module's math against the
  DEC-012 template, freezes the "one peer" abstraction, and reserves
  future context-key vocabulary at the docs level.
- **`docs/L2_SPECS/RELATIVE_STRENGTH_DE_REVIEW.md`** — Point-10 review
  across all 8 DE inputs. Explicit deferrals for Analogues, Sizing,
  Risk with owner-directive rationale; explicit integrations for
  Signals, Weight Learning, Confidence, Explanations, Recommendation
  Quality.
- **Decision Engine: new signal `RelativeStrength`** — **direction-
  neutral** (owner directive, Session 7 P4). 15 signals total (was 14).
  Reads exclusively `relative_strength.*` (5 features):
  `magnitude.rs_20`, `magnitude.rs_50`, `statistics.corr_50`,
  `expansion.relvol_50`, `entropy.cointegration_resid_std_100`.
  Direction always 0; strength = mean of `|rs_w − 1|` across available
  windows (symmetric divergence from equilibrium); confidence = base
  `0.30 + 0.60 × |corr_50|` plus a `+0.10` tight-cointegration bonus.
  Graceful degradation: without a peer, strength = 0 and evidence is
  empty.
- **Backend peer plumbing (DEC-007 pathway)**:
  - `RecommendRequest` and `WeightRequest` (Pydantic) gain optional
    `peer_provider` / `peer_symbol` fields.
  - `_fetch_peer_context()` helper in `server.py` fetches peer OHLCV
    with the target's interval/period, aligns to `df.index` via
    `reindex + ffill`, and returns `{"peer": aligned_df}` or None.
  - `decision_engine.recommender.recommend`,
    `decision_engine.signals.compute_all_signals`, and
    `decision_engine.weight_learner.learn_weights` all take an optional
    `context` argument, forwarded to `compute_features`.
  - `/api/features/values` gains optional `peer_provider` /
    `peer_symbol` query params so the RS mini-chart can render.
- **Frontend Decision tab**:
  - **Peer `<select>`** next to Symbol (default `— none —`); options
    are provider-scoped, target excluded. Peer resets when provider or
    symbol changes (prevents cross-provider mismatches).
  - **`RSMiniChart`** — a 160-px `lightweight-charts` line series of
    `relative_strength.magnitude.rs_20` with a dashed reference line at
    `y = 1.0` (equilibrium). Renders only when a peer is chosen.
  - Signal-Breakdown grid `grid-cols-7 → grid-cols-5` (three rows of
    five accommodates 15 signals cleanly).
  - About-tab copy: 14 → 15 signals, `RelativeStrength` marked as new,
    `NEW v0.7.2` badge cleaned off the L2 module list.
  - Header now reads `v0.7.3 · L1+L2 · 665 FEATURES`.
- **6 new backend regression tests** (class `TestRelativeStrengthV073`):
  1. `test_recommend_with_peer_populates_relative_strength` —
     end-to-end peer plumbing; asserts `peer_context` echoed, signal
     lane purity (every evidence row starts with
     `relative_strength.`), direction=0, strength/confidence bounds.
  2. `test_recommend_without_peer_graceful_degradation` — no peer →
     RS returns direction=0, strength=0, evidence=[].
  3. `test_features_values_accepts_peer_args` — `/api/features/values`
     accepts and echoes peer args; a majority of RS series points are
     finite when a peer is supplied.
  4. `test_weight_sum_invariant_v073` — `sum(SIGNAL_WEIGHTS.values())
     == 1.00` exactly; keys match the v0.7.3 canonical name set.
  5. `test_rs_identity_when_peer_equals_target_golden` — **new golden
     anchor** (goldens 36 → 37). With `peer = df.copy()`:
     `rs_20 ≡ 1.0` (atol 1e-9), `rs_50 ≡ 1.0`, `corr_50 ≥ 0.999`
     everywhere, `relvol_50 ≡ 1.0`.
  6. `test_recommend_learned_weights_with_peer` — weight learner
     accepts a peer, returns 15 signals summing to 1.0 within
     tolerance.

### Changed

- **Voter weights** — 0.03 redistributed from directional signals
  `Trend 0.14 → 0.12` (−0.02) and `Momentum 0.11 → 0.10` (−0.01). New
  `RelativeStrength = 0.03`. **Weight-sum verified exactly 1.00** by
  pytest. Rationale: RS is a comparative-strength quantity that
  partially overlaps with what `Trend` and `Momentum` measure in
  absolute terms; taking a proportional slice from those two is
  mathematically defensible. Directional totals shift from 0.86 → 0.83;
  direction-neutral confidence-modulator pool grows from 0.14 → 0.17.
- **Existing `TestDecisionRecommendV06::test_recommend_manual_weights`**
  extended: asserts `RelativeStrength` is direction-neutral (dir=0),
  strength=0 without peer, evidence=[] without peer. Backwards-compatible
  extension — no test rewritten.
- `atlas_core.__version__ → "0.7.3"`; FastAPI title + `/api/` root also
  `0.7.3`. Frontend header string updated to `v0.7.3 · L1+L2 · 665
  FEATURES`. About-tab copy updated.
- Backend regression: `EXPECTED_SIGNAL_NAMES_V07` grows to 15
  (RelativeStrength). Existing per-signal purity assertions preserved.
- Signal-Breakdown grid `grid-cols-7` → `grid-cols-5` in `App.js` for
  clean 3×5 layout at 15 signals.

### Registry stats (v0.7.3)

- **Total: 665 features** (unchanged — the L2 `relative_strength`
  module already contained all 12 features at v0.6).
- **L1 = 519**, **L2 = 146**. Module counts unchanged.
- All 11 Perspectives still populated across ≥ 3 modules.

### Test surface

- **Golden tests: 36/36 pass** (baseline). A new analytical anchor for
  `relative_strength` is included as a pytest-level golden inside
  `TestRelativeStrengthV073::test_rs_identity_when_peer_equals_target_golden`.
  The `/api/validation/golden` endpoint total remains at 36 (per-module
  goldens live under `atlas_core/validation/`; the new anchor is a
  pytest regression, exactly like the existing FR three-scale rule and
  no-direct-ohlcv gates for `fractal_relationships`).
- **Backend pytests: 31/31 pass** (was 25; +6 new for
  `TestRelativeStrengthV073`).
- **Weight-sum invariant**: `sum(SIGNAL_WEIGHTS.values()) == 1.00`
  verified twice — inside the recommend test and inside the dedicated
  `test_weight_sum_invariant_v073`.

### Book 1 compliance re-verified

- `relative_strength` reads L1 exclusively via `_l1_bridge.l1_series`
  (unchanged from v0.6; the module code itself was not modified).
- New `RelativeStrength` signal reads only `relative_strength.*` —
  lane-clean by construction, enforced by regression test.
- Peer abstraction respects the L2/L4 boundary at both the code and
  vocabulary level (see architectural-review section above). Multi-peer
  aggregation is documented as **out of scope** for this module in
  `RELATIVE_STRENGTH.md §9`.
- No interpretive names in feature IDs. Signal name `RelativeStrength`
  is L5 and permitted to be interpretive.
- Direction-neutral signal — no contribution to voter's
  `directional_score`; confidence-modulator only.
- No new L1/L2 math introduced; no new engine.

### Rollback plan

1. **Signal-only** — set `RelativeStrength = 0.0` in `SIGNAL_WEIGHTS`;
   restore `Trend = 0.14`, `Momentum = 0.11`. Reversible without a code
   change.
2. **Signal-plus-plumbing** — additionally remove `RelativeStrength`
   from `SIGNAL_FUNCS`. The 5 feature reads stay in `SIGNAL_FEATURE_IDS`
   but simply aren't consumed by any signal.
3. **Frontend-only** — hide the peer picker + RS mini-chart. Backend
   remains functional for API callers.
4. **Full version rollback** — revert v0.7.3 → v0.7.2. Zero DB-schema
   changes.

---

## v0.7.2 — Session 7 Priority 3 · `fractal_relationships` L2 module (July 2025)

**Theme:** Third and final L2 module of Session 7. Completes the L2
trend-and-scale triad. Follows the spec-first workflow (DEC-012) and
introduces a permanent architectural guardrail — the **Three-Scale Rule**
— that mathematically prevents overlap between this module and its two
Session-7 siblings.

The three L2 modules are now strictly orthogonal on their governing axis:

| Module | Governing axis | Question |
|---|---|---|
| `momentum_of_trend` (v0.7.0) | Temporal derivatives | *"How does the measurement change over time?"* |
| `trend_relationships` (v0.7.1) | Cross-source / cross-scale (2 scales) | *"Do independent measurements agree right now?"* |
| **`fractal_relationships`** (v0.7.2) | Scaling law across ≥ 3 scales | *"Does the same phenomenon scale self-similarly?"* |

### Added

- **L2 · `fractal_relationships` module** (21 features, 5 Perspectives populated).
  - **Geometry (5)**: variance-scaling exponent + R² over τ∈{2..64}; range-scaling exponent + R² + |β − 0.5| over τ∈{5..80}.
  - **Statistics (5)**: generalised Hurst H(1), H(2), H(3) over τ∈{2..32}; multifractal spread H(1)−H(3); Haar wavelet-variance scaling exponent over levels 1..4.
  - **Distribution (3)**: variance-ratio envelope over τ∈{2..16} — max deviation from unity, scale-std, signed extreme.
  - **Regime (5)**: Hurst cross-window σ and range (w∈{32,64,128}); Higuchi FD cross-window σ (w∈{25,50,100}); **self_similarity_score** (geometric mean of 5 Brownian-anchored sub-scores); **self_similarity_flag** (binary, gated at score > 0.75 with all sub-scores ≥ 0.5).
  - **Position (3)**: rolling 60-bar percentile ranks of α, multifractal spread, and self-similarity score.
- **L1 additive prerequisites** (2 features): `price.geometry.hurst_32`, `price.geometry.higuchi_fd_25`. Both use existing engines; no new engine math introduced. L1 count 517 → 519.
- **`docs/L2_SPECS/FRACTAL_RELATIONSHIPS.md`** — full 14-section spec written before code, following DEC-012. Introduces the **Three-Scale Rule** (§2) as the module's defining property. Includes an explicit **canonical values table** (§5.6) mapping every scaling-law feature to its expected value for Brownian motion, persistent, and anti-persistent processes.
- **`docs/L2_SPECS/FRACTAL_RELATIONSHIPS_DE_REVIEW.md`** — Point-10 review across all 8 DE inputs; explicit deferrals for Analogues, Sizing, Risk (owner directive: observe first, integrate later).
- **Decision Engine: new signal `FractalCoherence`** — **direction-neutral** (owner directive). 14 signals total (was 13). Reads exclusively `fractal_relationships.*` (5 features): `self_similarity_score`, `self_similarity_flag`, `variance_scaling_exponent_2_64`, `multifractal_spread_h1_minus_h3_2_32`, `variance_ratio_max_deviation_from_unity_2_16`. Direction always 0; strength = score; confidence = score mapped to [0.30, 1.00] with +15% unanimity bonus.
- **6 new Golden Tests** for `fractal_relationships`, all Brownian-anchored:
  - `test_fr_variance_scaling_of_brownian_is_one` (α → 1.0, tolerance 0.35)
  - `test_fr_multifractal_spread_of_monofractal_is_near_zero` (|H(1)−H(3)| < 0.15)
  - `test_fr_variance_ratio_of_random_walk_max_deviation_is_small` (< 0.5)
  - `test_fr_hurst_cross_window_std_bounds` (∈ [0, 0.5])
  - `test_fr_self_similarity_score_bounds` (∈ [0, 1])
  - `test_fr_self_similarity_flag_is_binary` (∈ {0, 1})
- **2 new backend regression assertions**:
  - `test_fractal_relationships_three_scale_rule` — every registered feature carries `params["scales"]` with `len(scales) ≥ 3`. Enforces the Three-Scale Rule at Registry level.
  - `test_fractal_relationships_no_direct_ohlcv` — grep-audit of the module source: zero `df["…"]` OHLCV reads (Invariant 6.4).

### Changed

- **Voter weights** — 0.03 redistributed **exclusively from direction-neutral confidence-modulators**: `Structure 0.05 → 0.03` (−0.02) and `Entropy 0.03 → 0.02` (−0.01). **Directional weights untouched.** New `FractalCoherence = 0.03`. **Weight-sum verified exactly 1.00** by pytest.
- **Feature-name discipline** — `fractal_coherence_score/flag` (draft) renamed to `self_similarity_score/flag` per owner review: "coherence" leans toward interpretation; the new names describe exactly the mathematical property. L5 signal name `FractalCoherence` retained (signal names may be interpretive per DEC-009).
- `atlas_core.__version__ → "0.7.2"`; FastAPI title + `/api/` root also `0.7.2`.
- Frontend header now reads `v0.7.2 · L1+L2 · 665 FEATURES`. About-tab copy: 14 signals, L2 modules list adds Fractal Relationships, Golden Tests 30 → 36. Signal-Breakdown grid `grid-cols-12 → grid-cols-7` (two rows of 7 accommodates 14 signals cleanly).
- Backend regression: `EXPECTED_TOTAL 642 → 665`, `EXPECTED_LAYERS.1 517 → 519`, `EXPECTED_LAYERS.2 125 → 146`, `EXPECTED_BY_MODULE` gains `price: 285→287` and `fractal_relationships: 21`, `EXPECTED_SIGNAL_NAMES_V07` grows to 14 (includes `FractalCoherence`). New per-signal purity assertion for FractalCoherence evidence + explicit `direction == 0` assertion. New voter weight-sum assertion inside the recommend test.

### Registry stats (v0.7.2)

- **Total: 665 features** (up from 642 at v0.7.1).
- **L1 = 519** (was 517; +2 for hurst_32, higuchi_fd_25), **L2 = 146** (was 125; +21 from `fractal_relationships`).
- Modules (13): price 287 · volatility 79 · volume 46 · liquidity 40 · microstructure 40 · time 27 · market_structure 44 · swing_dynamics 10 · compression_expansion 7 · relative_strength 12 · momentum_of_trend 32 · trend_relationships 20 · **fractal_relationships 21** *(NEW)*.
- All 11 Perspectives still populated across ≥ 3 modules.

### Test surface

- **Golden tests: 36/36 pass** (was 30).
- **Backend pytests: 25/25 pass** (was 23; +2 new: three-scale-rule and no-direct-ohlcv).
- **Weight-sum invariant**: `sum(SIGNAL_WEIGHTS.values()) == 1.00` verified inside the recommend regression test.

### Book 1 compliance re-verified

- `fractal_relationships` consumes L1 exclusively via `_l1_bridge.l1_series` — verified by a grep-audit regression test.
- The **Three-Scale Rule** (spec §2) enforced at Registry level: every registered feature carries an explicit `params["scales"]` list of length ≥ 3.
- Explicit orthogonality with `momentum_of_trend` (temporal axis) and `trend_relationships` (2-scale ratios) documented and enforced.
- No interpretive names in feature IDs. Signal name `FractalCoherence` is L5 and permitted to be interpretive.
- Direction-neutral signal — no contribution to voter's `directional_score`; confidence-modulator only. Matches Book 1 principle that Layer-5 constructs should be as targeted as their inputs justify.

### Rollback plan

1. **Signal-only** — set `FractalCoherence = 0.0` in `SIGNAL_WEIGHTS`; restore `Structure = 0.05`, `Entropy = 0.03`. Reversible without a code change.
2. **Feature-level** — remove `from ... import fractal_relationships` in `atlas_core/layers/l2_relationships/__init__.py`. The 21 features vanish from the Registry; the two L1 additions remain harmless.
3. **Full version rollback** — revert v0.7.2 → v0.7.1. Zero DB-schema changes.

---

## v0.7.1 — Session 7 Priority 2 · `trend_relationships` L2 module (July 2025)

**Theme:** Second L2 module of Session 7. Follows the spec-first workflow
codified in DEC-012. Complements `momentum_of_trend`: this module
measures cross-source and cross-scale agreement between independent trend
measurements (LR-slope, EMA-slope, ADX, Aroon, LR-R²), while
`momentum_of_trend` measures the temporal evolution of the same
measurements. The two axes are orthogonal by design.

### Added
- **L2 · `trend_relationships` module** (20 features, 5 Perspectives populated).
  - **Relative (7)**: cross-scale sign products; cross-methodology sign products; slope ratio 20/50 (safe-clipped ±10); slope divergence 20/50; short/long sign diff; methodology sign span.
  - **Geometry (4)**: EMA-cascade score (10→20→50→100 and 10→20→50), EMA-cascade signed, EMA span normalised (10 vs 100).
  - **Regime (3)**: directional consensus score in `[1/3, 1]`, consensus sign in `{-1, 0, +1}`, all-sources-agree flag.
  - **Statistics (3)**: ADX↔R² 60-bar rolling correlation, consensus-score rolling mean and std.
  - **Position (3)**: rolling percentile ranks of consensus_score, cascade_score, and |slope_ratio|.
- **`docs/L2_SPECS/TREND_RELATIONSHIPS.md`** — full mathematical specification with the pushback section and non-goals block, written before code.
- **`docs/L2_SPECS/TREND_RELATIONSHIPS_DE_REVIEW.md`** — Point-10 review across all 8 DE inputs; explicit deferrals for Analogues, Sizing, Risk with future-work notes for v0.8.
- **Decision Engine: new signal `TrendAlignment`** — 13 signals total (was 12). Reads exclusively `trend_relationships.*` (5 features). Direction from consensus sign (with cascade fallback when consensus is zero and cascade is unambiguous); strength from cascade cleanliness × cross-sign consistency; confidence anchored on consensus score with +20% unanimity bonus.
- **5 new Golden Tests** for `trend_relationships`:
  - `test_tr_slope_agreement_on_pure_trend` (all 3 methodologies agree → score = 1)
  - `test_tr_ema_cascade_score_bounds_and_full_up` (bounded [0, 1]; +1 on pure up-trend)
  - `test_tr_cross_scale_agreement_on_v_shape` (V-shaped close → agreement contains −1)
  - `test_tr_methodology_sign_span_bounds` (∈ {0, 1, 2}, integer-valued)
  - `test_tr_consensus_score_range` (∈ [1/3, 1])

### Changed
- **Voter weights** — 0.05 redistributed to `TrendAlignment(0.05)`: Trend `0.16 → 0.14`, Momentum `0.12 → 0.11`, TrendMomentum `0.05 → 0.03`. **Weight-sum verified exactly 1.00.** TrendMomentum drops 0.02 because both new L2 trend signals are first-ship and we hold total L2-trend weight budget constant.
- `atlas_core.__version__ → "0.7.1"`; FastAPI title + `/api/` root also `0.7.1`.
- Frontend header now reads `v0.7.1 · L1+L2 · 642 FEATURES`. About-tab copy: 13 signals, L2 modules list adds Trend Relationships, Golden Tests 25 → 30.
- Backend test regression: `EXPECTED_TOTAL 622 → 642`, `EXPECTED_LAYERS.2 105 → 125`, `EXPECTED_BY_MODULE` gains `trend_relationships: 20`, `EXPECTED_SIGNAL_NAMES_V07` grows to 13. New per-signal module-purity assertion for TrendAlignment evidence.

### Registry stats (v0.7.1)
- **Total: 642 features** (up from 622 at v0.7).
- **L1 = 517** (unchanged), **L2 = 125** (was 105; +20 from `trend_relationships`).
- Modules (12): price 285 · volatility 79 · volume 46 · liquidity 40 · microstructure 40 · time 27 · market_structure 44 · swing_dynamics 10 · compression_expansion 7 · relative_strength 12 · momentum_of_trend 32 · **trend_relationships 20** *(NEW)*.
- All 11 Perspectives still populated across ≥3 modules.

### Test surface
- **Golden tests: 30/30 pass** (was 25).
- **Backend pytests: 23/23 pass** (same count, purity assertion extended for TrendAlignment).

### Book 1 compliance re-verified
- `trend_relationships` consumes L1 exclusively through `_l1_bridge.l1_series`.
- Explicit orthogonality with `momentum_of_trend`: temporal axis is out of scope here (§9 of the spec).
- No interpretive names — `all_sources_agree_flag_20` (previously drafted as `trend_coherence_flag`) was renamed during spec review precisely to keep the name formula-descriptive.

---

## v0.7.0 — Session 7 Priority 1 · `momentum_of_trend` L2 module (July 2025)

**Theme:** First L2 module of Session 7. Following the user's Session 7
philosophy, every L2 feature answers a *relationship-based* mathematical
question — measuring how existing L1 trend measurements evolve over time —
that L1 alone cannot answer.

### Added
- **L2 · `momentum_of_trend` module** (32 features, 5 Perspectives populated).
  - Sources (consumed via `_l1_bridge.l1_series`): `price.motion.lr_slope_20`, `price.regime.adx_14`, `price.regime.aroon_osc_14`.
  - Derivatives at windows `w ∈ {10, 20}`: velocity, acceleration, velocity-stability (rolling std), direction-persistence, |velocity| percentile rank.
  - Two Relative-perspective cross-source alignment features: `velocity_sign_agreement_20` and `velocity_agreement_slope_adx_20`.
- **`docs/L2_SPECS/MOMENTUM_OF_TREND.md`** — mathematical specification: purpose, mathematical question, inputs, outputs, why L1 cannot answer, why L2. Written before implementation per Session 7 philosophy.
- **`docs/L2_SPECS/MOMENTUM_OF_TREND_DE_REVIEW.md`** — Point-10 Decision-Engine review across all 8 DE inputs; explicit justifications for each integrate/defer decision.
- **Decision Engine: new signal `TrendMomentum` (L2)** — 12 signals total (was 11). Consumes 4 `momentum_of_trend.*` features exclusively. Direction from LR-slope velocity; strength boosted by direction-persistence; confidence anchored on cross-source agreement.
- **4 new Golden Tests** for `momentum_of_trend`:
  - `test_mot_velocity_of_constant_slope_is_zero` (linear close → velocity ≈ 0)
  - `test_mot_velocity_sign_flips_on_v_shape` (V-shaped close → velocity spans both signs)
  - `test_mot_direction_persistence_bounds` (output ∈ `[0, w]` and integer-valued)
  - `test_mot_velocity_sign_agreement_in_unit_interval` (output ∈ `[0, 1]`)

### Changed
- **Voter weights** — 0.05 budget redistributed to make room for `TrendMomentum(0.05)`:
  Trend `0.18 → 0.16`, Momentum `0.14 → 0.12`, Structure `0.06 → 0.05`. Weight-sum ≈ 1.00 preserved.
- **`atlas_core.__version__ → "0.7.0"`**; FastAPI title + `/api/` root also `0.7.0`.
- Frontend header now reads `v0.7.0 · L1+L2 · 622 FEATURES`. Signal-Breakdown grid `grid-cols-11 → grid-cols-12`. About-tab copy updated (12 signals, L2 modules list adds Momentum of Trend, Golden Tests 21 → 25).
- Backend test regression: `EXPECTED_TOTAL 590 → 622`, `EXPECTED_LAYERS.2 73 → 105`, `EXPECTED_BY_MODULE` gains `momentum_of_trend: 32`, `EXPECTED_SIGNAL_NAMES` grows to 12 (includes `TrendMomentum`). New per-signal module-purity assertion for TrendMomentum evidence.

### Registry stats (v0.7.0)
- **Total: 622 features** (up from 590 at v0.6).
- **L1 = 517** (unchanged), **L2 = 105** (was 73; +32 from `momentum_of_trend`).
- Modules (11): price 285 · volatility 79 · volume 46 · liquidity 40 · microstructure 40 · time 27 · market_structure 44 · swing_dynamics 10 · compression_expansion 7 · relative_strength 12 · **momentum_of_trend 32** *(NEW)*.
- All 11 Perspectives still populated across ≥3 modules.

### Test surface
- **Golden tests: 25/25 pass** (was 21).
- **Backend pytests: 23/23 pass** in ~10s.
- Live-preview Playwright validation: to be run at end of ship.

### Book 1 compliance re-verified
- `momentum_of_trend` consumes L1 exclusively through `_l1_bridge.l1_series` (Invariant 6.4).
- No L1 math re-implemented; every source is a Registry lookup.
- No interpretive names (velocity/acceleration/persistence are formula-descriptive; no "exhaustion", "breakout", etc.).
- `TrendMomentum` lives in `decision_engine/` (L5 stays out of Atlas Core).

---

## v0.6.3 — Preview-broken hotfix: REACT_APP_BACKEND_URL undefined at build time (July 2025)

### Fixed
- **Frontend preview served /undefined/api/… → 404 storm.** Every axios call from the running bundle targeted the literal path `/undefined/api/…` and returned HTTP 404, producing an "Uncaught runtime errors" React banner in place of the UI.
- **Root cause**: Create React App inlines `process.env.REACT_APP_*` at **build time**, not runtime. When the frontend service booted, `/app/frontend/.env` did not yet exist, so webpack compiled `${process.env.REACT_APP_BACKEND_URL}/api` as `"undefined/api"`. This class of failure is silent — no compiler error, no lint warning, no test failed — because none of the previous test suite exercised the built bundle.
- **Fix**:
  1. Ensured `/app/frontend/.env` and `/app/backend/.env` are present and correct (`REACT_APP_BACKEND_URL`, `MONGO_URL`, `DB_NAME`).
  2. Restarted the frontend service so CRA re-inlined the env var.
  3. Added a **build-time guard** in `frontend/src/App.js`: if `_BACKEND` resolves to falsy / literal `"undefined"` / `"null"`, throw an explicit error with remediation instructions instead of silently emitting `/undefined/api/…` URLs.

### Added
- **`TestFrontendEndpointContract`** in `backend/tests/backend_test.py`:
  - `test_env_var_present_in_frontend_env_file` — asserts `/app/frontend/.env` exists and defines a valid http(s) `REACT_APP_BACKEND_URL`.
  - `test_every_frontend_endpoint_is_registered` — statically scans `App.js` for every `${API}/…` invocation and probes each against the live backend, failing on any 404. Guarantees frontend/backend endpoint contract stays in sync.
- Header version label now reads `v0.6.3 · L1+L2 · {N} FEATURES`.

### Changed
- `atlas_core.__version__ → "0.6.3"`, FastAPI title + `/api/` root also `0.6.3`.
- Backend pytest count: 21 → 23 (two new endpoint-contract tests).

### Verified (Playwright)
- Fresh preview load emits only `200 OK` responses on `/api/*`.
- All 6 tabs (Decision, Terminal, Features, Correlation, Prediction, About) load without the runtime-error banner.
- 21/21 golden tests pass. 23/23 backend pytests pass.

### Why previous testing missed it
The v0.6 pytest suite exercised the backend over HTTP but never loaded the compiled frontend bundle. A missing `.env` therefore produced a broken UI while every backend test still passed. The new `TestFrontendEndpointContract` closes this gap by (a) validating the env file itself and (b) enumerating and probing every route the frontend actually calls.

---

## v0.6.2 — L1 bridge cache-isolation bug fix (July 2025)

### Fixed
- **L1 bridge cache leakage across DataFrames** (Book 1 purity violation).
  `atlas_core/layers/l2_relationships/_l1_bridge.py` caches L1 series by
  `(id(df), feature_id)`. Python can recycle object ids after garbage
  collection, so a cached series computed for a previous DataFrame could
  be silently returned for a different DataFrame whose id CPython
  happened to reallocate to the same slot. This produced cross-test
  state leakage and violated Atlas Core's mathematical purity.
- **Fix** (`atlas_core/compute/_orchestrator.py`): `compute_features()`
  now calls `_l1_bridge.clear_cache()` on entry **and** on exit. The
  cache's only legitimate purpose is intra-call de-duplication of L1
  lookups by many L2 features; scoping it strictly per-call preserves
  that benefit while eliminating the id-recycling foot-gun.

### Added
- **`TestL1BridgeCacheIsolation`** in `backend/tests/backend_test.py` —
  two regression tests that (a) prime the cache with a poison entry and
  assert `compute_features()` flushes it, and (b) verify that back-to-back
  `compute_features(df1) → compute_features(df2) → compute_features(df1)`
  is deterministic and produces distinct outputs for distinct data.
- **DEC-011** — ADR documenting the per-call cache flush pattern; will
  be re-used verbatim when `_l1_bridge` is generalised for L3/L4.

### Changed
- `atlas_core.__version__ → "0.6.2"`.
- `server.py` FastAPI title & root endpoint report `0.6.2`.
- Backend pytest count: 19 → 21 (the two new isolation tests).

### Verified
- 21/21 golden tests pass.
- 21/21 backend pytests pass.
- 590 features registered — unchanged from v0.6.
- No public-API change; fully backward-compatible.

---

## v0.6.1 — Permanent documentation system (post-Session 6)

### Added
- **`docs/` folder** — permanent, self-bootstrapping documentation system:
  - `docs/README.md` — index and reading order for new AI sessions.
  - `docs/BOOK1_DIGEST.md` — structured engineering digest of Book 1 (philosophy, layers, invariants, forbidden practices, terminology, decision hierarchy).
  - `docs/PROJECT_CONTEXT.md` — current architecture, layer status, feature counts by module, engines, roadmap headline, technical-debt headline, decisions headline.
  - `docs/ARCHITECTURE.md` — complete architecture with diagrams (Atlas Core / Decision Engine / Registry / Validation / dependency rules / information flow / data flow / API flow).
  - `docs/DECISIONS.md` — ADR log (DEC-001 through DEC-010, plus REJ-001–REJ-003).
  - `docs/HANDOVER.md` — immediate priorities, boot-strap checklist, cardinal rules.
  - `docs/ROADMAP.md` — long-term plan by track (L1/L2/L3/L4, Decision Engine, Frontend, Validation, Research, Infrastructure).
  - `docs/KNOWN_LIMITATIONS.md` — technical debt, current limitations, embedded assumptions.
  - `docs/CHANGELOG.md` (this file).

### Changed
- Root `README.md` now points at `docs/`.
- `PROJECT_CONTEXT.md`, `HANDOVER.md`, `CHANGELOG.md` moved from `/app/` to `/app/docs/` (v0.6-created placeholders replaced by the permanent versions).

### Rationale
Project owner directive: Atlas has grown too large to rely on chat memory. The repository must contain everything a fresh AI session needs to continue development without prior context. See **DEC-010**.

---

## v0.6 — L1→L2 transition (Session 6, revised · July 2025)

**Theme:** Book 1 constitutional compliance. Session 6 was originally scoped as "more L1 modules" but a full read of Book 1 revealed three L1 designations that violated Invariants 6.3, 6.5, and 5.6. Project owner approved Option A: stay strictly Book-1 compliant; transition to first L2 implementation.

### Added
- **L1 · `microstructure` module** (40 features) — body/wick geometry, execution-imbalance and range-covered ratios, participation ratios, volume percentile ranks, doji/marubozu/high-participation flags, autocorrelation of body/range, Shannon entropy of wick-difference distribution. **All names formula-descriptive** (see DEC-009).
- **Layer 2 scaffolding** — `atlas_core/layers/l2_relationships/` with `_l1_bridge.py` enforcing Invariant 6.4 (upward flow via Registry only).
- **L2 · `market_structure` module** (44 features) — pivots at k=3/5/10, HH/HL/LH/LL, BOS at k=3/5, CHoCH, structure regime, break strength (ATR-normalised), structural range position, internal/external/fractal structure, persistence.
- **L2 · `swing_dynamics` module** (10), **`compression_expansion` module** (7), **`relative_strength` module** (12).
- **3 new engines**: `swings`, `flow_proxy` (interpretive names purged), `crossasset`.
- **Orchestrator**: `compute_features(df, feature_ids, context=None)` — optional multi-symbol payload, backward-compatible (see DEC-007).
- **Decision Engine** — two new signals: `Microstructure` (L1) + `MarketStructure` (L2). SIGNAL_WEIGHTS rebalanced; MarketStructure carries the largest single weight (0.15).
- **Golden tests: 10 → 21**, all passing. Every new engine + module has ≥1 analytical known-answer test.

### Moved
- **`atlas_core/ml/*` → `decision_engine/ml/*`** — closes Book 1 Invariant 5.6 violation from v0.5 (see DEC-004). Regression test `test_ml_not_in_atlas_core` enforces the boundary.

### Changed
- `atlas_core.__version__ → "0.6.0"`.
- `server.py` FastAPI title & root endpoint report `0.6.0`.
- Frontend header: `v0.6 · L1+L2 · {N} FEATURES`.
- Frontend About tab: describes L1 vs L2 split; lists all enforced Book 1 invariants.
- Signal-Breakdown grid: `grid-cols-9` → `grid-cols-11`.
- Backend tests: renamed `TestDecisionRecommendV05` → `TestDecisionRecommendV06`; added `test_ml_not_in_atlas_core`, `test_layer_split_l1_l2`, `test_microstructure_features_l1`, `test_l2_modules_present`, `test_market_structure_ids`.

### Registry stats (v0.6)
- **Total: 590 features** (up from 477 at v0.5).
- L1 = 517, L2 = 73.
- Modules (10): price 285 · volatility 79 · volume 46 · liquidity 40 · microstructure 40 · time 27 · market_structure 44 · swing_dynamics 10 · compression_expansion 7 · relative_strength 12.
- All 11 Perspectives populated across ≥3 modules.

### Test surface
- **Golden tests: 21/21 pass** (was 10/10).
- **Backend pytests: 19/19 pass** in ~30s (was 14/14).
- Decision Engine end-to-end: 11 signals fire on SYN-EQUITY, all evidence stays in-module (cross-module cleanup verified by test).

### Architectural pushback surfaced in Session 6
1. Session-6 v1 proposed Market Structure at L1 → overturned; Book 1 places it at L2. See DEC-005 / REJ-001.
2. Session-6 v1 proposed Cross-Asset at L1 → overturned; Book 1 places cross-module at L4. See DEC-005 / REJ-002.
3. Interpretive names in the initial `flow_proxy` engine violated Invariant 6.5 → renamed. See DEC-009 / REJ-003.
4. `atlas_core/ml/*` violated Invariant 5.6 → moved. See DEC-004.

---

## v0.5 — Cross-module cleanup + Liquidity + Time (Session 5)

### Added
- **L1 · Liquidity module** (40 features): Roll spread, HL spread, Amihud, Kyle-λ, turnover, effective-range ratio. All 11 Perspectives.
- **L1 · Time module** (27 features): calendar magnitudes, cyclic sin/cos encodings, session/calendar flags, position ratios, elapsed-seconds gap detector.
- **Decision Engine**: added `Volume` and `Liquidity` cross-module signals (7 → 9 signals).
- **Manual / learned weights toggle** end-to-end (`POST /api/decision/recommend` accepts `use_learned_weights`; response carries `weight_source` and `weights_used`).

### Changed
- **`Volatility` signal cleaned up** to read exclusively from `volatility.*` — no more `price.expansion.*` leakage. Book 1 architectural boundary restored end-to-end.

### Registry stats (v0.5)
- Total: 477 features (price 285 · volatility 79 · volume 46 · liquidity 40 · time 27).
- Golden tests: 10/10.
- Backend tests: 14/14.

---

## v0.4 — Balanced L1 depth (Session 4)

### Added
- **L1 · Volatility module** (79 features): 5 canonical estimators (Close-to-Close, Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang) + upside/downside semivariance. All 11 Perspectives.
- **L1 · Volume module** (46 features): base V, log V, dollar V, signed V, VWAP; OBV; PV confirmation. All 11 Perspectives.
- **Adaptive interpretable Weight Learner** (`decision_engine/weight_learner.py`): rolling logistic regression fits `direction × strength` per signal on forward-return sign. Interpretable output only.
- **Golden Test framework** (10 analytical tests, all passing).

### Registry stats (v0.4)
- Total: 410 features (price 285 · volatility 79 · volume 46).

---

## v0.3 — Decision Engine + signal-critical features (Session 3)

### Added
- **Decision Engine package** (`decision_engine/`) as a top-level Layer-5 consumer.
- **7 signals**: Trend, Momentum, Regime, Structure, MeanReversion, Volatility, Entropy.
- **Voter** with weighted aggregation, agreement-based confidence, conservative thresholds.
- **Risk engine**: ATR/std/VaR/ES/Ulcer/Hurst → qualitative levels + position sizing.
- **Historical Analogues**: K-NN=10 over 19-dim z-scored feature vector.
- **Multi-model ensemble** (`ml/ensemble.py`): 4 real models (XGBoost + RandomForest + GradientBoost + LogisticReg) vote independently.
- **~40 new signal-critical Price features**: Hilbert transform engine, L-moments engine, Aroon Up/Down/Osc, Vortex, ADX-like directional strength, DeMarker, Trend Intensity Index, linear-regression slope, R².
- **Terminal redesign**: Decision tab as default landing.

### Registry stats (v0.3)
- Total: 285 L1/Price features.

---

## v0.2 — Price depth (Session 2)

### Added
- **Price module expanded 70 → 248 features** across all 11 Perspectives.
- **Three new engines**: `fractal` (Higuchi FD, Hurst R/S, DFA, Kaufman ER), `information` (Shannon, permutation, sample, approximate, Rényi, Tsallis, LZ), `spectral` (dominant freq, centroid, entropy, flatness, rolloff), `technical` (EMA, ATR, Bollinger, Donchian, Keltner, KAMA, Chande, Ulcer, Choppiness).
- **Compute orchestrator perf-fix** (`pd.concat` instead of iterative insert).
- **Silent SHA-1 Rule-1 guardrail** operationalised (see DEC-003).

### Registry stats (v0.2)
- Total: 248 features. All 11 Perspectives populated.

---

## v0.1 — Initial vertical slice (Session 1)

### Added
- **Atlas Core skeleton**: `atlas_core/{registry, engines, layers, compute, data, analysis, ml}/`.
- **Registry as first-class subsystem**: `FeatureDefinition` dataclass with uniqueness enforcement via formula hash.
- **7 initial engines**: `rolling`, `statistics`, `motion`, `geometry`, `distribution`, `normalization`, `distance`.
- **L1 · Price module**: 70 features across all 11 Perspectives.
- **Data providers**: Synthetic (regime-switching GBM), CoinGecko, Yahoo, Binance, with `fetch_smart` graceful-fallback.
- **Market Analysis** (`atlas_core/analysis/`): `market_snapshot` + `explain_snapshot`.
- **ML pipeline** (later moved out in v0.6): XGBoost + RandomForest.
- **FastAPI server** exposing Registry, market, features, correlation, analysis, prediction endpoints.
- **Atlas Terminal frontend**: React 19 + lightweight-charts. 5 tabs (Terminal / Features / Correlation / Prediction / About).
- **Beginner/Pro mode toggle**.

### Registry stats (v0.1)
- Total: 70 features. L1/Price only. All 11 Perspectives populated.

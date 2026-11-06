# Contributing to Vorien · Atlas

Thank you for your interest in contributing to **Vorien · Atlas**!

We build institutional-grade quantitative research infrastructure. Our codebase powers high-throughput feature extraction, causal market modeling, purged machine learning, and event-driven backtesting. To preserve our mathematical integrity, performance benchmarks, and production reliability, all contributions must adhere to the engineering standards detailed below.

---

## 💬 Community, Bug Reports & Feature Requests

**We highly value your feedback, bug reports, and feature suggestions!**

- **Found a Bug?** If you spot a calculation flaw, numerical precision issue, edge-case crash, or API failure, please [open an issue on GitHub](https://github.com/zxyaditya/Vorien-Atlas/issues) with:
  1. A minimal reproducible code snippet.
  2. The input data shape, asset provider, and timeframe.
  3. The expected vs. actual numerical behavior.
  4. Your Python version and OS environment.
- **Have a Feature Request?** If there is an econometric feature, microstructure metric, volatility formulation, or data connector you would like to see, open a GitHub Issue tagged `enhancement` and describe its mathematical formulation and empirical motivation.

---

## 📖 Mandatory Prerequisite: Read the Documentation First

> [!IMPORTANT]
> **Before writing code or opening a Pull Request (PR), you MUST thoroughly read the documentation under [`docs/`](./docs/).**

To maintain institutional engineering rigor, all contributors must understand how the platform is architected before proposing modifications:

1. **[`docs/GETTING_STARTED.md`](./docs/GETTING_STARTED.md)** — The complete 5-step quant flow (Features → Labels → ML Signals → Backtest → Paper Trading).
2. **[`docs/FEATURE_HIERARCHY.md`](./docs/FEATURE_HIERARCHY.md)** — The 4-layer taxonomy (L1–L4, 925 features across 31 modules and 22 perspectives).
3. **[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)** — Layer boundaries, service topologies, and dependency rules.
4. **[`docs/VALIDATION_FRAMEWORK.md`](./docs/VALIDATION_FRAMEWORK.md)** — Mathematical certification, golden test suites, and universal validation gates.

---

## 🏛 Core Architectural Invariants

Every Pull Request must strictly respect the following non-negotiable quantitative standards:

### 1. Mathematical Purity (Atlas Core L1–L4)
- **Measurement Only**: `atlas_core/` calculates objective numerical market features. **Never** place predictive machine learning models, trading signals, position sizing, order execution, or strategy logic inside `atlas_core/`.
- **Zero Lookahead Bias**: Every feature formulation must be strictly causal (backward-looking in time: $t \le T$). Normalization, scaling, and rolling statistics must never peek into future bars.
- **Deterministic Registration**: Duplicate mathematical formulations are rejected. Every feature must be uniquely and deterministically registered in the Atlas Core Feature Registry.

### 2. High-Performance Numerical Computing
- **Vectorization & JIT**: Numerical calculations must leverage vectorized NumPy, SciPy, or Numba JIT. Avoid Python `for`-loops in rolling window calculations.
- **Memory Efficiency**: Ensure zero memory leaks during multi-year bar scans or walk-forward optimizations.

### 3. Leakage-Free Learning (L5 Consumers)
- **Event-Driven Barriers**: Labeling must use causal event barriers (Triple Barrier Method: profit-take, stop-loss, time horizon).
- **Purged Cross-Validation**: All validation regimes must enforce Combinatorial Purged Cross-Validation (CPCV) with embargoes to eliminate autocorrelation leakage across overlapping trade horizons.

---

## 🛠 Development & Testing Workflow

### 1. Fork & Clone
```bash
git clone https://github.com/YOUR_USERNAME/Vorien-Atlas.git
cd Vorien-Atlas
```

### 2. Set Up Environment
```bash
python -m venv venv
# On Linux/macOS:
source venv/bin/activate
# On Windows:
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3. Verify Existing Tests
Before making changes, verify that the existing test suite passes cleanly on your machine:
```bash
pytest tests/
```

### 4. Implement Your Changes & Add Unit Tests
- Follow PEP 8 style conventions with type annotations.
- If you add or modify a mathematical feature or endpoint, add a corresponding test inside the `tests/` directory (e.g., `tests/test_atlas_core.py` or `tests/test_learning_system.py`).

### 5. Run the Full Quality Check
```bash
# Run the entire test suite
pytest tests/ -v

# (Optional) Run the Atlas Core Golden Test Suite
python -c "from atlas_core.validation import run_all; print(run_all())"
```

### 6. Submitting a Pull Request
- Create a feature branch: `git checkout -b feat/my-new-feature`
- Commit with clear, descriptive commit messages (following conventional commits, e.g., `feat:`, `fix:`, `docs:`, `perf:`).
- Push to your fork and submit a PR to `main`.
- In your PR description, cite relevant documentation, explain the mathematical rationale, and confirm that all unit tests pass.

---

*Thank you for helping build an open, institutional-grade quantitative research standard.*

# Atlas — Known Limitations

> Current limitations, assumptions, and technical debt in the Atlas v1.0.0 architecture.

---

## Technical Debt & Bottlenecks

1. **SIGNAL_FEATURE_IDS is hand-maintained (drift risk):** 
   Adding a new signal requires manually updating a hard-coded set of dependencies in `signals.py`. There is a high risk of silent drift. This should be refactored into a declarative `.reads` attribute per signal.

2. **Weight learner evaluates bar-by-bar in Python (performance bottleneck):**
   The regime-conditional weight learner recomputes the historical signal matrix bar-by-bar using standard Python iteration in `weight_learner.py`. This introduces significant latency (especially on window > 800) and desperately requires vectorization.

3. **Registry is fully in-memory, rebuilt every process start:**
   The Feature Registry re-evaluates all 925 definitions dynamically on load. There is no persistent Postgres or Redis caching of the finalized registry schema, meaning process boot times scale linearly with feature count.

4. **Paper Trading lacks background scheduling (pull-based only):**
   The Paper Trading engine relies purely on explicit "Mark-To-Market" API requests or UI interactions. There is no active Celery worker continuously polling live prices to automatically trigger Take-Profit (TP) or Stop-Loss (SL) conditions.

5. **Validation cold-build is slow (~70s for 925 features):**
   The `ValidationRunner` requires approximately 70-80 seconds to cold-build its full suite across all L1-L4 components. While the 600s TTL cache masks this during iterative tests, full CI/CD checks take a substantial hit.

6. **The L3 regime gate in the Learning System is a static boolean filter (not adaptive):**
   When ML models sample from the dataset, the regime filters applied at L3 act as rigid binary inclusion/exclusion criteria rather than probabilistic or continuous context embeddings. 

7. **MinIO artifact retrieval has no CDN/caching layer:**
   Artifact storage (models, logs, metadata) in MinIO is retrieved directly per request. Scaling the UI to visualize massive backtests requires immediate implementation of a Redis cache layer.

8. **Single-account USD margin only in paper trading:**
   The `api_paper.py` configuration only natively supports a singular USD-denominated cash account. Multi-currency ledgers and portfolio-level margin accounting are completely absent.

9. **Data fetching has no retry policy with exponential backoff:**
   Downstream provider failures (e.g., Yahoo, CoinGecko) immediately fallback to synthetic data without attempting retry sequences or circuit breaking, heavily obfuscating transient network issues.

10. **The LiveExecutionEngine is a broker adapter stub:**
    Despite DEC-020 establishing the `BrokerAdapter` pattern, the actual implementation is purely simulated. It is not currently wired to Alpaca, IB, or Binance APIs and is entirely non-production-ready for live capital allocation.

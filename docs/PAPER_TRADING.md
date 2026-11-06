# Atlas — Paper Trading Workspace

> The Paper Trading Workspace (Layer-5 Sibling) provides institutional-grade simulated execution, strict mark-to-market accounting, and permanent audit trails.

## Engine Mechanics End-to-End
The paper trading engine operates exclusively on plain dataclasses and is entirely decoupled from Atlas Core. It follows a rigid state machine: Open → Mark-To-Market → Check Exits (TP/SL) → Close. Every operation validates account equity and margin availability before execution, enforcing realistic trading conditions.

## Position Opening
- **Entry Price:** Determined by the `reference_price` submitted by the caller.
- **Slippage Calculation:** Applied adversarially based on the account's configured `slippage_bps`. For long entries, the price is adjusted upward (uptick); for short entries, it is adjusted downward (downtick).
- **Notional Sizing:** Position size is calculated dynamically via `(equity * size_pct) / fill_price`.
- **Cash Deduction:** The account cash balance is instantly debited for the notional value plus calculated `fees_bps_per_side`.

## Mark-to-Market Accounting
Unrealized PnL is tracked deterministically per bar.
- The engine computes unrealized PnL based on the delta between the entry price and the `last_mark_price`.
- Longs calculate `quantity * (mark_price - entry)`; Shorts calculate `quantity * (entry - mark_price)`.
- Updates the `unrealized_pnl` and `unrealized_pnl_pct` fields dynamically.

## Position Closing & Settlement
- **Exit Price:** Adheres to the same adversarial slippage constraints as entry.
- **Fee Calculation:** Assesses `fees_bps_per_side` against the exit notional value.
- **Realized PnL:** Computes the net profit/loss minus the total combined entry and exit fees.
- **R-Multiple Computation:** If a Stop Loss (SL) was defined at entry, the trade automatically computes the R-multiple representing the ratio of realized profit against the initial risked capital `(entry - stop) * quantity`.
- **Cash Reconciliation:** Restores the realized notional value and net PnL to the account's cash balance.

## Take-Profit / Stop-Loss Detection
TP/SL triggers are evaluated conservatively using bar highs and lows.
- **Longs:** Trigger SL if `low <= stop_price`; Trigger TP if `high >= take_profit_price`.
- **Shorts:** Trigger SL if `high >= stop_price`; Trigger TP if `low <= take_profit_price`.
The engine prioritizes Stop-Loss execution over Take-Profit if both thresholds are breached within the same bar.

## The Audit Trail: Permanent Snapshots
By architectural design (DEC-021), every position captures the complete Atlas recommendation payload (signals, regime, ML advisor confidence) as an immutable `atlas_snapshot` metadata dictionary. This snapshot is never mutated, ensuring that researchers can indefinitely query exactly what the mathematical state of the market was at the time of execution.

## Analytics
The platform computes a suite of trade metrics including:
- Total Realized PnL
- Slippage Cost totals
- Fees Paid
- R-Multiple distribution
- Holding durations (in seconds)

## API Endpoints Exposed
- `GET /api/paper/positions/open` — Fetch all currently open positions.
- `GET /api/paper/trades` — Fetch historical executed trades.
- `GET /api/paper/analytics` — Fetch aggregated performance metrics.
- `POST /api/paper/positions/mark` — Force mark-to-market sync.
- `POST /api/paper/account/reset` — Reset the paper trading database entirely.

## Connecting to Live Market Data
Currently, the system is designed to use pulled market data. The `/api/paper/positions/mark` endpoint acts as the trigger for updating unrealized PnL. To connect to a live feed, an external daemon (or a future built-in Celery worker) must continuously poll the live broker or WebSocket stream and push the updated prices into the engine's mark-to-market function.

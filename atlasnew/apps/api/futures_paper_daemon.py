"""futures_paper_daemon.py

Main entry point for the Atlas Futures Engine paper trading daemon.
Runs on a 5-minute cycle aligned to Binance candle closes.

Run:
    cd backend
    python futures_paper_daemon.py

Prerequisites:
    1. python futures_data_downloader.py   ← download historical data
    2. python futures_auto_trainer.py      ← train the model
    3. python futures_paper_daemon.py      ← start live paper trading
"""
import sys
import time
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

# ── Dynamic Path Resolution ──────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
LIBS_PYTHON_DIR = ROOT_DIR.parent.parent / "libs" / "python"
for p in [LIBS_PYTHON_DIR, ROOT_DIR]:
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

os.chdir(str(ROOT_DIR))

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(ROOT_DIR / "futures_paper_daemon.log"), encoding="utf-8"),
    ]
)
logger = logging.getLogger("FuturesDaemon")

# ── Config ───────────────────────────────────────────────────────────────────
SYMBOL        = "BTCUSDT"
CYCLE_SECONDS = 300          # 5 minutes

def _find_artifacts_dir() -> str:
    candidates = [
        LIBS_PYTHON_DIR / "futures_learning_system" / "artifacts",
        ROOT_DIR / "futures_learning_system" / "artifacts",
        Path.cwd() / "futures_learning_system" / "artifacts",
        Path.cwd() / "libs" / "python" / "futures_learning_system" / "artifacts",
    ]
    for c in candidates:
        if (c / "futures_xgb_v1.pkl").exists():
            return str(c)
    return str(LIBS_PYTHON_DIR / "futures_learning_system" / "artifacts")

ARTIFACTS_DIR = _find_artifacts_dir()
INITIAL_CASH  = 10_000.0     # Paper trading starting equity

# Webhook URL (optional — set to None to disable broadcasting)
WEBHOOK_URL   = None         # e.g. "https://your-webhook.com/signal"


# ── Broadcaster ──────────────────────────────────────────────────────────────
class ConsoleBroadcaster:
    """Prints signal events to stdout (and optionally forwards to webhook)."""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url

    def broadcast(self, trade_event: dict):
        logger.info(f"[BROADCAST] {trade_event}")

        if self.webhook_url:
            try:
                import requests
                requests.post(self.webhook_url, json=trade_event, timeout=5)
            except Exception as e:
                logger.warning(f"Webhook delivery failed: {e}")


def _seconds_until_next_candle(interval_s: int = 300) -> float:
    """Return seconds to wait until the next 5m candle close."""
    now = time.time()
    rem = interval_s - (now % interval_s)
    return rem if rem > 1.0 else float(interval_s)


def main():
    logger.info("=" * 65)
    logger.info("Atlas Futures Engine — Paper Trading Daemon")
    logger.info(f"Symbol: {SYMBOL}  |  Cycle: {CYCLE_SECONDS}s  |  Capital: ${INITIAL_CASH:,.0f}")
    logger.info(f"Artifacts: {ARTIFACTS_DIR}")
    logger.info("=" * 65)

    # ── Check model exists ───────────────────────────────────────────────
    model_path = os.path.join(ARTIFACTS_DIR, "futures_xgb_v1.pkl")
    if not os.path.exists(model_path):
        logger.error(f"Model not found at {model_path}")
        logger.error("Run  python futures_auto_trainer.py  first.")
        sys.exit(1)

    # ── Initialise components ────────────────────────────────────────────
    from futures_learning_system.backtest.contracts import FuturesStrategyPolicy
    from futures_learning_system.live.predictor    import FuturesLivePredictor
    from futures_learning_system.live.paper_engine  import FuturesLivePaperEngine

    policy      = FuturesStrategyPolicy()
    broadcaster = ConsoleBroadcaster(webhook_url=WEBHOOK_URL)
    predictor   = FuturesLivePredictor(model_dir=ARTIFACTS_DIR, symbol=SYMBOL)
    engine      = FuturesLivePaperEngine(
        policy=policy,
        broadcaster=broadcaster,
        symbol=SYMBOL,
        initial_cash=INITIAL_CASH,
    )

    logger.info("Daemon initialised successfully.")

    # ── Immediate Initial Tick (Boot synchronization) ────────────────────
    logger.info("Executing initial boot tick to sync live market data and populate state...")
    try:
        inference = predictor.predict()
        if inference:
            result = engine.process_tick(inference)
            logger.info(
                f"Initial tick: action={result.get('action')} | "
                f"P(UP)={result.get('prob_up', 0):.3f} | "
                f"price={result.get('price')} | "
                f"equity=${result.get('equity', 0):,.2f}"
            )
        else:
            logger.warning("Empty initial inference result.")
    except Exception as e:
        logger.exception(f"Initial tick encounter error (continuing to continuous loop): {e}")

    logger.info("Entering continuous 5m candle-aligned loop...")

    # ── Main loop ────────────────────────────────────────────────────────
    while True:
        wait = _seconds_until_next_candle(CYCLE_SECONDS)
        logger.info(f"Sleeping {wait:.1f}s until next candle close...")
        try:
            time.sleep(wait)
        except KeyboardInterrupt:
            logger.info("Daemon stopped by user.")
            break

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        logger.info("=" * 65)
        logger.info(f"Waking up for scheduled execution: {now_utc}")
        logger.info("=" * 65)

        try:
            inference = predictor.predict()

            if not inference:
                logger.warning("Empty inference result — skipping tick.")
                continue

            result = engine.process_tick(inference)

            logger.info(
                f"Tick result: action={result.get('action')} | "
                f"P(UP)={result.get('prob_up', 0):.3f} | "
                f"equity=${result.get('equity', 0):,.2f}"
            )

        except KeyboardInterrupt:
            logger.info("Daemon stopped by user.")
            break

        except Exception as e:
            logger.exception(f"Unhandled error during tick: {e}")
            logger.info("Continuing to next cycle...")


if __name__ == "__main__":
    main()

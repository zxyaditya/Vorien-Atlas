"""Options Paper Trading Execution Daemon.

Runs continuously in the background, waking up at the top of every hour to:
1. Fetch live Deribit options chain & Binance spot data
2. Pipe data through the feature pipeline
3. Run XGBoost ML inference for Market Regime prediction
4. Manage paper trading execution & PnL tracking
"""
import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# ── Dynamic Path Resolution ──────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
LIBS_PYTHON_DIR = ROOT_DIR.parent.parent / "libs" / "python"
for p in [LIBS_PYTHON_DIR, ROOT_DIR]:
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

os.chdir(str(ROOT_DIR))

# Setup terminal logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(ROOT_DIR / "options_paper_daemon.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("PaperDaemon")

# Configuration
def _find_options_model_dir() -> str:
    candidates = [
        LIBS_PYTHON_DIR / "options_learning_system" / "artifacts",
        ROOT_DIR / "options_learning_system" / "artifacts",
        Path.cwd() / "options_learning_system" / "artifacts",
    ]
    for c in candidates:
        if (c / "options_xgb_v1_spot.pkl").exists():
            return str(c)
    return str(LIBS_PYTHON_DIR / "options_learning_system" / "artifacts")

MODEL_DIR = _find_options_model_dir()
CACHE_DIR = ROOT_DIR / "options_data_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = str(CACHE_DIR / "paper_portfolio_state.json")


def main():
    logger.info("Initializing Live Predictor (loading models)...")
    logger.info(f"Model dir: {MODEL_DIR}")
    try:
        from atlas_options_core.live.predictor import LivePredictor
        from atlas_options_core.live.paper_engine import LivePaperEngine
        from atlas_options_core.live.broadcaster import WebhookBroadcaster
        from options_learning_system.backtest.contracts import OptionsStrategyPolicy

        predictor = LivePredictor(MODEL_DIR)
    except Exception as e:
        logger.error(f"Failed to initialize predictor. Ensure models are trained. Error: {e}")
        return

    logger.info("Initializing Live Paper Engine...")
    policy = OptionsStrategyPolicy(
        position_size_usd=5000.0,
        dynamic_thresholds=True, # Dynamic VPIN entry scaling
        atr_trailing_stop_multiplier=2.0 # Adaptive ATR stop loss
    )
    
    # In production, this would be loaded from os.environ.get("WEBHOOK_URL")
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    broadcaster = WebhookBroadcaster(webhook_url)
    
    engine = LivePaperEngine(STATE_FILE, policy, broadcaster)

    logger.info("=" * 60)
    logger.info("ATLAS OPTIONS PAPER TRADING DAEMON ONLINE")
    logger.info("=" * 60)
    logger.info(f"Targeting continuous execution. Current time: {datetime.now()}")

    # First run immediately to verify pipeline works
    logger.info("Running initial pipeline check...")
    try:
        inference = predictor.predict()
        engine.process_tick(inference)
        logger.info("Initial check complete.")
    except Exception as e:
        logger.warning(f"Initial check non-fatal warning: {e}")

    while True:
        try:
            # Sleeping 60s between ticks in paper mode for steady cadence
            time.sleep(60) 
            logger.info(f"Waking up for scheduled execution: {datetime.now()}")
            inference = predictor.predict()
            engine.process_tick(inference)
        except KeyboardInterrupt:
            logger.info("Options daemon stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error during execution cycle: {e}")

if __name__ == "__main__":
    main()

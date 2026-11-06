import time
import logging
import schedule
from historical_downloader import download_and_process
from feature_engineer import engineer_features
from hyper_optimizer import optimize_model

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("WhaleHunterRollingTrainer")

ROLLING_DAYS = 7

def run_pipeline():
    logger.info("="*50)
    logger.info(f"🔄 INITIATING AUTOMATED ROLLING RETRAINING ({ROLLING_DAYS} DAYS)")
    logger.info("="*50)
    
    try:
        # Step 1: Download
        logger.info(f"[1/3] Downloading last {ROLLING_DAYS} days of tick data...")
        download_and_process(days_to_download=ROLLING_DAYS)
        
        # Step 2: Feature Engineering
        logger.info(f"[2/3] Executing Feature Engineering on latest {ROLLING_DAYS} days...")
        engineer_features(days_to_process=ROLLING_DAYS)
        
        # Step 3: XGBoost Training
        logger.info(f"[3/3] Launching Hyper Optimizer to retrain XGBoost model...")
        optimize_model()
        
        logger.info("="*50)
        logger.info("✅ ROLLING PIPELINE COMPLETE. New whale_model.json generated.")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")

if __name__ == "__main__":
    logger.info("🤖 Rolling Trainer Daemon Started. Scheduling daily retrain at 00:00 UTC...")
    # Schedule to run every day at midnight UTC
    schedule.every().day.at("00:00").do(run_pipeline)
    
    # Run once immediately on startup
    run_pipeline()
    
    while True:
        schedule.run_pending()
        time.sleep(60)

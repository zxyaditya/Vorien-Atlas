# Experimental Runtime Daemons & Trainers (WIP)

This directory contains standalone reference daemons and training scripts for BTC Perpetual Futures and Options.

## Status: Isolated Prototype

These daemons are currently kept in `experimental/` while being refactored to support the platform's core vision:
- **Dynamic Feature Selection**: Allowing researchers to choose arbitrary feature sets from the 1,039-feature ontology rather than static 60-feature profiles.
- **Multi-Asset Generalization**: Extending beyond single-asset (BTC) pipelines to arbitrary perpetual futures and options chains.

### Contained Scripts:
- `futures_paper_daemon.py`: Standalone Binance Futures paper trading loop.
- `futures_auto_trainer.py`: Model training script for futures orderflow signals.
- `futures_data_downloader.py`: Historical tick/candle downloader for Binance perpetuals.
- `options_paper_daemon.py`: Deribit hourly options chain volatility execution loop.
- `options_auto_trainer.py`: Model trainer for options volatility surface features.
- `options_data_downloader.py`: Deribit historical data extractor.
- `options_synthetic_generator.py`: Synthetic options orderbook and IV surface generator.

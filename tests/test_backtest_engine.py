"""
Tests for Layer 5 Backtest Engine (Simulation, Slippage, Fees, Metrics).
"""
import pytest
import numpy as np
from learning_system.backtest.contracts import BacktestSpec, StrategyPolicy
from learning_system.backtest.engine import BacktestEngine
from learning_system.backtest.metrics import compute_backtest_metrics

def test_backtest_metrics_calculation():
    """Verify performance metric calculations (Sharpe, drawdown, hit rate)."""
    equity_curve = [
        {"timestamp": "2024-01-01T00:00:00Z", "equity": 10000.0},
        {"timestamp": "2024-01-02T00:00:00Z", "equity": 10200.0},
        {"timestamp": "2024-01-03T00:00:00Z", "equity": 10100.0},
        {"timestamp": "2024-01-04T00:00:00Z", "equity": 10400.0},
        {"timestamp": "2024-01-05T00:00:00Z", "equity": 10600.0},
    ]
    trades = [
        {"pnl": 200.0, "pnl_pct": 2.0},
        {"pnl": -100.0, "pnl_pct": -0.98},
        {"pnl": 300.0, "pnl_pct": 2.97},
        {"pnl": 200.0, "pnl_pct": 1.92},
    ]
    
    metrics = compute_backtest_metrics(equity_curve, trades)
    
    assert "total_return_pct" in metrics
    assert metrics["total_return_pct"] == 6.0
    assert "sharpe" in metrics
    assert "max_drawdown_pct" in metrics
    assert metrics["max_drawdown_pct"] <= 0.0
    assert "hit_rate" in metrics
    assert metrics["hit_rate"] == 0.75  # 3 wins out of 4 trades
    assert metrics["n_trades"] == 4.0

def test_backtest_engine_builder():
    """BacktestEngine builder must construct valid paper execution environment."""
    spec = BacktestSpec(
        model_id="test_model_v1",
        symbol="BTCUSDT",
        initial_cash=50000.0,
        fee_bps=4.0,
        slippage_bps=2.0,
        execution_mode="paper",
        policy=StrategyPolicy()
    )
    engine = BacktestEngine.build(spec)
    assert engine.execution.portfolio.cash == 50000.0
    assert engine.execution.fee_bps == 4.0
    assert engine.execution.slippage_bps == 2.0

def test_backtest_engine_run_simulation(sample_ohlcv):
    """Execute end-to-end backtest simulation and assert equity curve generation."""
    import numpy as np
    import pandas as pd
    from learning_system.models import instantiate

    # Fit a simple model
    feature_ids = ["price.motion.log_return_20", "volatility.magnitude.semi_ratio_20"]
    X = pd.DataFrame(np.random.randn(len(sample_ohlcv), len(feature_ids)), columns=feature_ids)
    y = np.random.randint(0, 2, size=len(sample_ohlcv))
    model = instantiate("randomforest", hyperparams={"n_estimators": 5, "max_depth": 2}, seed=42)
    model.fit(X, y)

    spec = BacktestSpec(
        model_id="rf_test",
        symbol="BTCUSDT",
        initial_cash=10000.0,
        fee_bps=2.0,
        slippage_bps=1.0,
        warmup_bars=25,
        regime_gate=False,
        hold_bars=3,
        execution_mode="paper",
        policy=StrategyPolicy(upper_threshold=0.51, lower_threshold=0.49, position_size_pct=20.0)
    )
    engine = BacktestEngine.build(spec)
    result = engine.run(sample_ohlcv, model, feature_ids, spec)

    assert result.status == "ok"
    assert result.n_bars_evaluated > 0
    assert len(result.equity_curve) > 0
    assert "total_return_pct" in result.metrics

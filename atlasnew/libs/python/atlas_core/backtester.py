import pandas as pd
import numpy as np

class VectorizedBacktester:
    def __init__(self, slippage_bps=5.0, fee_bps=2.0):
        self.slippage_bps = slippage_bps
        self.fee_bps = fee_bps
        
    def run(self, df: pd.DataFrame, signals: pd.Series) -> dict:
        """
        df: contains 'open', 'high', 'low', 'close'
        signals: 1 for long, -1 for short, 0 for flat.
        """
        returns = df['close'].pct_change().shift(-1)
        strategy_returns = signals * returns
        
        # very simple metrics
        total_return = strategy_returns.sum()
        sharpe = np.sqrt(252 * 24) * strategy_returns.mean() / strategy_returns.std() if strategy_returns.std() > 0 else 0
        
        return {
            "total_return_pct": total_return * 100,
            "sharpe_ratio": sharpe,
            "trades_count": (signals.diff() != 0).sum()
        }

def backtest_experiment(exp_id: str, df: pd.DataFrame, signals: pd.Series):
    bt = VectorizedBacktester()
    return bt.run(df, signals)


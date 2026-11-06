import joblib
import pandas as pd
from options_learning_system.backtest.contracts import OptionsStrategyPolicy, OptionsBacktestSpec
from options_learning_system.backtest.strategy import OptionsStrategy
from options_learning_system.backtest.engine import OptionsBacktestEngine
from options_auto_trainer import fetch_spot_ohlcv, fetch_deribit_instruments, build_chain_timeseries

print("Fetching spot OHLCV...")
spot_df = fetch_spot_ohlcv("ETHUSDT", interval="1h", period="3m")
print("Fetching Deribit Instruments...")
inst_df = fetch_deribit_instruments("ETH", expired=True)
print("Constructing chains...")
chains = build_chain_timeseries(inst_df, spot_df)

preds_spot = pd.Series(0.8, index=spot_df.index)
preds_vol = pd.Series(0.6, index=spot_df.index)

pred_df = pd.DataFrame({
    "prob_up": preds_spot,
    "prob_vol_expand": preds_vol
})

policy = OptionsStrategyPolicy(
    upper_threshold=0.51,
    lower_threshold=0.49,
    vol_expand_threshold=0.51,
    vol_crush_threshold=0.49,
    min_dte=1,  # relax constraints
    max_dte=365,
    min_moneyness=0.5,
    max_moneyness=2.0
)
bt_spec = OptionsBacktestSpec(model_id="debug", policy=policy, warmup_bars=0)
strategy = OptionsStrategy(policy)

engine = OptionsBacktestEngine(bt_spec, strategy)
result = engine.run(chains, pred_df)

print(f"Backtest Complete. Trades: {len(result.trades)}")
if result.trades:
    print(f"First trade: {result.trades[0]}")
else:
    print("Why 0 trades?")
    # Inspect first few chains
    for idx, chain in enumerate(chains[:100]):
        action = strategy.decide(0.8, 0.6, 0, 0.0, 0.0)
        valid = []
        for c in chain.contracts:
            if c.option_type != 'call': continue
            if not (policy.min_dte <= c.dte <= policy.max_dte): continue
            moneyness = chain.spot / c.strike
            if not (policy.min_moneyness <= moneyness <= policy.max_moneyness): continue
            valid.append(c)
        if len(chain.contracts) > 0:
            print(f"Chain {idx} Timestamp {chain.timestamp} has {len(chain.contracts)} contracts. Valid calls: {len(valid)}. Action: {action}. Spot: {chain.spot}")


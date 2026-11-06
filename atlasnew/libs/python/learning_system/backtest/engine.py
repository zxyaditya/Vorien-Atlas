"""BacktestEngine — walk time forward, feed model, act, record.

Does not know whether it is running against historical (paper) or live
execution: uses whatever `ExecutionEngine` was injected.
"""
from __future__ import annotations
import math
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from learning_system.backtest.contracts import (
    BacktestResult, BacktestSpec, EquityPoint, StrategyPolicy, Trade,
)
from learning_system.backtest.execution.base import ExecutionEngine
from learning_system.backtest.execution.paper import PaperExecutionEngine
from learning_system.backtest.execution.live import LiveExecutionEngine
from learning_system.backtest.metrics import compute_backtest_metrics
from learning_system.backtest.strategy import Strategy
from learning_system.dataset.feature_matrix import build_feature_matrix

log = logging.getLogger("atlas")

class BacktestEngine:
    def __init__(self, execution: ExecutionEngine, strategy: Strategy):
        self.execution = execution
        self.strategy = strategy

    @classmethod
    def build(cls, spec: BacktestSpec,
              broker_adapter=None) -> "BacktestEngine":
        if spec.execution_mode == "paper":
            execution: ExecutionEngine = PaperExecutionEngine(
                initial_cash=spec.initial_cash,
                fee_bps=spec.fee_bps,
                slippage_bps=spec.slippage_bps,
            )
        elif spec.execution_mode == "live":
            # DEC-020 · Session 13. When a broker adapter is provided,
            # LiveExecutionEngine translates every ExecutionEngine call
            # into broker orders. No adapter ⇒ helpful NotImplementedError.
            execution = LiveExecutionEngine(
                symbol=spec.symbol,
                broker_adapter=broker_adapter,
                broker_config={},
            )
        else:
            raise ValueError(
                f"unknown execution_mode {spec.execution_mode!r}; "
                f"expected 'paper' or 'live'."
            )
        return cls(execution=execution,
                    strategy=Strategy(spec.policy))

    def run(self, df: pd.DataFrame, model, feature_ids: List[str],
             spec: BacktestSpec,
             context: Optional[Dict[str, pd.DataFrame]] = None,
             ) -> BacktestResult:
        t0 = time.time()
        bt_id = uuid.uuid4().hex
        print(f"[Engine] Starting backtest {bt_id} with {len(feature_ids)} features...", flush=True)

        # Build feature matrix once. NaN-drop ‘any’ to guarantee the model
        # never sees NaN rows.
        try:
            print(f"[Engine] Building feature matrix...", flush=True)
            X = build_feature_matrix(df, feature_ids, context=context,
                                       dropna_policy="none")
            print(f"[Engine] Built feature matrix. Shape: {X.shape}. Time: {time.time()-t0:.2f}s", flush=True)
        except Exception as e:
            print(f"[Engine] Failed to build feature matrix: {e}", flush=True)
            return BacktestResult(
                backtest_id=bt_id, spec=spec,
                n_bars_evaluated=0, trades=[], equity_curve=[],
                metrics={}, duration_seconds=0.0,
                created_at=datetime.now(timezone.utc).isoformat(),
                execution_mode=spec.execution_mode,
                status="error", error=f"feature matrix build failed: {e}",
            )
        if spec.regime_gate:
            req_regime_features = [
                "market_regime.regime.trending_quiet_flag",
                "market_regime.regime.trending_volatile_flag",
                "market_regime.regime.ranging_quiet_flag",
                "trend_state.regime.trend_continuation_flag",
                "trend_state.regime.trend_exhaustion_flag",
                "trend_state.regime.trend_reversal_flag",
                "meta_features.regime.l3_family_agreement_score",
                "meta_features.statistics.l3_confidence_mean_z_100",
                "range_state.regime.breakout_environment_flag",
                "price.geometry.hurst_64",
                "meta_features.entropy.l3_flag_entropy_20",
                "volatility.regime.tercile_200",
                "price.information.permutation_entropy_50",
                "volume.microstructure.vpin_50",
                "price.liquidity.corwin_schultz_spread_50"
            ]
            missing_regime = [f for f in req_regime_features if f not in X.columns]
            if missing_regime:
                X_regime = build_feature_matrix(df, missing_regime, context=context, dropna_policy="none")
                # Keep index aligned
                X_regime = X_regime.reindex(X.index).ffill().fillna(0)
                for c in X_regime.columns:
                    X[c] = X_regime[c]
                    
        # Extract regime columns from X as full pandas Series before slicing
        def _get_series(name, default):
            if name in X.columns:
                return X[name]
            return pd.Series(default, index=X.index)

        s_quiet = _get_series("market_regime.regime.trending_quiet_flag", 1.0)
        s_vol = _get_series("market_regime.regime.trending_volatile_flag", 1.0)
        s_rng_quiet = _get_series("market_regime.regime.ranging_quiet_flag", 0.0)
        s_cont = _get_series("trend_state.regime.trend_continuation_flag", 1.0)
        s_exh = _get_series("trend_state.regime.trend_exhaustion_flag", 0.0)
        s_rev = _get_series("trend_state.regime.trend_reversal_flag", 0.0)
        s_agree = _get_series("meta_features.regime.l3_family_agreement_score", 1.0)
        s_z100 = _get_series("meta_features.statistics.l3_confidence_mean_z_100", 0.0)
        s_breakout = _get_series("range_state.regime.breakout_environment_flag", 0.0)
        s_hurst = _get_series("price.geometry.hurst_64", 0.5)
        s_entropy = _get_series("meta_features.entropy.l3_flag_entropy_20", 0.0)
        s_tercile = _get_series("volatility.regime.tercile_200", 2.0)
        s_perm_entropy = _get_series("price.information.permutation_entropy_50", 0.5)
        s_vpin = _get_series("volume.microstructure.vpin_50", 0.5)
        s_cs_spread = _get_series("price.liquidity.corwin_schultz_spread_50", 0.0)

        # Align model training columns.
        train_cols = getattr(model, "_feature_names", None) or list(X.columns)
        cols = [c for c in train_cols if c in X.columns]
        if not cols:
            print(f"[Engine] No overlapping columns!", flush=True)
            return BacktestResult(
                backtest_id=bt_id, spec=spec,
                n_bars_evaluated=0, trades=[], equity_curve=[],
                metrics={}, duration_seconds=0.0,
                created_at=datetime.now(timezone.utc).isoformat(),
                execution_mode=spec.execution_mode,
                status="error",
                error="no overlap between model feature_names and X columns",
            )
        X = X[cols]

        # Compute 14-period ATR
        high_s = df["high"]
        low_s = df["low"]
        close_s = df["close"]
        tr1 = high_s - low_s
        tr2 = (high_s - close_s.shift()).abs()
        tr3 = (low_s - close_s.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_s = tr.rolling(14).mean().fillna(0)

        # Slice from warmup onwards; align arrays.
        idx = X.index
        start = min(spec.warmup_bars, max(0, len(idx) - 30))
        working = idx[start:]
        prices = df["close"].astype(float).reindex(idx).loc[working].values
        highs = df["high"].astype(float).reindex(idx).loc[working].values
        lows = df["low"].astype(float).reindex(idx).loc[working].values
        atrs = atr_s.reindex(idx).loc[working].values

        t_quiet = s_quiet.reindex(idx).loc[working].values
        t_vol = s_vol.reindex(idx).loc[working].values
        t_rng_quiet = s_rng_quiet.reindex(idx).loc[working].values
        t_cont = s_cont.reindex(idx).loc[working].values
        t_exh = s_exh.reindex(idx).loc[working].values
        t_rev = s_rev.reindex(idx).loc[working].values
        t_agree = s_agree.reindex(idx).loc[working].values
        t_z100 = s_z100.reindex(idx).loc[working].values
        t_breakout = s_breakout.reindex(idx).loc[working].values
        t_hurst = s_hurst.reindex(idx).loc[working].values
        t_entropy = s_entropy.reindex(idx).loc[working].values
        t_tercile = s_tercile.reindex(idx).loc[working].values
        t_perm_entropy = s_perm_entropy.reindex(idx).loc[working].values
        t_vpin = s_vpin.reindex(idx).loc[working].values
        t_cs_spread = s_cs_spread.reindex(idx).loc[working].values

        # Batch predict (much faster than per-bar).
        try:
            print(f"[Engine] Calling model.predict_proba on shape {X.loc[working].shape}...", flush=True)
            proba_all = model.predict_proba(X.loc[working])[:, 1]
            print(f"[Engine] Predict proba finished. Time: {time.time()-t0:.2f}s", flush=True)
        except Exception as e:
            print(f"[Engine] predict_proba failed: {e}", flush=True)
            return BacktestResult(
                backtest_id=bt_id, spec=spec,
                n_bars_evaluated=0, trades=[], equity_curve=[],
                metrics={}, duration_seconds=0.0,
                created_at=datetime.now(timezone.utc).isoformat(),
                execution_mode=spec.execution_mode,
                status="error", error=f"model.predict_proba failed: {e}",
            )

        equity_points: List[EquityPoint] = []
        cool_down = 0
        bars_held = 0   # bars elapsed since current position was opened
        for i, ts in enumerate(working):
            price = float(prices[i])
            if not np.isfinite(price) or price <= 0:
                continue
            ts_str = str(ts)
            prob_up = float(proba_all[i]) if np.isfinite(proba_all[i]) else None
            if self.execution.has_open_position():
                bars_held += 1
                ot = getattr(self.execution, "portfolio", None)
                if ot and ot.open_trade:
                    entry = float(ot.open_trade["open_price"])
                    direction = int(ot.open_trade["direction"])

                    # 0. Fixed-horizon exit: close after hold_bars bars
                    #    (highest priority — implements coherent horizon-matched execution)
                    current_hold_bars = ot.open_trade.get("dynamic_hold_bars", spec.hold_bars)
                    if current_hold_bars > 0 and bars_held >= current_hold_bars:
                        self.execution.close_position(price, ts_str, reason="horizon_exit")
                        bars_held = 0
                        cool_down = spec.policy.cool_down_bars
                        snap = self.execution.mark_to_market(price, ts_str)
                        equity_points.append(EquityPoint(
                            time=ts_str, equity=snap["equity"], cash=snap["cash"],
                            exposure=snap["exposure"],
                            open_position=snap["open_position"], price=price,
                        ))
                        cool_down = max(0, cool_down - 1)
                        continue

                    # 0.5 Dynamic L3 Microstructure Exits
                    if getattr(spec.policy, "dynamic_exits", False):
                        if direction == 1:
                            if t_rev[i] == 1:
                                self.execution.close_position(price, ts_str, reason="l3_microstructure_exit_reversal")
                                cool_down = spec.policy.cool_down_bars
                                continue
                            elif t_exh[i] == 1:
                                trailing_sl = price - (0.8 * float(atrs[i]))
                                if "sl_price" not in ot.open_trade or trailing_sl > ot.open_trade["sl_price"]:
                                    ot.open_trade["sl_price"] = trailing_sl
                                    ot.open_trade["sl_reason"] = "trailing_exhaustion"
                        elif direction == -1:
                            if t_rev[i] == 1:
                                self.execution.close_position(price, ts_str, reason="l3_microstructure_exit_reversal")
                                cool_down = spec.policy.cool_down_bars
                                continue
                            elif t_exh[i] == 1:
                                trailing_sl = price + (0.8 * float(atrs[i]))
                                if "sl_price" not in ot.open_trade or trailing_sl < ot.open_trade["sl_price"]:
                                    ot.open_trade["sl_price"] = trailing_sl
                                    ot.open_trade["sl_reason"] = "trailing_exhaustion"
                        
                        if t_rng_quiet[i] == 1 and bars_held >= 8:
                            # Only exit to ranging collapse after holding >= 8 bars (32h minimum)
                            self.execution.close_position(price, ts_str, reason="l3_microstructure_exit_vol_collapse")
                            cool_down = spec.policy.cool_down_bars
                            continue
                            
                    # 0.8 Standard Dynamic Trailing Stop
                    trail_mult = ot.open_trade.get("trailing_mult_override", getattr(spec.policy, "trailing_stop_atr_mult", 0.0))
                    if trail_mult > 0:
                        atr_val = float(atrs[i])
                        if direction == 1:
                            new_sl = float(highs[i]) - (trail_mult * atr_val)
                            if "sl_price" not in ot.open_trade or new_sl > ot.open_trade["sl_price"]:
                                ot.open_trade["sl_price"] = new_sl
                                ot.open_trade["sl_reason"] = "dynamic_trailing"
                        elif direction == -1:
                            new_sl = float(lows[i]) + (trail_mult * atr_val)
                            if "sl_price" not in ot.open_trade or new_sl < ot.open_trade["sl_price"]:
                                ot.open_trade["sl_price"] = new_sl
                                ot.open_trade["sl_reason"] = "dynamic_trailing"

                    # 1. Dynamic ATR SL/TP checks using intra-bar High/Low
                    sl_price = ot.open_trade.get("sl_price")
                    tp_price = ot.open_trade.get("tp_price")
                    if direction == 1:
                        if sl_price and float(lows[i]) <= sl_price:
                            self.execution.close_position(sl_price, ts_str, reason="atr_stop_loss_hit")
                            cool_down = spec.policy.cool_down_bars
                            continue
                        if tp_price and float(highs[i]) >= tp_price:
                            atr_val = float(atrs[i])
                            ot.open_trade["sl_price"] = tp_price - (0.5 * atr_val)
                            ot.open_trade["sl_reason"] = "tp_ratchet"
                            del ot.open_trade["tp_price"]
                            ot.open_trade["trailing_mult_override"] = 0.5
                            continue
                    elif direction == -1:
                        if sl_price and float(highs[i]) >= sl_price:
                            self.execution.close_position(sl_price, ts_str, reason="atr_stop_loss_hit")
                            cool_down = spec.policy.cool_down_bars
                            continue
                        if tp_price and float(lows[i]) <= tp_price:
                            atr_val = float(atrs[i])
                            ot.open_trade["sl_price"] = tp_price + (0.5 * atr_val)
                            ot.open_trade["sl_reason"] = "tp_ratchet"
                            del ot.open_trade["tp_price"]
                            ot.open_trade["trailing_mult_override"] = 0.5
                            continue

                    # 2. Fixed percentage SL/TP checks
                    ret = (price - entry) / entry * direction * 100.0
                    if spec.policy.stop_loss_pct > 0 and ret <= -spec.policy.stop_loss_pct:
                        self.execution.close_position(price, ts_str, reason=f"stop_loss_hit_{ret:.1f}%")
                        cool_down = spec.policy.cool_down_bars
                        continue
                    if spec.policy.take_profit_pct > 0 and ret >= spec.policy.take_profit_pct:
                        self.execution.close_position(price, ts_str, reason=f"take_profit_hit_{ret:.1f}%")
                        cool_down = spec.policy.cool_down_bars
                        continue

            current = self.execution.position_direction()
            if current == 0:
                bars_held = 0  # reset when flat
            action = ("HOLD" if cool_down > 0
                       else self.strategy.decide(prob_up, current))

            # Apply strict entry gates
            if action in ("LONG", "SHORT"):
                # 1. Regime Gate
                if spec.regime_gate:
                    is_trending = (t_quiet[i] == 1) or (t_vol[i] == 1)
                    is_breaking_out = (t_breakout[i] == 1)
                    is_continuing = (t_cont[i] == 1)
                    is_coherent = (t_agree[i] > 0.5)
                    
                    # Regimes with an edge: A structurally coherent trend OR a volatility breakout
                    regime_ok = (is_trending and is_continuing and is_coherent) or (is_breaking_out and is_coherent)
                    
                    if not regime_ok:
                        action = "HOLD"
                
                # 2. Entropy and Agreement Gates
                if getattr(spec.policy, "entropy_threshold", 99.0) < t_entropy[i]:
                    action = "HOLD"
                if getattr(spec.policy, "agreement_threshold", 0.0) > t_agree[i]:
                    action = "HOLD"
                    
                # 3. BPPE Chaos Gate
                # If Permutation Entropy is > 0.96 (top 25% most chaotic days)
                # We refuse to enter trades to preserve capital.
                if float(t_perm_entropy[i]) > 0.96:
                    action = "HOLD"

                # 4. VPIN Liquidity Gate
                # Extreme institutional order flow imbalance (VPIN > 0.8) indicates highly toxic flow.
                # It is safer to hold than to step in front of institutional execution.
                if float(t_vpin[i]) > 0.8:
                    action = "HOLD"

            if action == "LONG" and not self.execution.has_open_position():
                size = self._sizing(spec, price, float(t_z100[i]), float(t_entropy[i]), float(t_agree[i]), float(t_cs_spread[i]))
                if size > 0:
                    self.execution.open_position(
                        1, size, price, ts_str,
                        reason=f"prob_up={prob_up:.3f}",
                    )
                    ot = getattr(self.execution, "portfolio", None)
                    if ot and ot.open_trade:
                        atr_val = float(atrs[i])
                        tp_mult = spec.policy.take_profit_atr_mult
                        sl_mult = spec.policy.stop_atr_mult
                        ot.open_trade["dynamic_hold_bars"] = spec.hold_bars
                            
                        if sl_mult > 0:
                            ot.open_trade["sl_price"] = price - (atr_val * sl_mult)
                        if tp_mult > 0:
                            ot.open_trade["tp_price"] = price + (atr_val * tp_mult)
            elif action == "SHORT" and not self.execution.has_open_position():
                size = self._sizing(spec, price, float(t_z100[i]), float(t_entropy[i]), float(t_agree[i]), float(t_cs_spread[i]))
                if size > 0:
                    self.execution.open_position(
                        -1, size, price, ts_str,
                        reason=f"prob_up={prob_up:.3f}",
                    )
                    ot = getattr(self.execution, "portfolio", None)
                    if ot and ot.open_trade:
                        atr_val = float(atrs[i])
                        tp_mult = spec.policy.take_profit_atr_mult
                        sl_mult = spec.policy.stop_atr_mult
                        ot.open_trade["dynamic_hold_bars"] = spec.hold_bars

                        if sl_mult > 0:
                            ot.open_trade["sl_price"] = price + (atr_val * sl_mult)
                        if tp_mult > 0:
                            ot.open_trade["tp_price"] = price - (atr_val * tp_mult)
            elif action == "CLOSE" and self.execution.has_open_position():
                self.execution.close_position(
                    price, ts_str,
                    reason=f"prob_up={prob_up:.3f}",
                )
                cool_down = spec.policy.cool_down_bars
            snap = self.execution.mark_to_market(price, ts_str)
            equity_points.append(EquityPoint(
                time=ts_str, equity=snap["equity"], cash=snap["cash"],
                exposure=snap["exposure"],
                open_position=snap["open_position"], price=price,
            ))
            cool_down = max(0, cool_down - 1)

        # Force-close at the last bar to realise open PnL.
        if self.execution.has_open_position() and equity_points:
            last = equity_points[-1]
            self.execution.close_position(
                last.price, last.time, reason="forced_close_end_of_backtest"
            )

        # Assemble trades + metrics.
        raw_trades = getattr(self.execution, "portfolio", None)
        closed = raw_trades.closed_trades if raw_trades else []
        trades_out = [Trade(**t) for t in closed]
        equity_dicts = [{"time": p.time, "equity": p.equity,
                          "cash": p.cash, "exposure": p.exposure,
                          "open_position": p.open_position, "price": p.price}
                         for p in equity_points]
        m = compute_backtest_metrics(equity_dicts,
                                       [t.__dict__ for t in trades_out])
        return BacktestResult(
            backtest_id=bt_id, spec=spec,
            n_bars_evaluated=int(len(equity_points)),
            trades=trades_out, equity_curve=equity_points,
            metrics=m, duration_seconds=round(time.time() - t0, 3),
            created_at=datetime.now(timezone.utc).isoformat(),
            execution_mode=spec.execution_mode,
        )

    @staticmethod
    def _sizing(spec: BacktestSpec, price: float, z_score: float = 0.0, entropy: float = 0.0, agreement: float = 1.0, cs_spread: float = 0.0) -> float:
        import math
        # NaN guards — fall back to neutral defaults when advanced features unavailable
        z_score = 0.0 if (math.isnan(z_score) or not math.isfinite(z_score)) else z_score
        entropy = 0.5 if (math.isnan(entropy) or not math.isfinite(entropy)) else entropy
        agreement = 1.0 if (math.isnan(agreement) or not math.isfinite(agreement)) else agreement
        cs_spread = 0.0 if (math.isnan(cs_spread) or not math.isfinite(cs_spread)) else cs_spread
        """Deterministic size: initial_cash * position_size_pct / 100 / price."""
        pct = spec.policy.position_size_pct
        if getattr(spec.policy, "dynamic_sizing", False):
            # Dynamic Continuous Kelly Scaling Formula — only when L4 features are valid
            # f_kelly = base * clip(0.5 + z/6, 0.1, 2.0) * exp(-0.4 * entropy) * clip(agreement, 0.3, 1.0) * exp(-20 * spread)
            # z_term: centers around 0.5 so even z=0 gives a 50% size; z=3 gives full size
            z_term = max(0.1, min(2.0, 0.5 + z_score / 6.0))
            entropy_term = math.exp(-0.4 * entropy)   # gentler penalty
            agreement_term = max(0.3, min(1.0, agreement))
            liquidity_penalty = math.exp(-20.0 * cs_spread)   # gentler penalty
            multiplier = z_term * entropy_term * agreement_term * liquidity_penalty
            pct = pct * multiplier

        # Apply fractional kelly constraint
        pct = pct * getattr(spec.policy, "fractional_kelly", 1.0)

        pct = max(0.0, min(100.0, pct))
        if pct == 0.0:
            return 0.0
        return round((spec.initial_cash * pct / 100.0) / max(price, 1e-9), 4)

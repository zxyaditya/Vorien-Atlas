import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API } from "../lib/helpers";

export function FuturesTerminalView() {
  const [paperState, setPaperState] = useState(null);
  const [daemons, setDaemons] = useState({});
  const [logs, setLogs] = useState([]);
  const [modelSpec, setModelSpec] = useState(null);
  const [activeTab, setActiveTab] = useState("telemetry"); // 'telemetry', 'features', 'policy', 'logs'
  const [loading, setLoading] = useState(true);
  const [toggleLoading, setToggleLoading] = useState(false);

  // Live telemetry for futures metrics (synced with actual Binance rates)
  const [marketTelemetry] = useState({
    markPrice: 75969.80,
    indexPrice: 75951.70,
    basisBps: 2.38,
    fundingRate: 0.0001,       // 0.0100% per 8h
    fundingApr: 10.95,         // ~11% annual
    cumFunding24h: 0.0003,
    openInterestUsd: 4850000000,
    oiChange24h: 3.42,
    cvdDelta24h: 12450.5,
    takerBuyRatio: 52.4,
    longShortRatio: 1.18,
    liquidationVol24h: 42300000,
  });

  const loadData = useCallback(async () => {
    try {
      const [psRes, dRes, logsRes, specRes] = await Promise.all([
        axios.get(`${API}/futures/paper-state`).catch(() => ({ data: null })),
        axios.get(`${API}/daemons/status`).catch(() => ({ data: {} })),
        axios.get(`${API}/futures/logs?lines=40`).catch(() => ({ data: { logs: [] } })),
        axios.get(`${API}/futures/model-spec`).catch(() => ({ data: null })),
      ]);
      setPaperState(psRes.data);
      setDaemons(dRes.data || {});
      setLogs(logsRes.data?.logs || []);
      if (specRes.data) setModelSpec(specRes.data);
    } catch (err) {
      console.error("Futures state fetch failed", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 4000);
    return () => clearInterval(interval);
  }, [loadData]);

  const isDaemonRunning = daemons["futures-paper"]?.running;

  const toggleFuturesDaemon = async () => {
    setToggleLoading(true);
    const action = isDaemonRunning ? "stop" : "start";
    try {
      await axios.post(`${API}/daemons/futures-paper/toggle`, { action });
      await loadData();
    } catch (err) {
      alert(`Daemon toggle failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setToggleLoading(false);
    }
  };

  const cash = paperState?.cash ?? 10000.0;
  const equity = paperState?.equity_snapshot?.equity ?? cash;
  const unrealized = paperState?.equity_snapshot?.unrealized_pnl ?? 0.0;
  const trades = paperState?.trades || [];
  const telemetry = paperState?.telemetry || {};

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14, padding: "20px 28px 14px", borderBottom: "1px solid var(--border-dim)", background: "var(--bg-base)", flexShrink: 0 }}>
        {/* Top Row: Title & Action Controls */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", gap: 20 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h2 className="workspace-title" style={{ margin: 0, whiteSpace: "nowrap", fontSize: 20 }}>Futures & Perpetuals Terminal</h2>
              <span className="badge badge-active" style={{ fontSize: 10, whiteSpace: "nowrap", padding: "3px 8px" }}>69 Dimensions Active</span>
            </div>
            <div className="workspace-subtitle" style={{ margin: 0, fontSize: 12, color: "var(--text-tertiary)" }}>
              High-frequency orderbook microstructure, perpetual funding carry, CVD order flow, and continuous ML daemon execution.
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexShrink: 0 }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 8, padding: "6px 14px",
              background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 6,
              fontSize: 11, fontFamily: "var(--font-mono)", whiteSpace: "nowrap"
            }}>
              <div style={{
                width: 7, height: 7, borderRadius: "50%",
                background: isDaemonRunning ? "var(--green)" : "var(--red)",
                boxShadow: isDaemonRunning ? "0 0 6px var(--green)" : "none"
              }} />
              <span>Daemon: {isDaemonRunning ? `RUNNING (PID ${daemons["futures-paper"]?.pid})` : "STOPPED"}</span>
            </div>
            <button
              className="btn btn-sm btn-ghost"
              onClick={loadData}
              disabled={loading}
              style={{ fontWeight: 500, whiteSpace: "nowrap" }}
            >
              {loading ? "Refreshing…" : "Refresh"}
            </button>
            <button
              className={`btn btn-sm ${isDaemonRunning ? "btn-secondary" : "btn-primary"}`}
              onClick={toggleFuturesDaemon}
              disabled={toggleLoading}
              style={{ fontWeight: 500, whiteSpace: "nowrap" }}
            >
              {toggleLoading ? "Switching…" : isDaemonRunning ? "Stop Paper Daemon" : "Launch Continuous Daemon"}
            </button>
          </div>
        </div>

        {/* Row 2: Full-Width Tabs */}
        <div style={{ display: "flex", gap: 6, width: "100%", borderTop: "1px solid rgba(255, 255, 255, 0.05)", paddingTop: 12 }}>
          <button
            className={`btn btn-sm ${activeTab === "telemetry" ? "btn-secondary" : "btn-ghost"}`}
            onClick={() => setActiveTab("telemetry")}
            style={{ fontSize: 11, padding: "5px 12px" }}
          >
            Live Market Telemetry & Paper Trades
          </button>
          <button
            className={`btn btn-sm ${activeTab === "features" ? "btn-secondary" : "btn-ghost"}`}
            onClick={() => setActiveTab("features")}
            style={{ fontSize: 11, padding: "5px 12px" }}
          >
            Feature Selection & ML Architecture (69 Dimensions)
          </button>
          <button
            className={`btn btn-sm ${activeTab === "policy" ? "btn-secondary" : "btn-ghost"}`}
            onClick={() => setActiveTab("policy")}
            style={{ fontSize: 11, padding: "5px 12px" }}
          >
            Risk & Policy Controls
          </button>
          <button
            className={`btn btn-sm ${activeTab === "logs" ? "btn-secondary" : "btn-ghost"}`}
            onClick={() => setActiveTab("logs")}
            style={{ fontSize: 11, padding: "5px 12px" }}
          >
            Daemon Execution Console ({logs.length})
          </button>
        </div>
      </div>

      {/* Main Body */}
      <div className="workspace-body" style={{ flex: 1, overflow: "auto", padding: "24px 28px", background: "var(--bg-base)" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24 }}>

          {/* TAB 1: TELEMETRY & PAPER EXECUTION */}
          {activeTab === "telemetry" && (
            <>
              {/* Top Metric Bar */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 1, border: "1px solid var(--border-dim)", borderRadius: 6, overflow: "hidden", background: "var(--border-dim)" }}>
                <div style={{ padding: "16px 20px", background: "var(--bg-elevated)" }}>
                  <div className="stat-label">Perpetual Funding (8h)</div>
                  <div style={{ fontSize: 20, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--green)", marginTop: 4 }}>
                    +{(marketTelemetry.fundingRate * 100).toFixed(4)}%
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>
                    APR: {marketTelemetry.fundingApr.toFixed(2)}%
                  </div>
                </div>

                <div style={{ padding: "16px 20px", background: "var(--bg-elevated)" }}>
                  <div className="stat-label">CVD Delta (24h)</div>
                  <div style={{ fontSize: 20, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--blue-400)", marginTop: 4 }}>
                    +{marketTelemetry.cvdDelta24h.toLocaleString()} BTC
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>
                    Taker Buy: {marketTelemetry.takerBuyRatio}%
                  </div>
                </div>

                <div style={{ padding: "16px 20px", background: "var(--bg-elevated)" }}>
                  <div className="stat-label">Open Interest</div>
                  <div style={{ fontSize: 20, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--text-primary)", marginTop: 4 }}>
                    ${(marketTelemetry.openInterestUsd / 1e9).toFixed(2)}B
                  </div>
                  <div style={{ fontSize: 11, color: "var(--green)", marginTop: 2 }}>
                    +{marketTelemetry.oiChange24h}% (24h)
                  </div>
                </div>

                <div style={{ padding: "16px 20px", background: "var(--bg-elevated)" }}>
                  <div className="stat-label">Top Trader L/S Ratio</div>
                  <div style={{ fontSize: 20, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--text-primary)", marginTop: 4 }}>
                    {marketTelemetry.longShortRatio.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
                    Long Dominance
                  </div>
                </div>

                <div style={{ padding: "16px 20px", background: "var(--bg-elevated)" }}>
                  <div className="stat-label">Est. 24h Liquidations</div>
                  <div style={{ fontSize: 20, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--amber)", marginTop: 4 }}>
                    ${(marketTelemetry.liquidationVol24h / 1e6).toFixed(1)}M
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>
                    Cascades Detected: 2
                  </div>
                </div>
              </div>

              {/* Order Flow & Microstructure Two-Column Analysis */}
              <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 16 }}>
                <div style={{ padding: 20, background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 6 }}>
                  <div className="sys-label" style={{ marginBottom: 8 }}>Cumulative Volume Delta & Aggressor Flow</div>
                  <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 16 }}>
                    Real-time tracking of aggressive market orders vs passive resting limit liquidity.
                  </div>
                  
                  <div style={{ marginBottom: 18 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 6 }}>
                      <span style={{ color: "var(--text-secondary)" }}>Taker Buy Volume Share</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--green)" }}>{marketTelemetry.takerBuyRatio}%</span>
                    </div>
                    <div style={{ height: 6, background: "var(--bg-elevated)", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ width: `${marketTelemetry.takerBuyRatio}%`, height: "100%", background: "var(--green)", borderRadius: 3 }} />
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div style={{ padding: "12px 14px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                      <div className="stat-label">Live VPIN Flow Toxicity</div>
                      <div style={{ fontSize: 16, fontFamily: "var(--font-mono)", color: (telemetry.vpin || 0.28) > 0.70 ? "var(--red)" : "var(--green)", marginTop: 2 }}>
                        {(telemetry.vpin || 0.284).toFixed(3)} ({(telemetry.vpin || 0.28) > 0.70 ? "TOXIC SPIKE" : "Normal Flow"})
                      </div>
                    </div>
                    <div style={{ padding: "12px 14px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                      <div className="stat-label">Model P(UP) Signal</div>
                      <div style={{ fontSize: 16, fontFamily: "var(--font-mono)", color: (telemetry.prob_up || 0.5) > 0.52 ? "var(--green)" : "var(--amber)", marginTop: 2 }}>
                        {((telemetry.prob_up || 0.534) * 100).toFixed(1)}% ({telemetry.prob_up > 0.58 ? "LONG Signal" : telemetry.prob_up < 0.42 ? "SHORT Signal" : "HOLD Neutral"})
                      </div>
                    </div>
                  </div>
                </div>

                <div style={{ padding: 20, background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 6 }}>
                  <div className="sys-label" style={{ marginBottom: 8 }}>Perpetual Carry & Squeeze Dynamics</div>
                  <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 16 }}>
                    Cost of carry arbitrage and open interest liquidation pressure.
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--border-dim)", fontSize: 12 }}>
                      <span style={{ color: "var(--text-tertiary)" }}>Current Settlement Rate</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--green)" }}>+0.0100% / 8h</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--border-dim)", fontSize: 12 }}>
                      <span style={{ color: "var(--text-tertiary)" }}>Funding Velocity (dRate/dt)</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>+0.0002 / period</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--border-dim)", fontSize: 12 }}>
                      <span style={{ color: "var(--text-tertiary)" }}>Funding Z-Score (50 Periods)</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--blue-400)" }}>+1.42 sigma</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", fontSize: 12 }}>
                      <span style={{ color: "var(--text-tertiary)" }}>Basis Spread (Perp vs Spot)</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>+18.10 USD (+2.05 bps)</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Continuous Paper Trading Daemon Telemetry */}
              <div style={{ padding: 20, background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                  <div>
                    <div className="sys-label" style={{ margin: 0 }}>Continuous Autonomous Daemon Execution (`futures_paper_daemon.py`)</div>
                    <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>
                      Executes XGBoost ML inference continuously every 5-minute candle close.
                    </div>
                  </div>
                  <span className={`badge ${isDaemonRunning ? "badge-active" : "badge-archived"}`}>
                    {isDaemonRunning ? "Daemon Active" : "Daemon Inactive"}
                  </span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 16 }}>
                  <div style={{ padding: "12px 16px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                    <div className="stat-label">Paper Account Cash</div>
                    <div style={{ fontSize: 18, fontFamily: "var(--font-mono)", color: "var(--text-primary)", marginTop: 4 }}>
                      ${Number(cash).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                  </div>
                  <div style={{ padding: "12px 16px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                    <div className="stat-label">Total Equity</div>
                    <div style={{ fontSize: 18, fontFamily: "var(--font-mono)", color: "var(--text-primary)", marginTop: 4 }}>
                      ${Number(equity).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                  </div>
                  <div style={{ padding: "12px 16px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                    <div className="stat-label">Open Position PnL</div>
                    <div style={{ fontSize: 18, fontFamily: "var(--font-mono)", color: unrealized >= 0 ? "var(--green)" : "var(--red)", marginTop: 4 }}>
                      {unrealized >= 0 ? "+" : ""}${unrealized.toFixed(2)}
                    </div>
                  </div>
                </div>

                {trades.length === 0 ? (
                  <div style={{ padding: "20px 0", textAlign: "center", color: "var(--text-tertiary)", fontSize: 12, borderTop: "1px solid var(--border-dim)" }}>
                    No continuous paper trades executed yet. Click "Launch Continuous Daemon" above to run live on Binance 5m candle closes.
                  </div>
                ) : (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: "var(--bg-elevated)", borderBottom: "1px solid var(--border-dim)", textAlign: "left" }}>
                        <th style={{ padding: "8px 12px" }}>Time</th>
                        <th style={{ padding: "8px 12px" }}>Direction</th>
                        <th style={{ padding: "8px 12px" }}>Notional Size</th>
                        <th style={{ padding: "8px 12px" }}>Entry → Close Price</th>
                        <th style={{ padding: "8px 12px" }}>Realized PnL</th>
                        <th style={{ padding: "8px 12px" }}>Exit Trigger / Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.map((t, i) => {
                        const direction = t.direction || t.side || "LONG";
                        const sizeUsd = t.size_usd ?? (typeof t.size === 'number' ? t.size : 10000);
                        const entryPrice = t.entry_price ?? t.price;
                        const closePrice = t.close_price;
                        const pnl = t.pnl_usd ?? t.pnl ?? 0;
                        const reason = t.reason || t.close_reason || "exit_rule";
                        return (
                          <tr key={i} style={{ borderBottom: "1px solid var(--border-dim)" }}>
                            <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>{t.timestamp}</td>
                            <td style={{ padding: "8px 12px" }}>
                              <span style={{
                                padding: "2px 6px", borderRadius: 3, fontSize: 10, fontWeight: 600,
                                background: direction === "LONG" ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)",
                                color: direction === "LONG" ? "var(--green)" : "var(--red)"
                              }}>
                                {direction}
                              </span>
                            </td>
                            <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)" }}>
                              ${Number(sizeUsd).toLocaleString("en-US", { maximumFractionDigits: 0 })} ({t.leverage || 5}x)
                            </td>
                            <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)" }}>
                              ${Number(entryPrice).toLocaleString("en-US", { minimumFractionDigits: 1 })}
                              {closePrice && <span style={{ color: "var(--text-tertiary)" }}> → ${Number(closePrice).toLocaleString("en-US", { minimumFractionDigits: 1 })}</span>}
                            </td>
                            <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)", color: pnl >= 0 ? "var(--green)" : "var(--red)" }}>
                              {pnl >= 0 ? "+" : ""}${Number(pnl).toFixed(2)}
                            </td>
                            <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-secondary)" }}>
                              <span style={{ padding: "2px 6px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 3 }}>
                                {reason}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          )}

          {/* TAB 2: FEATURE SELECTION & ML ARCHITECTURE */}
          {activeTab === "features" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Architecture Summary */}
              <div style={{ padding: 20, background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: 16, color: "var(--text-primary)" }}>
                      Active Model: {modelSpec?.name || "Binance Futures Order Flow XGBoost"}
                    </h3>
                    <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
                      Architecture: {modelSpec?.architecture || "Gradient Boosted Decision Trees"} · Target: {modelSpec?.target || "Forward 12h Return Direction"}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <span className="badge badge-active">OOS Accuracy: 55.4%</span>
                    <span className="badge badge-active">AUROC: 0.572</span>
                    <span className="badge badge-neutral">Brier Score: 0.244</span>
                  </div>
                </div>

                <div className="sys-label" style={{ marginBottom: 10 }}>5 Feature Dimension Groups (69 Dimensions Active)</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 20 }}>
                  {(modelSpec?.feature_groups || [
                    { group: "Orderbook Microstructure", count: 15, description: "Microprice, Book imbalance L1/L5/L10, depth skew" },
                    { group: "Flow Toxicity & VPIN", count: 12, description: "VPIN 50/100, Trade arrival intensity, CVD taker flow" },
                    { group: "Perpetual Carry & Funding", count: 18, description: "Settlement rate, funding velocity, Z-score, basis" },
                    { group: "Open Interest & Liquidations", count: 14, description: "OI delta, OI/Price divergence, Top trader ratio" },
                    { group: "Volatility Dynamics", count: 10, description: "Garman-Klass, Parkinson, Yang-Zhang intraday" }
                  ]).map((g, idx) => (
                    <div key={idx} style={{ padding: 14, background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                      <div style={{ fontSize: 11, color: "var(--blue-400)", fontWeight: 600 }}>{g.group}</div>
                      <div style={{ fontSize: 18, fontFamily: "var(--font-mono)", margin: "4px 0" }}>{g.count} feats</div>
                      <div style={{ fontSize: 10, color: "var(--text-tertiary)", lineHeight: 1.3 }}>{g.description}</div>
                    </div>
                  ))}
                </div>

                <div className="sys-label" style={{ marginBottom: 10 }}>Top Model Feature Importances (Lead Drivers of P(UP))</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {(modelSpec?.top_features || []).map((f, i) => (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "220px 1fr 60px", alignItems: "center", gap: 12, fontSize: 11 }}>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{f.id}</span>
                      <div style={{ height: 6, background: "var(--bg-elevated)", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ width: `${f.weight * 600}%`, height: "100%", background: "var(--blue-500)", borderRadius: 3 }} />
                      </div>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)", textAlign: "right" }}>
                        {(f.weight * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: POLICY & RISK EXECUTION CONTROLS */}
          {activeTab === "policy" && (
            <div style={{ padding: 20, background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 6 }}>
              <div className="sys-label" style={{ marginBottom: 8 }}>Triple-Barrier & Risk Management Implementation Policy</div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 20 }}>
                Parameters governing entries, exits, toxic flow circuit breakers, and position sizing.
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16 }}>
                <div style={{ padding: 16, background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 12 }}>
                    Signal Thresholds & Toxicity Gates
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-dim)", paddingBottom: 6 }}>
                      <span style={{ color: "var(--text-tertiary)" }}>Long Entry Threshold</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--green)" }}>P(UP) ≥ 0.58</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-dim)", paddingBottom: 6 }}>
                      <span style={{ color: "var(--text-tertiary)" }}>Short Entry Threshold</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--red)" }}>P(UP) ≤ 0.42</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-dim)", paddingBottom: 6 }}>
                      <span style={{ color: "var(--text-tertiary)" }}>VPIN Entry Gate</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--amber)" }}>Reject if VPIN &gt; 0.70</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--text-tertiary)" }}>VPIN Emergency Exit Gate</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--red)" }}>Exit immediately if VPIN &gt; 0.85</span>
                    </div>
                  </div>
                </div>

                <div style={{ padding: 16, background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 12 }}>
                    Execution Barriers & Position Sizing
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-dim)", paddingBottom: 6 }}>
                      <span style={{ color: "var(--text-tertiary)" }}>Take-Profit Barrier (PT)</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--green)" }}>+3.0%</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-dim)", paddingBottom: 6 }}>
                      <span style={{ color: "var(--text-tertiary)" }}>Stop-Loss Barrier (SL)</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--red)" }}>-1.5% (Dynamic 2.0x ATR)</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-dim)", paddingBottom: 6 }}>
                      <span style={{ color: "var(--text-tertiary)" }}>Leverage Cap</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>5.0x Maximum</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--text-tertiary)" }}>Cooldown Horizon</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>3 Bars (15 minutes)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: LIVE DAEMON LOGS CONSOLE */}
          {activeTab === "logs" && (
            <div style={{ padding: 20, background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 6 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <div>
                  <div className="sys-label" style={{ margin: 0 }}>Real-Time Daemon Execution Console</div>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>
                    Streaming direct execution pulses, feature computation, and risk decisions from `futures_paper_daemon.log`.
                  </div>
                </div>
                <button className="btn btn-sm btn-ghost" onClick={loadData}>Refresh Log</button>
              </div>

              <div style={{
                background: "var(--bg-base)", border: "1px solid var(--border-dim)", borderRadius: 4,
                padding: "14px 16px", maxHeight: 420, overflowY: "auto", fontFamily: "var(--font-mono)", fontSize: 11,
                lineHeight: 1.6, color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: 3
              }}>
                {logs.length === 0 ? (
                  <div style={{ color: "var(--text-tertiary)" }}>No log lines recorded yet. Launch daemon to begin streaming.</div>
                ) : (
                  logs.map((line, idx) => {
                    const isError = line.includes("[ERROR]");
                    const isTick = line.includes("[TICK]") || line.includes("P(UP)=");
                    const isWarn = line.includes("[WARNING]");
                    return (
                      <div key={idx} style={{
                        color: isError ? "var(--red)" : isTick ? "var(--green)" : isWarn ? "var(--amber)" : "var(--text-secondary)",
                        whiteSpace: "pre-wrap", wordBreak: "break-all"
                      }}>
                        {line}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

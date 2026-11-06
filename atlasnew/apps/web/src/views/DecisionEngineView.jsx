import React, { useState, useCallback } from "react";
import axios from "axios";
import { API, isAbortError, fmtRelative } from "../lib/helpers";
import { SymbolSelector } from "../components/SymbolSelector";

export function DecisionEngineView() {
  const [provider, setProvider] = useState("yahoo");
  const [symbol, setSymbol] = useState("AAPL");
  const [interval, setIntervalVal] = useState("1d");
  const [period, setPeriod] = useState("2y");
  const [horizon, setHorizon] = useState(5);
  const [includeModels, setIncludeModels] = useState(true);
  const [useLearnedWeights, setUseLearnedWeights] = useState(false);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("generate"); // "generate" | "history"

  const runRecommendation = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await axios.post(`${API}/decision/recommend`, {
        provider, symbol, interval, period, horizon: parseInt(horizon, 10),
        include_models: includeModels,
        use_learned_weights: useLearnedWeights,
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail ? (typeof err.response.data.detail === 'string' ? err.response.data.detail : JSON.stringify(err.response.data.detail)) : err.message);
    } finally {
      setLoading(false);
    }
  }, [provider, symbol, interval, period, horizon, includeModels, useLearnedWeights]);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await axios.get(`${API}/decision/history`, { params: { limit: 30 } });
      setHistory(res.data || []);
    } catch (err) {
      if (!isAbortError(err)) console.error(err);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const handleTabSwitch = (tab) => {
    setActiveTab(tab);
    if (tab === "history" && history.length === 0) loadHistory();
  };

  const dirColor = (dir) => {
    if (!dir) return "var(--text-tertiary)";
    const d = String(dir).toUpperCase();
    if (d === "BUY" || d === "LONG" || d === "UP") return "var(--green)";
    if (d === "SELL" || d === "SHORT" || d === "DOWN") return "var(--red)";
    return "var(--amber)";
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div className="workspace-header" style={{ padding: "20px 28px 16px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div>
            <h2 className="workspace-title">Decision Engine</h2>
            <div className="workspace-subtitle">
              Multi-signal voting system with ensemble agreement, adaptive weights, and regime conditioning.
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className={`btn btn-sm ${activeTab === "generate" ? "btn-secondary" : "btn-ghost"}`}
              onClick={() => handleTabSwitch("generate")}
            >Generate Signal</button>
            <button
              className={`btn btn-sm ${activeTab === "history" ? "btn-secondary" : "btn-ghost"}`}
              onClick={() => handleTabSwitch("history")}
            >Signal History</button>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        {activeTab === "generate" ? (
          <div style={{ display: "flex", height: "100%" }}>
            {/* Config panel */}
            <div style={{ width: 360, flexShrink: 0, borderRight: "1px solid var(--border-dim)", padding: "24px 28px", overflow: "auto", background: "var(--bg-surface)" }}>
              <div style={{ marginBottom: 28 }}>
                <div className="sys-label" style={{ marginBottom: 14 }}>Market Context</div>
                <SymbolSelector
                  provider={provider} symbol={symbol}
                  onProviderChange={setProvider} onSymbolChange={setSymbol}
                  style={{ flexDirection: "column" }}
                />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 }}>
                  <div className="input-group">
                    <label className="input-label">Interval</label>
                    <select className="input" value={interval} onChange={e => setIntervalVal(e.target.value)}>
                      {["5m", "15m", "1h", "4h", "1d"].map(i => <option key={i} value={i}>{i}</option>)}
                    </select>
                  </div>
                  <div className="input-group">
                    <label className="input-label">Period</label>
                    <select className="input" value={period} onChange={e => setPeriod(e.target.value)}>
                      {["6mo", "1y", "2y", "3y", "5y"].map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </div>
                </div>
              </div>

              <div style={{ marginBottom: 28 }}>
                <div className="sys-label" style={{ marginBottom: 14 }}>Signal Configuration</div>
                <div className="input-group">
                  <label className="input-label">Prediction Horizon (bars)</label>
                  <input type="number" className="input" value={horizon} onChange={e => setHorizon(e.target.value)} min={1} max={60} />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 14 }}>
                  <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 8, cursor: "pointer", color: "var(--text-secondary)" }}>
                    <input type="checkbox" checked={includeModels} onChange={e => setIncludeModels(e.target.checked)} style={{ accentColor: "var(--blue-500)" }} />
                    Include ML Ensemble Agreement
                  </label>
                  <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 8, cursor: "pointer", color: "var(--text-secondary)" }}>
                    <input type="checkbox" checked={useLearnedWeights} onChange={e => setUseLearnedWeights(e.target.checked)} style={{ accentColor: "var(--blue-500)" }} />
                    Use Adaptive Learned Weights
                  </label>
                </div>
              </div>

              <button
                className="btn btn-primary"
                style={{ width: "100%", justifyContent: "center", padding: "12px 0", fontSize: 13 }}
                onClick={runRecommendation}
                disabled={loading}
              >
                {loading ? "Computing Signal…" : "Generate Recommendation"}
              </button>

              {loading && (
                <div style={{ marginTop: 12, padding: "10px 14px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 6 }}>
                  <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", marginBottom: 4 }}>Estimated time:</div>
                  <div style={{ fontSize: 12, color: "var(--amber)" }}>
                    {includeModels ? "60–90 seconds (ML training active)" : "~3 seconds (rules only)"}
                  </div>
                </div>
              )}

              {error && (
                <div style={{ marginTop: 16, padding: "12px 16px", background: "var(--red-muted)", border: "1px solid var(--red-border)", borderRadius: 6, fontSize: 12, color: "var(--red)" }}>
                  {error}
                </div>
              )}
            </div>

            {/* Results panel */}
            <div style={{ flex: 1, padding: "32px 40px", overflow: "auto", background: "var(--bg-base)" }}>
              {!result && !loading && (
                <div className="page-empty">
                  <div className="page-empty-desc">Configure parameters and generate a recommendation signal.</div>
                </div>
              )}

              {loading && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <div style={{ padding: "16px", background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 6 }}>
                    <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", marginBottom: 8 }}>RUNNING DECISION ENGINE</div>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                      {includeModels
                        ? "Fetching market data · Computing 925+ features · Training ML ensemble (XGBoost + RandomForest) · Running voting system…"
                        : "Fetching market data · Computing signals · Running voting system…"}
                    </div>
                    <div style={{ marginTop: 12, height: 2, borderRadius: 1, background: "var(--border-dim)", overflow: "hidden", position: "relative" }}>
                      <div style={{ position: "absolute", left: 0, top: 0, height: "100%", width: "40%", background: "var(--blue-400)", animation: "shimmer 1.5s ease-in-out infinite" }} />
                    </div>
                  </div>
                  <div className="skeleton" style={{ height: 200, borderRadius: 6 }} />
                  <div className="skeleton" style={{ height: 160, borderRadius: 6 }} />
                </div>
              )}

              {result && (
                <div style={{ maxWidth: 860, margin: "0 auto" }}>
                  {/* Primary signal */}
                  <div style={{
                    padding: "28px 32px", marginBottom: 24,
                    background: "var(--bg-surface)", border: "1px solid var(--border-dim)",
                    borderRadius: 8, position: "relative",
                  }}>
                    <div style={{ position: "absolute", top: 0, left: 0, width: 10, height: 10, borderTop: "2px solid var(--border-accent)", borderLeft: "2px solid var(--border-accent)" }} />
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
                      <div>
                        <div className="sys-label" style={{ marginBottom: 6 }}>Final Recommendation</div>
                        <div style={{ fontSize: 32, fontWeight: 300, color: dirColor(result.decision || result.direction), fontFamily: "var(--font-mono)", letterSpacing: "-0.02em" }}>
                          {result.decision || result.direction || "HOLD"}
                        </div>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <div className="stat-label">Confidence</div>
                        <div style={{ fontSize: 24, fontWeight: 300, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                          {result.confidence != null ? (result.confidence * 100).toFixed(1) + "%" : "—"}
                        </div>
                      </div>
                    </div>

                    {/* Confidence bar */}
                    <div style={{ height: 4, borderRadius: 2, background: "var(--border-dim)", overflow: "hidden" }}>
                      <div style={{
                        width: `${(result.confidence || 0) * 100}%`, height: "100%",
                        background: dirColor(result.decision || result.direction),
                        transition: "width 300ms ease-out",
                      }} />
                    </div>

                    {result.symbol && (
                      <div style={{ marginTop: 12, fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
                        {result.symbol} · {result.provider} · Horizon: {horizon} bars
                      </div>
                    )}
                  </div>

                  {/* Signal Breakdown */}
                  {result.signals && Object.keys(result.signals).length > 0 && (
                    <div style={{ marginBottom: 24 }}>
                      <div className="sys-label" style={{ marginBottom: 12 }}>Individual Signal Votes</div>
                      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden" }}>
                        <table className="atlas-table">
                          <thead>
                            <tr>
                              <th>Signal</th>
                              <th>Vote</th>
                              <th>Score</th>
                              <th>Weight</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(Array.isArray(result.signals) ? result.signals : Object.values(result.signals)).map((sig, i) => { const name = sig.name || "Signal " + i; return (
                              <tr key={name}>
                                <td style={{ fontWeight: 500 }}>{name}</td>
                                <td>
                                  <span style={{
                                    color: dirColor(sig.vote || sig.direction),
                                    fontFamily: "var(--font-mono)", fontSize: 11,
                                  }}>
                                    {String(sig.vote || sig.direction || "-").toUpperCase()}
                                  </span>
                                </td>
                                <td className="mono-value">{sig.score != null ? sig.score.toFixed(3) : "—"}</td>
                                <td className="mono-value" style={{ color: "var(--text-tertiary)" }}>
                                  {sig.weight != null ? sig.weight.toFixed(3) : "—"}
                                </td>
                              </tr>
                            );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Ensemble Agreement */}
                  {result.model_agreement && !result.model_agreement.error && (
                    <div style={{ marginBottom: 24 }}>
                      <div className="sys-label" style={{ marginBottom: 12 }}>ML Ensemble Agreement</div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 1, border: "1px solid var(--border-dim)", borderRadius: 6, overflow: "hidden" }}>
                        {[
                          { label: "Consensus Direction", value: result.model_agreement.consensus || result.model_agreement.direction || "—", color: dirColor(result.model_agreement.consensus || result.model_agreement.direction) },
                          { label: "Agreement Score", value: result.model_agreement.agreement_score != null ? (result.model_agreement.agreement_score * 100).toFixed(1) + "%" : "—" },
                          { label: "Models Used", value: result.model_agreement.n_models || result.model_agreement.model_count || "—" },
                        ].map((s, i) => (
                          <div key={i} style={{ padding: "16px 20px", background: "var(--bg-elevated)", borderRight: i < 2 ? "1px solid var(--border-dim)" : "none" }}>
                            <div className="stat-label">{s.label}</div>
                            <div className="stat-value" style={{ fontSize: 15, marginTop: 4, color: s.color || "var(--text-primary)" }}>{s.value}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Regime context */}
                  {result.regime && (
                    <div style={{ marginBottom: 24 }}>
                      <div className="sys-label" style={{ marginBottom: 12 }}>Detected Market Regime</div>
                      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                        {Object.entries(result.regime).map(([key, val]) => (
                          <div key={key} style={{ padding: "10px 16px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 6 }}>
                            <div className="mono-label" style={{ marginBottom: 4 }}>{key}</div>
                            <div className="mono-value">{typeof val === "number" ? val.toFixed(3) : String(val)}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Disclaimer */}
                  <div style={{
                    padding: "12px 16px", background: "var(--bg-elevated)",
                    border: "1px solid var(--border-dim)", borderRadius: 4,
                    fontSize: 11, color: "var(--text-tertiary)", lineHeight: 1.5,
                    textAlign: "center", fontStyle: "italic",
                  }}>
                    Decision Engine signals are research tools. They do not constitute financial advice. Past signal accuracy does not predict future performance.
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* History Tab */
          <div style={{ padding: "24px 28px", maxWidth: 1100, margin: "0 auto" }}>
            {historyLoading ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[1,2,3,4,5].map(i => <div key={i} className="skeleton" style={{ height: 52 }} />)}
              </div>
            ) : history.length === 0 ? (
              <div className="page-empty" style={{ paddingTop: 60 }}>
                <div className="page-empty-title">No Signal History</div>
                <div className="page-empty-desc">Generate recommendations to build a history of signals.</div>
              </div>
            ) : (
              <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden" }}>
                <table className="atlas-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Direction</th>
                      <th>Confidence</th>
                      <th>Provider</th>
                      <th>Horizon</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((h, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 500 }}>{h.symbol || "—"}</td>
                        <td>
                          <span style={{ color: dirColor(h.direction), fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600 }}>
                            {String(h.direction || h.decision || "-").toUpperCase()}
                          </span>
                        </td>
                        <td className="mono-value">{h.confidence != null ? (h.confidence * 100).toFixed(1) + "%" : "—"}</td>
                        <td className="mono-value" style={{ color: "var(--text-tertiary)" }}>{h.provider || "—"}</td>
                        <td className="mono-value">{h.horizon || "—"}</td>
                        <td style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
                          {fmtRelative(h.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

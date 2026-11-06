import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API, fmtRelative, makeAbortable, isAbortError, INTERVALS } from "../../lib/helpers";
import { SymbolSelector } from "../../components/SymbolSelector";

export function ProjectBacktests({ project }) {
  const [activeTab, setActiveTab] = useState(() => {
    return sessionStorage.getItem("atlas_prefill_model_id") ? "new" : "list";
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div style={{ padding: "16px 28px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div className="sys-label" style={{ marginBottom: 4 }}>Module</div>
          <div style={{ fontSize: 16, color: "var(--text-primary)" }}>Backtesting Workspace</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className={`btn btn-sm ${activeTab === "list" ? "btn-secondary" : "btn-ghost"}`} onClick={() => setActiveTab("list")}>
            Run History
          </button>
          <button className={`btn btn-sm ${activeTab === "new" ? "btn-secondary" : "btn-ghost"}`} onClick={() => setActiveTab("new")}>
            + New Backtest
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "hidden" }}>
        {activeTab === "list" ? <BacktestList /> : <NewBacktestForm project={project} onSuccess={() => setActiveTab("list")} />}
      </div>
    </div>
  );
}

function BacktestList() {
  const [backtests, setBacktests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  const fetchDetail = async (bt) => {
    setSelected(bt); // Optimistic UI update
    try {
      const res = await axios.get(`${API}/learning/backtest/${bt.backtest_id}`);
      setSelected(res.data);
    } catch (err) {
      console.error("Failed to fetch backtest detail", err);
    }
  };

  const load = useCallback(async (signal) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/learning/backtest/list`, { signal });
      setBacktests(res.data || []);
      if (res.data?.length > 0) {
        fetchDetail(res.data[0]);
      }
    } catch (err) {
      if (!isAbortError(err)) console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const { signal, abort } = makeAbortable();
    load(signal);
    return () => abort();
  }, [load]);

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this backtest run?")) return;
    try {
      await axios.delete(`${API}/learning/backtest/${id}`);
      setSelected(null);
      load();
    } catch (err) {
      console.error("Failed to delete backtest", err);
    }
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Sidebar List */}
      <div style={{ width: 340, flexShrink: 0, borderRight: "1px solid var(--border-dim)", overflow: "auto", background: "var(--bg-surface)" }}>
        {loading ? (
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
            {[1,2,3,4].map(i => <div key={i} className="skeleton" style={{ height: 60 }} />)}
          </div>
        ) : backtests.length === 0 ? (
          <div className="page-empty" style={{ paddingTop: 60 }}>
            <div className="page-empty-title">No Backtests Found</div>
            <div className="page-empty-desc">Run a simulation to view results here.</div>
          </div>
        ) : (
          backtests.map(bt => (
            <div
              key={bt.backtest_id}
              onClick={() => fetchDetail(bt)}
              style={{
                padding: "14px 18px",
                borderBottom: "1px solid var(--border-dim)",
                cursor: "pointer",
                background: selected?.backtest_id === bt.backtest_id ? "var(--bg-hover)" : "transparent",
                borderLeft: selected?.backtest_id === bt.backtest_id ? "2px solid var(--blue-500)" : "2px solid transparent",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 13, color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                  {bt.backtest_id.split("-")[0]}
                </span>
                <span className="badge badge-active">{bt.spec?.symbol || "UNKNOWN"}</span>
              </div>
              <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 }}>
                Model: {bt.spec?.model_id?.split("-")[0] || "None"}
              </div>
              <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
                {fmtRelative(bt.created_at)}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Main Detail Panel */}
      <div style={{ flex: 1, padding: "32px 40px", overflow: "auto", background: "var(--bg-base)" }}>
        {!selected ? (
          <div className="page-empty"><div className="page-empty-desc">Select a backtest to view results.</div></div>
        ) : (
          <div style={{ maxWidth: 860, margin: "0 auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
              <div>
                <h3 style={{ fontSize: 20, fontWeight: 300, color: "var(--text-primary)", fontFamily: "var(--font-mono)", marginBottom: 4 }}>
                  {selected.backtest_id}
                </h3>
                <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                  Run on {new Date(selected.created_at).toLocaleString()}
                </div>
              </div>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <button className="btn btn-sm btn-ghost" style={{ color: "var(--red)" }} onClick={() => handleDelete(selected.backtest_id)}>
                  Delete Run
                </button>
                <div className="badge badge-active">{selected.spec?.symbol}</div>
              </div>
            </div>

            {/* Metrics */}
            <div style={{ marginBottom: 32 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>Performance Summary</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", border: "1px solid var(--border-dim)", borderRadius: 4, overflow: "hidden", position: "relative" }}>
                <div style={{ position: "absolute", top: 0, left: 0, width: 8, height: 8, borderTop: "1px solid var(--border-accent)", borderLeft: "1px solid var(--border-accent)", pointerEvents: "none" }} />
                {[
                  { label: "Total Return", value: selected.metrics?.total_return_pct != null ? `${selected.metrics.total_return_pct.toFixed(2)}%` : "—", color: selected.metrics?.total_return_pct >= 0 ? "var(--green)" : "var(--red)" },
                  { label: "Sharpe Ratio", value: selected.metrics?.sharpe != null ? selected.metrics.sharpe.toFixed(2) : "—" },
                  { label: "Max Drawdown", value: selected.metrics?.max_drawdown_pct != null ? `${selected.metrics.max_drawdown_pct.toFixed(2)}%` : "—", color: "var(--red)" },
                  { label: "Win Rate", value: selected.metrics?.hit_rate != null ? `${(selected.metrics.hit_rate * 100).toFixed(1)}%` : "—" },
                ].map((s, i) => (
                  <div key={i} style={{ padding: "16px 20px", background: "var(--bg-elevated)", borderRight: i < 3 ? "1px solid var(--border-dim)" : "none" }}>
                    <div className="stat-label">{s.label}</div>
                    <div className="stat-value" style={{ fontSize: 16, marginTop: 4, color: s.color || "var(--text-primary)" }}>{s.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Config & Assumptions */}
            <div style={{ marginBottom: 32 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>Execution Assumptions</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, border: "1px solid var(--border-dim)", borderRadius: 4, overflow: "hidden" }}>
                {[
                  { label: "Model Ref", value: selected.spec?.model_id },
                  { label: "Initial Cash", value: `$${selected.spec?.initial_cash?.toLocaleString()}` },
                  { label: "Fees (bps)", value: selected.spec?.fee_bps },
                  { label: "Slippage (bps)", value: selected.spec?.slippage_bps },
                  { label: "Position Size", value: `${selected.spec?.policy?.position_size_pct}%` },
                  { label: "Max Leverage", value: `${selected.spec?.policy?.max_leverage}x` },
                  { label: "Thresholds", value: `Up: ${selected.spec?.policy?.upper_threshold} / Dn: ${selected.spec?.policy?.lower_threshold}` },
                  { label: "Allow Short", value: selected.spec?.policy?.allow_short ? "Yes" : "No" },
                ].map((row, i) => (
                  <div key={i} style={{ padding: "12px 16px", background: "var(--bg-elevated)", borderRight: i % 2 === 0 ? "1px solid var(--border-dim)" : "none", borderBottom: i < 6 ? "1px solid var(--border-dim)" : "none" }}>
                    <div className="mono-label" style={{ marginBottom: 4 }}>{row.label}</div>
                    <div className="mono-value">{row.value || "—"}</div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Disclaimer */}
            <div style={{ padding: "12px 16px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4, fontSize: 11, color: "var(--text-tertiary)", lineHeight: 1.5, textAlign: "center", fontStyle: "italic", marginBottom: 32 }}>
              Historical backtest results do not predict future performance. Results are sensitive to assumptions. Examine assumptions before drawing conclusions.
            </div>

            {/* Trade Ledger */}
            {(() => {
              const trades = selected.trades || selected.ledger || selected.metrics?.trades || [];
              if (!trades.length) return null;
              return (
                <div style={{ marginBottom: 32 }}>
                  <div className="sys-label" style={{ marginBottom: 12 }}>Trade Ledger</div>
                  <div style={{ border: "1px solid var(--border-dim)", borderRadius: 4, overflow: "auto", maxHeight: 400 }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                      <thead style={{ background: "var(--bg-elevated)", position: "sticky", top: 0 }}>
                        <tr>
                          <th style={{ padding: "8px 12px", textAlign: "left", borderBottom: "1px solid var(--border-dim)", color: "var(--text-secondary)", fontWeight: 400 }}>Time</th>
                          <th style={{ padding: "8px 12px", textAlign: "left", borderBottom: "1px solid var(--border-dim)", color: "var(--text-secondary)", fontWeight: 400 }}>Action</th>
                          <th style={{ padding: "8px 12px", textAlign: "right", borderBottom: "1px solid var(--border-dim)", color: "var(--text-secondary)", fontWeight: 400 }}>Price</th>
                          <th style={{ padding: "8px 12px", textAlign: "right", borderBottom: "1px solid var(--border-dim)", color: "var(--text-secondary)", fontWeight: 400 }}>PnL</th>
                        </tr>
                      </thead>
                      <tbody>
                        {trades.map((t, i) => (
                          <tr key={i} style={{ borderBottom: "1px solid var(--border-dim)" }}>
                            <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)" }}>
                              {new Date(t.open_time || t.timestamp || t.time || t.date).toLocaleString()}
                            </td>
                            <td style={{ padding: "8px 12px", color: t.direction === 1 || (t.action || "").toUpperCase().includes("LONG") || (t.action || "").toUpperCase().includes("BUY") ? "var(--green)" : "var(--red)" }}>
                              {t.direction === 1 ? "LONG" : t.direction === -1 ? "SHORT" : (t.action || t.side || "TRADE").toUpperCase()}
                            </td>
                            <td style={{ padding: "8px 12px", textAlign: "right", fontFamily: "var(--font-mono)" }}>
                              {t.open_price != null ? `$${parseFloat(t.open_price).toFixed(2)}` : (t.price != null ? `$${parseFloat(t.price).toFixed(2)}` : "—")}
                            </td>
                            <td style={{ padding: "8px 12px", textAlign: "right", fontFamily: "var(--font-mono)", color: t.pnl > 0 ? "var(--green)" : t.pnl < 0 ? "var(--red)" : "inherit" }}>
                              {t.pnl != null ? (t.pnl > 0 ? `+$${parseFloat(t.pnl).toFixed(2)}` : `-$${Math.abs(parseFloat(t.pnl)).toFixed(2)}`) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
}

function NewBacktestForm({ project, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [models, setModels] = useState([]);
  
  const [form, setForm] = useState({
    model_id: "",
    provider: "binance",
    symbol: "BTCUSDT",
    interval: "1d",
    period: "2y",
    initial_cash: 100000,
    fee_bps: 5.0,
    slippage_bps: 5.0,
    position_size_pct: 30.0,
    max_leverage: 1.0,
    allow_short: true
  });

  useEffect(() => {
    const { signal, abort } = makeAbortable();
    const prefillId = sessionStorage.getItem("atlas_prefill_model_id");
    
    axios.get(`${API}/learning/models`, { signal })
      .then(res => {
        setModels(res.data || []);
        if (prefillId) {
          setForm(f => ({ ...f, model_id: prefillId }));
          sessionStorage.removeItem("atlas_prefill_model_id");
        } else if (res.data?.length > 0 && !form.model_id) {
          setForm(f => ({ ...f, model_id: res.data[0].model_id }));
        }
      })
      .catch(err => { if (!isAbortError(err)) console.error(err); });
    return () => abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async () => {
    if (!form.model_id) { setError("Please select a model."); return; }
    setLoading(true);
    setError(null);
    try {
      const payload = {
        model_id: form.model_id,
        provider: form.provider,
        symbol: form.symbol,
        interval: form.interval,
        period: form.period,
        tags: project?._id ? [project._id] : [],
        initial_cash: parseFloat(form.initial_cash),
        fee_bps: parseFloat(form.fee_bps),
        slippage_bps: parseFloat(form.slippage_bps),
        position_size_pct: parseFloat(form.position_size_pct),
        max_leverage: parseFloat(form.max_leverage),
        allow_short: form.allow_short,
        upper_threshold: 0.51,
        lower_threshold: 0.49,
        regime_gate: false
      };
      await axios.post(`${API}/learning/backtest/run`, payload);
      onSuccess(); // Switch to list view
    } catch (err) {
      let msg;
      if (err.response?.data?.detail) {
        // Server returned a structured error — show it directly
        const detail = err.response.data.detail;
        msg = typeof detail === 'string' ? detail : JSON.stringify(detail);
      } else if (err.response) {
        // Server responded but without a detail field
        msg = `Server error ${err.response.status}: ${err.response.statusText || "Unknown error"}`;
      } else if (err.request) {
        // Request was sent but no response received (network error / server down)
        msg = "Network Error — could not reach the server. Check that the API is running and try again.";
      } else {
        msg = err.message || "Backtest failed to run.";
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ height: "100%", overflow: "auto", paddingBottom: "40px" }}>
      <div style={{ maxWidth: 600, margin: "40px auto", padding: "0 20px" }}>
        <h3 style={{ fontSize: 20, fontWeight: 300, color: "var(--text-primary)", marginBottom: 24 }}>Configure Backtest</h3>
      
      {error && (
        <div style={{ marginBottom: 24, padding: "12px 16px", background: "var(--red-muted)", border: "1px solid rgba(220,64,75,0.2)", borderRadius: 4, fontSize: 12.5, color: "var(--red)" }}>
          {error}
        </div>
      )}

      <div style={{ marginBottom: 32 }}>
        <div className="sys-label" style={{ marginBottom: 12 }}>1. Strategy Source</div>
        <div className="input-group">
          <label className="input-label">Model (Registered Run)</label>
          <select className="input" value={form.model_id} onChange={e => setForm({...form, model_id: e.target.value})}>
            <option value="">Select a model...</option>
            {models.map(m => <option key={m.model_id} value={m.model_id}>{m.model_id} ({m.kind})</option>)}
          </select>
        </div>
      </div>

      <div style={{ marginBottom: 32 }}>
        <div className="sys-label" style={{ marginBottom: 12 }}>2. Universe & Timeframe</div>
        <SymbolSelector
          provider={form.provider}
          symbol={form.symbol}
          onProviderChange={v => setForm(prev => ({ ...prev, provider: v }))}
          onSymbolChange={v => setForm(prev => ({ ...prev, symbol: v }))}
          style={{ marginBottom: 12 }}
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div className="input-group">
            <label className="input-label">Interval</label>
            <select className="input" value={form.interval} onChange={e => setForm({...form, interval: e.target.value})}>
              {INTERVALS.map(i => <option key={i} value={i}>{i}</option>)}
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">Period</label>
            <input className="input" value={form.period} onChange={e => setForm({...form, period: e.target.value})} />
          </div>
        </div>
      </div>

      <div style={{ marginBottom: 32 }}>
        <div className="sys-label" style={{ marginBottom: 12 }}>3. Execution Assumptions</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div className="input-group">
            <label className="input-label">Initial Cash ($)</label>
            <input type="number" className="input" value={form.initial_cash} onChange={e => setForm({...form, initial_cash: e.target.value})} />
          </div>
          <div className="input-group">
            <label className="input-label">Position Size (%)</label>
            <input type="number" className="input" value={form.position_size_pct} onChange={e => setForm({...form, position_size_pct: e.target.value})} />
          </div>
          <div className="input-group">
            <label className="input-label">Fee (bps)</label>
            <input type="number" className="input" value={form.fee_bps} onChange={e => setForm({...form, fee_bps: e.target.value})} />
          </div>
          <div className="input-group">
            <label className="input-label">Slippage (bps)</label>
            <input type="number" className="input" value={form.slippage_bps} onChange={e => setForm({...form, slippage_bps: e.target.value})} />
          </div>
          <div className="input-group">
            <label className="input-label">Max Leverage</label>
            <input type="number" step="0.1" className="input" value={form.max_leverage} onChange={e => setForm({...form, max_leverage: e.target.value})} />
          </div>
          <div className="input-group" style={{ display: "flex", alignItems: "center", paddingTop: 20 }}>
            <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 8, cursor: "pointer", color: "var(--text-secondary)" }}>
              <input type="checkbox" checked={form.allow_short} onChange={e => setForm({...form, allow_short: e.target.checked})} />
              Allow Short Selling
            </label>
          </div>
        </div>
      </div>

      <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={handleSubmit} disabled={loading}>
        {loading ? "Simulating Strategy..." : "Run Immutable Backtest"}
      </button>
      </div>
    </div>
  );
}


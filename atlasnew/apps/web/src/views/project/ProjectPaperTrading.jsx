import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API, fmtRelative, makeAbortable, isAbortError } from "../../lib/helpers";
import { SymbolSelector } from "../../components/SymbolSelector";

export function ProjectPaperTrading({ project }) {
  const [data, setData] = useState({
    account: null,
    metrics: null,
    equity: 0,
    unrealized_pnl: 0,
    open_positions: [],
    trades: []
  });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(() => {
    return sessionStorage.getItem("atlas_prefill_model_id") ? "deploy" : "manual";
  });

  const loadAll = useCallback(async (signal) => {
    try {
      setLoading(true);
      const [analyticsRes, posRes, tradesRes] = await Promise.all([
        axios.get(`${API}/paper-trading/analytics`, { signal }),
        axios.get(`${API}/paper-trading/positions/open`, { signal }),
        axios.get(`${API}/paper-trading/trades`, { signal, params: { limit: 10 } })
      ]);
      setData({
        ...analyticsRes.data,
        open_positions: posRes.data || [],
        trades: tradesRes.data || []
      });
    } catch (err) {
      if (!isAbortError(err)) console.error("Paper trading load failed", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const { signal, abort } = makeAbortable();
    loadAll(signal);
    return () => abort();
  }, [loadAll]);

  const handleMarkToMarket = async () => {
    try {
      await axios.post(`${API}/paper-trading/positions/mark`, { auto_close_on_tp_sl: true });
      loadAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      alert(detail ? (typeof detail === 'string' ? detail : JSON.stringify(detail)) : "Failed to mark positions to market");
    }
  };

  const handleReset = async () => {
    if (!window.confirm("Reset the paper trading account? This clears all positions and trade history.")) return;
    try {
      await axios.post(`${API}/paper-trading/account/reset`, { starting_balance: 100000 });
      loadAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      alert(detail ? (typeof detail === 'string' ? detail : JSON.stringify(detail)) : "Reset failed");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "14px 28px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div className="sys-label" style={{ marginBottom: 4 }}>Module</div>
          <div style={{ fontSize: 15, color: "var(--text-primary)", fontWeight: 500 }}>Paper Trading Simulator</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-sm btn-ghost" onClick={handleReset}>Reset Account</button>
          <button className="btn btn-sm btn-secondary" onClick={handleMarkToMarket}>Force MTM Sync</button>
          <button className="btn btn-sm btn-primary" onClick={() => loadAll()}>Refresh</button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "24px 28px" }}>
        <div style={{ maxWidth: 1160, margin: "0 auto", display: "flex", flexDirection: "column", gap: 28 }}>

          {/* Account Summary */}
          <AccountSummary data={data} loading={loading} />

          {/* Order Entry — Tab: Manual | Deploy Model */}
          <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden" }}>
            <div style={{ display: "flex", borderBottom: "1px solid var(--border-dim)" }}>
              {["manual", "deploy"].map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    padding: "10px 20px",
                    fontSize: 12, fontWeight: 500,
                    background: activeTab === tab ? "var(--bg-elevated)" : "transparent",
                    color: activeTab === tab ? "var(--text-primary)" : "var(--text-tertiary)",
                    borderRight: "1px solid var(--border-dim)",
                    borderBottom: activeTab === tab ? "2px solid var(--blue-500)" : "none",
                    cursor: "pointer",
                    letterSpacing: "0.05em", textTransform: "uppercase",
                  }}
                >
                  {tab === "manual" ? "Manual Order Entry" : "Deploy Trained Model"}
                </button>
              ))}
            </div>
            <div style={{ padding: 20 }}>
              {activeTab === "manual"
                ? <QuickEntryForm onSuccess={loadAll} />
                : <ModelDeployPanel onSuccess={loadAll} />
              }
            </div>
          </div>

          {/* Positions + Trades */}
          <div style={{ display: "flex", gap: 24 }}>
            <div style={{ flex: 1 }}>
              <OpenPositions positions={data.open_positions} loading={loading} onRefresh={loadAll} />
            </div>
            <div style={{ flex: 1 }}>
              <TradeHistory trades={data.trades} loading={loading} />
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

/* ─── Account Summary ─────────────────────────────────────────────── */
function AccountSummary({ data, loading }) {
  if (loading && !data.account) return <div className="skeleton" style={{ height: 140 }} />;
  const fmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
  const starting = data.account?.starting_balance || 100000;
  const equity = data.equity || starting;
  const pnlPct = ((equity - starting) / starting) * 100;

  return (
    <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, padding: "20px 24px" }}>
      <div className="sys-label" style={{ marginBottom: 12 }}>Live Equity Snapshot</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 20 }}>
        <span style={{ fontSize: 34, fontWeight: 300, color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
          {fmt.format(equity)}
        </span>
        <span style={{ fontSize: 15, color: pnlPct >= 0 ? "var(--green)" : "var(--red)", fontFamily: "var(--font-mono)" }}>
          {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
        </span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <StatBox label="Unrealized PnL" value={fmt.format(data.unrealized_pnl || 0)} color={(data.unrealized_pnl || 0) >= 0 ? "var(--green)" : "var(--red)"} />
        <StatBox label="Sharpe Ratio" value={data.metrics?.sharpe_ratio != null ? data.metrics.sharpe_ratio.toFixed(2) : "—"} />
        <StatBox label="Win Rate" value={data.metrics?.win_rate ? `${(data.metrics.win_rate * 100).toFixed(1)}%` : "—"} />
        <StatBox label="Trades Closed" value={data.closed_trade_count ?? 0} />
      </div>
    </div>
  );
}

function StatBox({ label, value, color }) {
  return (
    <div style={{ padding: "10px 14px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
      <div className="stat-label" style={{ marginBottom: 4, fontSize: 10 }}>{label}</div>
      <div style={{ fontSize: 14, fontFamily: "var(--font-mono)", color: color || "var(--text-primary)" }}>{value}</div>
    </div>
  );
}

/* ─── Manual Entry Form ───────────────────────────────────────────── */
function QuickEntryForm({ onSuccess }) {
  const [form, setForm] = useState({
    side: "long", symbol: "BTCUSDT", provider: "binance", interval: "1d",
    size_pct: 10, stop_loss_pct: 0, take_profit_pct: 0, note: ""
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const submit = async () => {
    setLoading(true); setError(null);
    try {
      await axios.post(`${API}/paper-trading/positions/open`, {
        side: form.side, symbol: form.symbol, provider: form.provider,
        interval: form.interval, size_pct: form.size_pct, note: form.note,
      });
      onSuccess();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail ? (typeof detail === 'string' ? detail : JSON.stringify(detail)) : "Order failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
      <div>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          {["long", "short"].map(s => (
            <button key={s}
              className={`btn flex-1 ${form.side === s ? "btn-primary" : "btn-ghost"}`}
              style={form.side === s && s === "short" ? { background: "var(--red)", borderColor: "var(--red)" } : {}}
              onClick={() => setForm({ ...form, side: s })}
            >
              {s === "long" ? "Buy (Long)" : "Sell (Short)"}
            </button>
          ))}
        </div>

        <SymbolSelector
          provider={form.provider}
          symbol={form.symbol}
          onProviderChange={v => setForm(prev => ({ ...prev, provider: v }))}
          onSymbolChange={v => setForm(prev => ({ ...prev, symbol: v }))}
          style={{ marginBottom: 10, flexDirection: "column" }}
        />

        <div className="input-group">
          <label className="input-label">Interval</label>
          <select className="input" value={form.interval} onChange={e => setForm({ ...form, interval: e.target.value })}>
            {["5m", "15m", "1h", "4h", "1d"].map(i => <option key={i} value={i}>{i}</option>)}
          </select>
        </div>
      </div>

      <div>
        <div className="input-group" style={{ marginBottom: 10 }}>
          <label className="input-label">Position Size (%)</label>
          <input type="number" className="input" min="0.1" max="100" step="0.5"
            value={form.size_pct} onChange={e => setForm({ ...form, size_pct: parseFloat(e.target.value) })} />
        </div>
        <div className="input-group" style={{ marginBottom: 10 }}>
          <label className="input-label">Note (optional)</label>
          <input type="text" className="input" placeholder="e.g. momentum setup"
            value={form.note} onChange={e => setForm({ ...form, note: e.target.value })} />
        </div>
        {error && <div style={{ fontSize: 11, color: "var(--red)", marginBottom: 8, padding: "6px 10px", background: "rgba(220,64,75,0.1)", borderRadius: 4 }}>{error}</div>}
        <button className="btn btn-secondary" style={{ width: "100%", justifyContent: "center", marginTop: 4 }}
          onClick={submit} disabled={loading}>
          {loading ? "Routing…" : "Submit Market Order"}
        </button>
      </div>
    </div>
  );
}

/* ─── Model Deploy Panel ──────────────────────────────────────────── */
function ModelDeployPanel({ onSuccess }) {
  const [models, setModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(true);
  const [selectedModel, setSelectedModel] = useState(null);
  const [form, setForm] = useState({
    symbol: "SYN-EQUITY", provider: "synthetic", interval: "1d",
    size_pct: 10, stop_loss_pct: 0, take_profit_pct: 0,
    upper_threshold: 0.51, lower_threshold: 0.49, note: ""
  });
  const [signal, setSignal] = useState(null);
  const [deploying, setDeploying] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    const prefillId = sessionStorage.getItem("atlas_prefill_model_id");
    axios.get(`${API}/learning/models`).then(r => {
      const data = r.data || [];
      setModels(data);
      if (prefillId) {
        const m = data.find(x => x.model_id === prefillId);
        if (m) setSelectedModel(m);
        else if (data.length) setSelectedModel(data[0]);
        sessionStorage.removeItem("atlas_prefill_model_id");
      } else if (data.length) {
        setSelectedModel(data[0]);
      }
    }).catch(() => {}).finally(() => setLoadingModels(false));
  }, []);

  const getSignal = async () => {
    if (!selectedModel) return;
    setChecking(true); setSignal(null); setError(null); setSuccess(null);
    const payload = {
      model_id: selectedModel.model_id,
      symbol: form.symbol, provider: form.provider,
      interval: form.interval, period: "2y",
      size_pct: 0.1, // Minimum allowed size to avoid Pydantic validation error
      upper_threshold: form.upper_threshold,
      lower_threshold: form.lower_threshold,
      preview_only: true,
      note: "__signal_preview__",
    };
    try {
      const res = await axios.post(`${API}/paper-trading/model-deploy`, payload);
      setSignal(res.data.inference);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail ? (typeof detail === 'string' ? detail : JSON.stringify(detail)) : "Inference failed");
    } finally {
      setChecking(false);
      if (onSuccess) onSuccess();
    }
  };

  const deploy = async () => {
    if (!selectedModel) return;
    setDeploying(true); setError(null); setSuccess(null);
    try {
      const res = await axios.post(`${API}/paper-trading/model-deploy`, {
        model_id: selectedModel.model_id,
        symbol: form.symbol, provider: form.provider,
        interval: form.interval, period: "2y",
        size_pct: form.size_pct,
        stop_loss_pct: form.stop_loss_pct,
        take_profit_pct: form.take_profit_pct,
        upper_threshold: form.upper_threshold,
        lower_threshold: form.lower_threshold,
        note: form.note || `Model deploy: ${selectedModel.model_id}`,
      });
      if (res.data.position_opened) {
        setSuccess(`Position opened: ${res.data.inference?.signal?.toUpperCase()} (p=${res.data.inference?.prob_up?.toFixed(3)})`);
        onSuccess();
      } else {
        setError(`No position: ${res.data.reason || "Signal is FLAT"}`);
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail ? (typeof detail === 'string' ? detail : JSON.stringify(detail)) : "Deploy failed");
    } finally {
      setDeploying(false);
    }
  };

  const fmtAcc = (m) => {
    const acc = m?.metrics?.accuracy_mean ?? m?.metrics?.accuracy;
    return acc != null ? (acc * 100).toFixed(1) + "%" : "—";
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 24 }}>
      {/* Model Selector */}
      <div>
        <div className="sys-label" style={{ marginBottom: 10 }}>Select Trained Model</div>
        {loadingModels ? (
          <div className="skeleton" style={{ height: 160 }} />
        ) : models.length === 0 ? (
          <div style={{ fontSize: 12, color: "var(--text-tertiary)", padding: "20px 0" }}>
            No trained models found. Run an experiment first.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 240, overflowY: "auto" }}>
            {models.map(m => (
              <div key={m.model_id}
                onClick={() => { setSelectedModel(m); setSignal(null); }}
                style={{
                  padding: "10px 12px", borderRadius: 6, cursor: "pointer",
                  border: `1px solid ${selectedModel?.model_id === m.model_id ? "var(--blue-500)" : "var(--border-dim)"}`,
                  background: selectedModel?.model_id === m.model_id ? "rgba(66,106,230,0.08)" : "var(--bg-elevated)",
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text-primary)", marginBottom: 3 }}>
                  {m.kind || "Model"}
                  <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", marginLeft: 8 }}>
                    {m.model_id?.slice(0, 10)}…
                  </span>
                </div>
                <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>
                  Accuracy: {fmtAcc(m)} · {m.symbol || "?"}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Config + Signal */}
      <div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 14 }}>
          <div className="input-group">
            <label className="input-label">Symbol</label>
            <select className="input" value={form.symbol} onChange={e => setForm({ ...form, symbol: e.target.value })}>
              {["SYN-EQUITY", "BTCUSDT", "ETHUSDT", "AAPL", "MSFT", "SPY"].map(s =>
                <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">Provider</label>
            <select className="input" value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })}>
              <option value="synthetic">Synthetic</option>
              <option value="binance">Binance</option>
              <option value="yahoo">Yahoo Finance</option>
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">Interval</label>
            <select className="input" value={form.interval} onChange={e => setForm({ ...form, interval: e.target.value })}>
              {["5m", "15m", "1h", "4h", "1d"].map(i => <option key={i} value={i}>{i}</option>)}
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">Size (%)</label>
            <input type="number" className="input" min="0.1" max="100" step="0.5"
              value={form.size_pct} onChange={e => setForm({ ...form, size_pct: parseFloat(e.target.value) })} />
          </div>
          <div className="input-group">
            <label className="input-label">Stop Loss (%)</label>
            <input type="number" className="input" min="0" max="50" step="0.5"
              value={form.stop_loss_pct} onChange={e => setForm({ ...form, stop_loss_pct: parseFloat(e.target.value) })} />
          </div>
          <div className="input-group">
            <label className="input-label">Take Profit (%)</label>
            <input type="number" className="input" min="0" max="100" step="0.5"
              value={form.take_profit_pct} onChange={e => setForm({ ...form, take_profit_pct: parseFloat(e.target.value) })} />
          </div>
        </div>

        {/* Threshold sliders */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 14 }}>
          <div className="input-group">
            <label className="input-label">Long Threshold (prob_up ≥)</label>
            <input type="number" className="input" min="0.5" max="0.99" step="0.01"
              value={form.upper_threshold} onChange={e => setForm({ ...form, upper_threshold: parseFloat(e.target.value) })} />
          </div>
          <div className="input-group">
            <label className="input-label">Short Threshold (prob_up ≤)</label>
            <input type="number" className="input" min="0.01" max="0.5" step="0.01"
              value={form.lower_threshold} onChange={e => setForm({ ...form, lower_threshold: parseFloat(e.target.value) })} />
          </div>
        </div>

        {/* Signal preview */}
        {signal && (
          <div style={{
            background: signal.signal === "long" ? "rgba(46,175,107,0.08)" : signal.signal === "short" ? "rgba(220,64,75,0.08)" : "var(--bg-elevated)",
            border: `1px solid ${signal.signal === "long" ? "rgba(46,175,107,0.3)" : signal.signal === "short" ? "rgba(220,64,75,0.3)" : "var(--border-dim)"}`,
            borderRadius: 6, padding: "12px 16px", marginBottom: 12,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <span className="sys-label">Model Signal</span>
                <span style={{
                  marginLeft: 10, padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600,
                  background: signal.signal === "long" ? "var(--green)" : signal.signal === "short" ? "var(--red)" : "var(--text-tertiary)",
                  color: "#fff"
                }}>
                  {signal.signal.toUpperCase()}
                </span>
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                <span style={{ color: "var(--text-tertiary)" }}>P(up) = </span>
                <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{(signal.prob_up * 100).toFixed(1)}%</span>
              </div>
            </div>
            {/* Probability bar */}
            <div style={{ marginTop: 8, height: 4, borderRadius: 2, background: "var(--border-dim)", overflow: "hidden" }}>
              <div style={{ width: `${signal.prob_up * 100}%`, height: "100%",
                background: signal.prob_up >= form.upper_threshold ? "var(--green)" : signal.prob_up <= form.lower_threshold ? "var(--red)" : "var(--text-tertiary)" }} />
            </div>
            <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 4 }}>
              {signal.model_kind} · {signal.feature_count} features · bar {signal.bar_time?.slice(0, 10)}
            </div>
          </div>
        )}

        {error && <div style={{ fontSize: 11, color: "var(--red)", marginBottom: 10, padding: "6px 10px", background: "rgba(220,64,75,0.1)", borderRadius: 4 }}>{error}</div>}
        {success && <div style={{ fontSize: 11, color: "var(--green)", marginBottom: 10, padding: "6px 10px", background: "rgba(46,175,107,0.1)", borderRadius: 4 }}>{success}</div>}

        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-ghost" style={{ flex: 1, justifyContent: "center" }}
            onClick={getSignal} disabled={checking || !selectedModel}>
            {checking ? "Running Inference…" : "Get Signal Preview"}
          </button>
          <button className="btn btn-primary" style={{ flex: 1, justifyContent: "center" }}
            onClick={deploy} disabled={deploying || !selectedModel}>
            {deploying ? "Deploying…" : "Deploy → Open Position"}
          </button>
        </div>
        <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 6 }}>
          "Deploy" runs live inference and opens a position only if the signal is above the threshold. "Get Signal" is read-only.
        </div>
      </div>
    </div>
  );
}

/* ─── Open Positions ──────────────────────────────────────────────── */
function OpenPositions({ positions, loading, onRefresh }) {
  const closePos = async (id) => {
    if (!window.confirm("Close this position at market price?")) return;
    try {
      await axios.post(`${API}/paper-trading/positions/${id}/close`, { exit_reason: "manual" });
      onRefresh();
    } catch (err) {
      const detail = err.response?.data?.detail;
      alert(detail ? (typeof detail === 'string' ? detail : JSON.stringify(detail)) : "Failed to close position");
    }
  };

  return (
    <div>
      <div className="sys-label" style={{ marginBottom: 10 }}>Open Positions</div>
      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden" }}>
        {loading && !positions.length ? (
          <div style={{ padding: 20 }}><div className="skeleton" style={{ height: 60 }} /></div>
        ) : !positions.length ? (
          <div style={{ padding: "32px 20px", textAlign: "center", color: "var(--text-tertiary)", fontSize: 12 }}>No open positions.</div>
        ) : (
          <table className="atlas-table">
            <thead>
              <tr>
                <th>Symbol</th><th>Side</th><th>Entry Px</th><th>Mark Px</th><th>Unreal. PnL</th><th></th>
              </tr>
            </thead>
            <tbody>
              {positions.map(p => (
                <tr key={p.position_id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{p.symbol}</div>
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>{p.provider} · {p.interval}</div>
                  </td>
                  <td>
                    <span className="badge" style={{
                      background: p.side === "long" ? "rgba(46,175,107,0.15)" : "rgba(220,64,75,0.15)",
                      color: p.side === "long" ? "var(--green)" : "var(--red)"
                    }}>{p.side.toUpperCase()}</span>
                  </td>
                  <td className="mono-value">${p.entry_price?.toFixed(4)}</td>
                  <td className="mono-value">${(p.last_mark_price || p.entry_price)?.toFixed(4)}</td>
                  <td className="mono-value" style={{ color: (p.unrealized_pnl || 0) >= 0 ? "var(--green)" : "var(--red)" }}>
                    {(p.unrealized_pnl || 0) >= 0 ? "+" : ""}${(p.unrealized_pnl || 0).toFixed(2)}
                  </td>
                  <td><button className="btn btn-sm btn-ghost" onClick={() => closePos(p.position_id)}>Close</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ─── Trade History ───────────────────────────────────────────────── */
function TradeHistory({ trades, loading }) {
  return (
    <div>
      <div className="sys-label" style={{ marginBottom: 10 }}>Recent Trades</div>
      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden" }}>
        {loading && !trades.length ? (
          <div style={{ padding: 20 }}><div className="skeleton" style={{ height: 60 }} /></div>
        ) : !trades.length ? (
          <div style={{ padding: "32px 20px", textAlign: "center", color: "var(--text-tertiary)", fontSize: 12 }}>No trades yet.</div>
        ) : (
          <table className="atlas-table">
            <thead>
              <tr><th>Symbol</th><th>Side</th><th>Exit Px</th><th>PnL</th><th>Reason</th></tr>
            </thead>
            <tbody>
              {trades.map(t => (
                <tr key={t.trade_id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{t.symbol}</div>
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>{fmtRelative(t.closed_at)}</div>
                  </td>
                  <td>
                    <span style={{ fontSize: 11, color: t.side === "long" ? "var(--green)" : "var(--red)", textTransform: "uppercase", fontFamily: "var(--font-mono)" }}>
                      {t.side}
                    </span>
                  </td>
                  <td className="mono-value">${t.exit_price?.toFixed(4)}</td>
                  <td className="mono-value" style={{ color: (t.realized_pnl || 0) >= 0 ? "var(--green)" : "var(--red)" }}>
                    {(t.realized_pnl || 0) >= 0 ? "+" : ""}${(t.realized_pnl || 0).toFixed(2)}
                  </td>
                  <td><span className="badge badge-inactive">{t.exit_reason}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}


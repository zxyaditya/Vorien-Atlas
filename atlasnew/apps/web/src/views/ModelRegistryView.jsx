import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API, makeAbortable, isAbortError, fmtRelative } from "../lib/helpers";
import { SymbolSelector } from "../components/SymbolSelector";

export function ModelRegistryView() {
  const [activeTab, setActiveTab] = useState("registry"); // 'registry' or 'laboratory'
  
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div className="workspace-header" style={{ padding: "20px 28px 16px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div>
            <h2 className="workspace-title">Model Registry & Laboratory</h2>
            <div className="workspace-subtitle">
              Versioned model checkpoints, hyperparameter sweeps, and out-of-sample validation.
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button 
              className={`btn btn-sm ${activeTab === "registry" ? "btn-secondary" : "btn-ghost"}`}
              onClick={() => setActiveTab("registry")}
            >
              Registered Models
            </button>
            <button 
              className={`btn btn-sm ${activeTab === "laboratory" ? "btn-secondary" : "btn-ghost"}`}
              onClick={() => setActiveTab("laboratory")}
            >
              Model Laboratory
            </button>
            <button 
              className={`btn btn-sm ${activeTab === "history" ? "btn-secondary" : "btn-ghost"}`}
              onClick={() => setActiveTab("history")}
            >
              Prediction History
            </button>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "hidden" }}>
        {activeTab === "registry" && <ModelRegistryList />}
        {activeTab === "laboratory" && <ModelLaboratory />}
        {activeTab === "history" && <ModelHistory />}
      </div>
    </div>
  );
}

function ModelRegistryList() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  const load = useCallback(async (signal) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/learning/models`, { signal });
      setModels(res.data || []);
      if (res.data?.length > 0) setSelected(res.data[0]);
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

  const handleDeleteModel = async () => {
    if (!selected) return;
    if (!window.confirm(`Are you sure you want to delete model ${selected.model_id}? This cannot be undone.`)) return;
    try {
      await axios.delete(`${API}/learning/models/${selected.model_id}`);
      setSelected(null);
      load(); // Reload list
    } catch (err) {
      alert("Failed to delete model: " + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* List */}
      <div style={{ width: 340, flexShrink: 0, borderRight: "1px solid var(--border-dim)", overflow: "auto", background: "var(--bg-surface)" }}>
        {loading ? (
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
            {[...Array(6)].map((_, i) => <div key={i} className="skeleton" style={{ height: 68 }} />)}
          </div>
        ) : models.length === 0 ? (
          <div className="page-empty" style={{ paddingTop: 60 }}>
            <div className="page-empty-title">No Models Found</div>
            <div className="page-empty-desc">Train a model in the laboratory to register it.</div>
          </div>
        ) : (
          models.map(m => (
            <div
              key={m.model_id}
              onClick={() => setSelected(m)}
              style={{
                padding: "14px 18px",
                borderBottom: "1px solid var(--border-dim)",
                cursor: "pointer",
                background: selected?.model_id === m.model_id ? "var(--bg-hover)" : "transparent",
                borderLeft: selected?.model_id === m.model_id ? "2px solid var(--blue-500)" : "2px solid transparent",
                transition: "background 100ms",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                <span className="badge badge-active">{m.kind}</span>
                <span style={{ fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
                  {m.symbol || "UNKNOWN"}
                </span>
              </div>
              <div style={{ fontSize: 12.5, color: "var(--text-primary)", fontWeight: 500, marginBottom: 4, fontFamily: "var(--font-mono)" }}>
                {m.model_id}
              </div>
              {m.metrics?.accuracy_mean !== undefined && (
                <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 }}>
                  Accuracy: <span style={{ color: "var(--green)" }}>{(m.metrics.accuracy_mean * 100).toFixed(1)}%</span>
                </div>
              )}
              <div style={{ marginTop: 6, fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
                {fmtRelative(m.created_at)}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Details */}
      <div style={{ flex: 1, padding: "32px 40px", overflow: "auto", background: "var(--bg-base)" }}>
        {!selected ? (
          <div className="page-empty">
            <div className="page-empty-desc">Select a model to view its validation metrics.</div>
          </div>
        ) : (
          <div style={{ maxWidth: 800, margin: "0 auto" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
              <div>
                <h3 style={{ fontSize: 20, fontWeight: 300, color: "var(--text-primary)", fontFamily: "var(--font-mono)", marginBottom: 4 }}>
                  {selected.model_id}
                </h3>
                <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                  Trained on {new Date(selected.created_at).toLocaleString()}
                </div>
              </div>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <div className="badge badge-active">{selected.kind}</div>
                <button className="btn btn-sm btn-ghost" style={{ color: "var(--red)" }} onClick={handleDeleteModel}>
                  Delete
                </button>
              </div>
            </div>

            {/* Validation Metrics */}
            <div style={{ marginBottom: 32 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>Out-of-Sample Validation</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", border: "1px solid var(--border-dim)", borderRadius: 4, overflow: "hidden", position: "relative" }}>
                <div style={{ position: "absolute", top: 0, left: 0, width: 8, height: 8, borderTop: "1px solid var(--border-accent)", borderLeft: "1px solid var(--border-accent)", pointerEvents: "none" }} />
                {[
                  { label: "Accuracy", value: selected.metrics?.accuracy_mean !== undefined ? (selected.metrics.accuracy_mean * 100).toFixed(2) + "%" : "—" },
                  { label: "AUROC", value: selected.metrics?.roc_auc_mean !== undefined ? selected.metrics.roc_auc_mean.toFixed(3) : "—" },
                  { label: "Log Loss", value: selected.metrics?.log_loss_mean !== undefined ? selected.metrics.log_loss_mean.toFixed(3) : "—" },
                ].map((s, i) => (
                  <div key={i} style={{ padding: "16px 20px", background: "var(--bg-elevated)", borderRight: i < 2 ? "1px solid var(--border-dim)" : "none" }}>
                    <div className="stat-label">{s.label}</div>
                    <div className="stat-value" style={{ fontSize: 16, marginTop: 4 }}>{s.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Configuration */}
            <div style={{ marginBottom: 32 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>Model Configuration</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, border: "1px solid var(--border-dim)", borderRadius: 4, overflow: "hidden" }}>
                {[
                  { label: "Experiment ID", value: selected.experiment_id },
                  { label: "Fold", value: selected.fold },
                  { label: "Features", value: selected.feature_ids?.length },
                  { label: "Asset", value: selected.symbol },
                ].map((row, i) => (
                  <div key={i} style={{
                    padding: "12px 16px", background: "var(--bg-elevated)",
                    borderRight: i % 2 === 0 ? "1px solid var(--border-dim)" : "none",
                    borderBottom: i < 2 ? "1px solid var(--border-dim)" : "none",
                  }}>
                    <div className="mono-label" style={{ marginBottom: 4 }}>{row.label}</div>
                    <div className="mono-value">{row.value || "—"}</div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}

function ModelLaboratory() {
  const [modelType, setModelType] = useState("xgboost");
  const [horizon, setHorizon] = useState(5);
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [provider, setProvider] = useState("binance");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleTrain = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const payload = {
        provider, symbol, interval: "1d", period: "2y",
        horizon: parseInt(horizon, 10),
        model: modelType
      };
      
      const res = await axios.post(`${API}/predict/train`, payload);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail ? (typeof err.response.data.detail === 'string' ? err.response.data.detail : JSON.stringify(err.response.data.detail)) : err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Config */}
      <div style={{ width: 360, flexShrink: 0, borderRight: "1px solid var(--border-dim)", padding: "24px 28px", overflow: "auto" }}>
        <div style={{ marginBottom: 32 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>Training Configuration</div>
          
          <div className="input-group">
            <label className="input-label">Architecture</label>
            <select className="input" value={modelType} onChange={e => setModelType(e.target.value)}>
              <option value="xgboost">XGBoost (Gradient Boosted Trees)</option>
              <option value="randomforest">Random Forest Classifier</option>
              <option value="logreg">Logistic Regression (L2)</option>
            </select>
          </div>
          
          <SymbolSelector
            provider={provider}
            symbol={symbol}
            onProviderChange={setProvider}
            onSymbolChange={setSymbol}
            style={{ marginBottom: 12, flexDirection: "column" }}
          />
          
          <div className="input-group">
            <label className="input-label">Prediction Horizon (Bars)</label>
            <input type="number" className="input" value={horizon} onChange={e => setHorizon(e.target.value)} />
          </div>
        </div>

        <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={handleTrain} disabled={loading}>
          {loading ? "Training Model..." : "Dispatch Training Job"}
        </button>

        {error && (
          <div style={{ marginTop: 16, padding: "12px 16px", background: "var(--red-muted)", border: "1px solid rgba(220,64,75,0.2)", borderRadius: 4, fontSize: 12.5, color: "var(--red)" }}>
            {error}
          </div>
        )}
      </div>

      {/* Output */}
      <div style={{ flex: 1, padding: "32px 40px", overflow: "auto", background: "var(--bg-base)" }}>
        {!result && !loading && (
          <div className="page-empty">
            <div className="page-empty-desc">Configure parameters and dispatch a training job.</div>
          </div>
        )}
        {loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="skeleton" style={{ height: 120, borderRadius: 4 }} />
            <div className="skeleton" style={{ height: 300, borderRadius: 4 }} />
          </div>
        )}
        {result && result.error && (
          <div style={{ maxWidth: 800, margin: "0 auto" }}>
            <div style={{ padding: 24, backgroundColor: "var(--bg-elevated)", border: "1px solid var(--alert-red)", borderRadius: 4 }}>
              <h3 style={{ fontSize: 18, color: "var(--alert-red)", marginBottom: 8, fontWeight: 500 }}>Training Failed</h3>
              <p style={{ color: "var(--text-secondary)", margin: 0, fontFamily: "var(--font-mono)", fontSize: 13 }}>{result.error}</p>
            </div>
          </div>
        )}
        {result && !result.error && (
          <div style={{ maxWidth: 800, margin: "0 auto" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
              <h3 style={{ fontSize: 20, fontWeight: 300, color: "var(--text-primary)" }}>Training Completed</h3>
              <div className="badge badge-active">{modelType.toUpperCase()}</div>
            </div>

            {/* Performance */}
            <div style={{ marginBottom: 32 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>Validation Metrics</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", border: "1px solid var(--border-dim)", borderRadius: 4, overflow: "hidden", position: "relative" }}>
                <div style={{ position: "absolute", top: 0, left: 0, width: 8, height: 8, borderTop: "1px solid var(--border-accent)", borderLeft: "1px solid var(--border-accent)", pointerEvents: "none" }} />
                {[
                  { label: "Accuracy", value: result.metrics?.accuracy ? (result.metrics.accuracy * 100).toFixed(2) + "%" : "—" },
                  { label: "Precision", value: result.metrics?.precision ? result.metrics.precision.toFixed(3) : "—" },
                  { label: "Recall", value: result.metrics?.recall ? result.metrics.recall.toFixed(3) : "—" },
                ].map((s, i) => (
                  <div key={i} style={{ padding: "16px 20px", background: "var(--bg-elevated)", borderRight: i < 2 ? "1px solid var(--border-dim)" : "none" }}>
                    <div className="stat-label">{s.label}</div>
                    <div className="stat-value" style={{ fontSize: 16, marginTop: 4 }}>{s.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Latest Prediction */}
            {result.prediction && (
              <div style={{ marginBottom: 32 }}>
                <div className="sys-label" style={{ marginBottom: 12 }}>Current State Inference (T_0)</div>
                <div style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4, padding: "16px 20px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                    <span className="mono-label">Direction</span>
                    <span className="mono-value" style={{ color: result.prediction.direction === "UP" ? "var(--green)" : "var(--red)" }}>
                      {result.prediction.direction}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                    <span className="mono-label">Confidence</span>
                    <span className="mono-value">{(result.prediction.confidence * 100).toFixed(1)}%</span>
                  </div>
                  {result.expected_move && (
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span className="mono-label">Expected Volatility ({horizon} Bars)</span>
                      <span className="mono-value">{result.expected_move.sigma_pct}%</span>
                    </div>
                  )}
                </div>
              </div>
            )}
            
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", fontStyle: "italic", textAlign: "center", marginTop: 24 }}>
              This model run has been persisted to the predictions database.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ModelHistory() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const { signal, abort } = makeAbortable();
    axios.get(`${API}/predict/history`, { signal, params: { limit: 50 } })
      .then(res => setHistory(res.data || []))
      .catch(err => { if (!isAbortError(err)) console.error(err); })
      .finally(() => setLoading(false));
    return () => abort();
  }, []);

  const dirColor = (dir) => {
    if (!dir) return "var(--text-tertiary)";
    const d = dir.toUpperCase();
    if (d === "BUY" || d === "LONG" || d === "UP") return "var(--green)";
    if (d === "SELL" || d === "SHORT" || d === "DOWN") return "var(--red)";
    return "var(--amber)";
  };

  return (
    <div style={{ padding: "24px 28px", maxWidth: 1100, margin: "0 auto", height: "100%", overflow: "auto" }}>
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[1,2,3,4,5].map(i => <div key={i} className="skeleton" style={{ height: 52 }} />)}
        </div>
      ) : history.length === 0 ? (
        <div className="page-empty" style={{ paddingTop: 60 }}>
          <div className="page-empty-title">No Prediction History</div>
          <div className="page-empty-desc">Train models in the laboratory to generate predictions.</div>
        </div>
      ) : (
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden" }}>
          <table className="atlas-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Model</th>
                <th>Symbol</th>
                <th>Direction</th>
                <th>Confidence</th>
                <th>Horizon</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={i}>
                  <td style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
                    {fmtRelative(h.created_at)}
                  </td>
                  <td style={{ fontWeight: 500 }}>{h.model || h.model_id || "—"}</td>
                  <td className="mono-value">{h.symbol || "—"}</td>
                  <td>
                    <span style={{ color: dirColor(h.prediction?.direction || h.direction), fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600 }}>
                      {(h.prediction?.direction || h.direction || "—").toUpperCase()}
                    </span>
                  </td>
                  <td className="mono-value">
                    {h.prediction?.confidence != null ? (h.prediction.confidence * 100).toFixed(1) + "%" : (h.confidence != null ? (h.confidence * 100).toFixed(1) + "%" : "—")}
                  </td>
                  <td className="mono-value">{h.horizon || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

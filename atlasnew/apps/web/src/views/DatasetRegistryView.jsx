import React, { useState, useEffect } from "react";
import axios from "axios";
import { API, makeAbortable, isAbortError, INTERVALS } from "../lib/helpers";

export function DatasetRegistryView() {
  const [activeTab, setActiveTab] = useState("builder"); // 'registry' or 'builder'
  
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div className="workspace-header" style={{ padding: "20px 28px 16px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div>
            <h2 className="workspace-title">Dataset Registry</h2>
            <div className="workspace-subtitle">
              Versioned, reproducible dataset configurations built from the Feature Registry.
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button 
              className={`btn btn-sm ${activeTab === "registry" ? "btn-secondary" : "btn-ghost"}`}
              onClick={() => setActiveTab("registry")}
            >
              Registered Datasets
            </button>
            <button 
              className={`btn btn-sm ${activeTab === "builder" ? "btn-secondary" : "btn-ghost"}`}
              onClick={() => setActiveTab("builder")}
            >
              Dataset Builder
            </button>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        {activeTab === "builder" ? <DatasetBuilder /> : <DatasetList />}
      </div>
    </div>
  );
}

function DatasetList() {
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const { signal, abort } = makeAbortable();
    axios.get(`${API}/learning/datasets`, { signal })
      .then(res => setDatasets(res.data || []))
      .catch(err => { if (!isAbortError(err)) console.error(err); })
      .finally(() => setLoading(false));
    return () => abort();
  }, []);

  if (loading) {
    return (
      <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 8 }}>
        {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: 60 }} />)}
      </div>
    );
  }

  if (datasets.length === 0) {
    return (
      <div className="page-empty" style={{ paddingTop: 80 }}>
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1" style={{ marginBottom: 16 }}>
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        <div className="page-empty-title">No Registered Datasets</div>
        <div className="page-empty-desc">
          Datasets are constructed dynamically during experiments. <br/>
          Use the Dataset Builder to specify and preview a dataset configuration.
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "24px 28px", maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden" }}>
        <table className="atlas-table">
          <thead>
            <tr>
              <th>Dataset ID</th>
              <th>Features</th>
              <th>Horizon</th>
              <th>Label</th>
              <th>Rows</th>
              <th>Symbol</th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((ds, i) => (
              <tr key={ds.dataset_id || i}>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 500 }}>
                  {(ds.dataset_id || "—").substring(0, 12)}
                </td>
                <td className="mono-value">{ds.n_features ?? ds.feature_ids?.length ?? "—"}</td>
                <td className="mono-value">{ds.horizon ?? "—"}</td>
                <td className="mono-value">{ds.label_kind || "—"}</td>
                <td className="mono-value">{ds.n_rows ?? "—"}</td>
                <td className="mono-value" style={{ color: "var(--text-tertiary)" }}>{ds.symbol || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DatasetBuilder() {
  const [provider, setProvider] = useState("synthetic");
  const [symbol, setSymbol] = useState("SYN-EQUITY");
  const [interval, setInterval] = useState("1d");
  const [period, setPeriod] = useState("3y");
  
  const [horizon, setHorizon] = useState(5);
  const [labelKind, setLabelKind] = useState("sign");
  const [minHistory, setMinHistory] = useState(200);
  
  const [features, setFeatures] = useState([]);
  const [selectedFeatures, setSelectedFeatures] = useState(["l1.price.log_return", "l1.price.volatility_20", "l1.volume.relative"]);
  
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load available features for selection
  useEffect(() => {
    const { signal, abort } = makeAbortable();
    axios.get(`${API}/registry/features`, { signal })
      .then(res => setFeatures(res.data || []))
      .catch(err => { if (!isAbortError(err)) console.error("Failed to load features"); });
    return () => abort();
  }, []);

  const handlePreview = async () => {
    if (selectedFeatures.length === 0) {
      setError("Please select at least one feature.");
      return;
    }
    setLoading(true);
    setError(null);
    setPreview(null);
    
    try {
      const payload = {
        provider, symbol, interval, period,
        dataset: {
          feature_ids: selectedFeatures,
          horizon: parseInt(horizon, 10),
          label_kind: labelKind,
          min_history: parseInt(minHistory, 10),
          dropna_policy: "any"
        }
      };
      
      const res = await axios.post(`${API}/learning/datasets/preview`, payload);
      
      if (typeof res.data !== "object" || !res.data.shape) {
        throw new Error("Invalid response from server. Backend endpoint is missing or returned HTML.");
      }
      
      setPreview(res.data);
    } catch (err) {
      setError(err.response?.data?.detail ? (typeof err.response.data.detail === 'string' ? err.response.data.detail : JSON.stringify(err.response.data.detail)) : err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Configuration Panel */}
      <div style={{ width: 420, flexShrink: 0, borderRight: "1px solid var(--border-dim)", padding: "24px 28px", overflow: "auto" }}>
        
        {/* Source Configuration */}
        <div style={{ marginBottom: 32 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>1. Market Data Source</div>
          <div className="input-group">
            <label className="input-label">Provider</label>
            <select className="input" value={provider} onChange={e => setProvider(e.target.value)}>
              <option value="synthetic">Synthetic</option>
              <option value="binance">Binance</option>
              <option value="yahoo">Yahoo Finance</option>
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">Symbol</label>
            <select className="input" value={symbol} onChange={e => setSymbol(e.target.value)}>
              {provider === "synthetic" ? (
                <option value="SYN-EQUITY">SYN-EQUITY</option>
              ) : provider === "binance" ? (
                <>
                  <option value="BTCUSDT">BTCUSDT</option>
                  <option value="ETHUSDT">ETHUSDT</option>
                  <option value="SOLUSDT">SOLUSDT</option>
                  <option value="BNBUSDT">BNBUSDT</option>
                </>
              ) : (
                <>
                  <option value="AAPL">AAPL</option>
                  <option value="MSFT">MSFT</option>
                  <option value="TSLA">TSLA</option>
                </>
              )}
            </select>
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <div className="input-group" style={{ flex: 1 }}>
              <label className="input-label">Interval</label>
              <select className="input" value={interval} onChange={e => setInterval(e.target.value)}>
                {INTERVALS.map(i => <option key={i} value={i}>{i}</option>)}
              </select>
            </div>
            <div className="input-group" style={{ flex: 1 }}>
              <label className="input-label">Period</label>
              <select className="input" value={period} onChange={e => setPeriod(e.target.value)}>
                <option value="1y">1 Year</option>
                <option value="3y">3 Years</option>
                <option value="5y">5 Years</option>
              </select>
            </div>
          </div>
        </div>

        {/* Feature Engineering */}
        <div style={{ marginBottom: 32 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>2. Feature Selection</div>
          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 8, lineHeight: 1.5 }}>
            Selected: {selectedFeatures.length} features. 
          </div>
          <div style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4, padding: "8px 12px", maxHeight: 200, overflow: "auto" }}>
            {selectedFeatures.map(f => (
              <div key={f} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                <span>{f}</span>
                <span style={{ color: "var(--red)", cursor: "pointer" }} onClick={() => setSelectedFeatures(prev => prev.filter(x => x !== f))}>✕</span>
              </div>
            ))}
          </div>
          
          <div className="input-group" style={{ marginTop: 12 }}>
            <input 
              className="input" 
              list="feature-registry-list"
              placeholder="+ Search and Add Feature..."
              onChange={e => {
                const val = e.target.value;
                if (features.find(f => f.id === val) && !selectedFeatures.includes(val)) {
                  setSelectedFeatures([...selectedFeatures, val]);
                  e.target.value = "";
                }
              }}
            />
            <datalist id="feature-registry-list">
              {features.map(f => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </datalist>
          </div>
        </div>

        {/* Label Engineering */}
        <div style={{ marginBottom: 32 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>3. Label Engineering</div>
          <div className="input-group">
            <label className="input-label">Prediction Horizon (Bars)</label>
            <input type="number" className="input" value={horizon} onChange={e => setHorizon(e.target.value)} />
          </div>
          <div className="input-group">
            <label className="input-label">Label Transformation</label>
            <select className="input" value={labelKind} onChange={e => setLabelKind(e.target.value)}>
              <option value="sign">Sign (Up/Down)</option>
              <option value="magnitude">Magnitude (Continuous Return)</option>
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">Minimum History (Bars)</label>
            <input type="number" className="input" value={minHistory} onChange={e => setMinHistory(e.target.value)} />
          </div>
        </div>

        <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={handlePreview} disabled={loading}>
          {loading ? "Compiling Dataset..." : "Build Dataset Preview"}
        </button>
        
        {error && (
          <div style={{ marginTop: 16, padding: "12px 16px", background: "var(--red-muted)", border: "1px solid rgba(220,64,75,0.2)", borderRadius: 4, fontSize: 12.5, color: "var(--red)" }}>
            {error}
          </div>
        )}
      </div>

      {/* Preview Panel */}
      <div style={{ flex: 1, padding: "32px 40px", overflow: "auto", background: "var(--bg-base)" }}>
        {!preview && !loading && (
          <div className="page-empty">
            <div className="page-empty-desc">Configure parameters and build preview to see dataset characteristics.</div>
          </div>
        )}
        {loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="skeleton" style={{ height: 120, borderRadius: 4 }} />
            <div className="skeleton" style={{ height: 300, borderRadius: 4 }} />
          </div>
        )}
        {preview && (
          <div style={{ maxWidth: 800, margin: "0 auto" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
              <h3 style={{ fontSize: 20, fontWeight: 300, color: "var(--text-primary)" }}>Dataset Compiled Successfully</h3>
              <div className="badge badge-active">Ready for Experimentation</div>
            </div>

            {/* Shape Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", border: "1px solid var(--border-dim)", borderRadius: 4, overflow: "hidden", marginBottom: 32, position: "relative" }}>
              <div style={{ position: "absolute", top: 0, left: 0, width: 8, height: 8, borderTop: "1px solid var(--border-accent)", borderLeft: "1px solid var(--border-accent)", pointerEvents: "none" }} />
              {[
                { label: "Valid Samples", value: preview.shape.samples.toLocaleString() },
                { label: "Feature Columns", value: preview.shape.features },
                { label: "Null Values", value: preview.shape.nulls },
              ].map((s, i) => (
                <div key={i} style={{ padding: "16px 20px", background: "var(--bg-elevated)", borderRight: i < 2 ? "1px solid var(--border-dim)" : "none" }}>
                  <div className="stat-label">{s.label}</div>
                  <div className="stat-value" style={{ fontSize: 16, marginTop: 4 }}>{s.value}</div>
                </div>
              ))}
            </div>

            {/* Label Summary */}
            <div style={{ marginBottom: 32 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>Label Characteristics ({preview.label.kind})</div>
              <div style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4, padding: "16px 20px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                  <span className="mono-label">Target Name</span>
                  <span className="mono-value">{preview.label.name}</span>
                </div>
                {preview.label.balance && (
                  <>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                      <span className="mono-label">Class 0 (Down)</span>
                      <span className="mono-value" style={{ color: "var(--red)" }}>{(preview.label.balance["0.0"] || preview.label.balance["0"] || 0)} samples</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span className="mono-label">Class 1 (Up)</span>
                      <span className="mono-value" style={{ color: "var(--green)" }}>{(preview.label.balance["1.0"] || preview.label.balance["1"] || 0)} samples</span>
                    </div>
                  </>
                )}
                {!preview.label.balance && (
                  <div style={{ fontSize: 12, color: "var(--text-tertiary)", fontStyle: "italic" }}>
                    Continuous label; balance not applicable.
                  </div>
                )}
              </div>
            </div>

            {/* Missing Info */}
            {preview.missing_info && Object.keys(preview.missing_info).length > 0 && (
              <div style={{ marginBottom: 32 }}>
                <div className="sys-label" style={{ marginBottom: 12 }}>Data Quality Warnings</div>
                <div style={{ background: "var(--amber-muted)", border: "1px solid rgba(245, 166, 35, 0.2)", borderRadius: 4, padding: "12px 16px", fontSize: 12.5, color: "var(--text-primary)" }}>
                  Some features resulted in dropped rows due to NaN propagation.
                  <ul style={{ margin: "8px 0 0 20px", color: "var(--text-secondary)" }}>
                    {Object.entries(preview.missing_info).slice(0, 10).map(([feat, nans]) => (
                      <li key={feat}><span style={{ fontFamily: "var(--font-mono)" }}>{feat}</span>: {nans} nulls</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
            
          </div>
        )}
      </div>
    </div>
  );
}

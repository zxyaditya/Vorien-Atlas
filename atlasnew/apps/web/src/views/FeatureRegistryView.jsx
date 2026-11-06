import React, { useState, useEffect } from "react";
import axios from "axios";
import { FeatureRegistryPanel } from "./project/ProjectFeatures";
import { SymbolSelector } from "../components/SymbolSelector";
import { API } from "../lib/helpers";

// Workspace-level feature registry
export function FeatureRegistryView() {
  const [activeTab, setActiveTab] = useState("registry");

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div className="workspace-header" style={{ padding: "20px 28px 16px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div>
            <h2 className="workspace-title">Feature Registry</h2>
            <div className="workspace-subtitle">
              Workspace-level catalogue of all registered research features with definitions and computed values.
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button 
              className={`btn btn-sm ${activeTab === "registry" ? "btn-secondary" : "btn-ghost"}`}
              onClick={() => setActiveTab("registry")}
            >
              Registry & Definitions
            </button>
            <button 
              className={`btn btn-sm ${activeTab === "correlation" ? "btn-secondary" : "btn-ghost"}`}
              onClick={() => setActiveTab("correlation")}
            >
              Cross-Correlation
            </button>
          </div>
        </div>
      </div>

      {/* Panel fills remaining height */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        {activeTab === "registry" && <FeatureRegistryPanel embedded={false} />}
        {activeTab === "correlation" && <CorrelationPanel />}
      </div>
    </div>
  );
}

function CorrelationPanel() {
  const [provider, setProvider] = useState("yahoo");
  const [symbol, setSymbol] = useState("SPY");
  const [module, setModule] = useState("");
  const [perspective, setPerspective] = useState("");
  
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [vocab, setVocab] = useState({ modules: [], perspectives: [] });

  // Load vocab once — /registry/vocab returns { layers, perspectives }
  // We also fetch features to extract the unique module list
  useEffect(() => {
    const fetchVocab = async () => {
      try {
        const [vocabRes, featsRes] = await Promise.all([
          axios.get(`${API}/registry/vocab`).catch(() => ({ data: {} })),
          axios.get(`${API}/registry/features`).catch(() => ({ data: [] })),
        ]);
        const modules = [...new Set((featsRes.data || []).map(f => f.module).filter(Boolean))].sort();
        setVocab({
          modules,
          perspectives: vocabRes.data?.perspectives || [],
        });
      } catch { /* silent */ }
    };
    fetchVocab();
  }, []);

  const loadCorrelation = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API}/features/correlation`, {
        params: { provider, symbol, module: module || undefined, perspective: perspective || undefined, limit: 25 }
      });
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail ? (typeof err.response.data.detail === 'string' ? err.response.data.detail : JSON.stringify(err.response.data.detail)) : err.message);
    } finally {
      setLoading(false);
    }
  };

  const getCellColor = (val) => {
    // Red for negative (-1 to 0), Green for positive (0 to 1)
    if (val === 1) return "var(--bg-elevated)";
    if (val < 0) {
      const alpha = Math.min(Math.abs(val), 1) * 0.5;
      return `rgba(220, 64, 75, ${alpha})`; // red
    } else {
      const alpha = Math.min(val, 1) * 0.5;
      return `rgba(66, 172, 102, ${alpha})`; // green
    }
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Sidebar */}
      <div style={{ width: 320, padding: "24px 28px", borderRight: "1px solid var(--border-dim)", overflow: "auto", flexShrink: 0, background: "var(--bg-surface)" }}>
        <div style={{ marginBottom: 24 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>Market Context</div>
          <SymbolSelector
            provider={provider} symbol={symbol}
            onProviderChange={setProvider} onSymbolChange={setSymbol}
            style={{ flexDirection: "column" }}
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>Feature Subset</div>
          <div className="input-group">
            <label className="input-label">Module Filter</label>
            <select className="input" value={module} onChange={e => setModule(e.target.value)}>
              <option value="">All Modules (Max 25)</option>
              {vocab.modules.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className="input-group" style={{ marginTop: 12 }}>
            <label className="input-label">Perspective Filter</label>
            <select className="input" value={perspective} onChange={e => setPerspective(e.target.value)}>
              <option value="">All Perspectives</option>
              {vocab.perspectives.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>

        <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={loadCorrelation} disabled={loading}>
          {loading ? "Computing Matrix..." : "Compute Correlation"}
        </button>

        {error && (
          <div style={{ marginTop: 16, padding: "12px 16px", background: "var(--red-muted)", border: "1px solid rgba(220,64,75,0.2)", borderRadius: 4, fontSize: 12.5, color: "var(--red)" }}>
            {error}
          </div>
        )}
      </div>

      {/* Main Heatmap */}
      <div style={{ flex: 1, padding: "32px 40px", overflow: "auto", background: "var(--bg-base)" }}>
        {!data && !loading && (
          <div className="page-empty">
            <div className="page-empty-desc">Configure context and compute to see feature correlations.</div>
          </div>
        )}
        
        {loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {[...Array(10)].map((_, i) => <div key={i} className="skeleton" style={{ height: 24 }} />)}
          </div>
        )}

        {data && data.matrix && data.matrix.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <div style={{ display: "inline-block", border: "1px solid var(--border-dim)", borderRadius: 4, background: "var(--bg-surface)", padding: 16 }}>
              <table style={{ borderSpacing: 1, borderCollapse: "separate" }}>
                <thead>
                  <tr>
                    <th style={{ padding: 4 }}></th>
                    {data.features.map((f, i) => (
                      <th key={i} style={{ padding: 4, writingMode: "vertical-rl", transform: "rotate(180deg)", textAlign: "left", fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-secondary)", fontWeight: 400 }}>
                        {f}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.matrix.map((row, i) => (
                    <tr key={i}>
                      <td style={{ padding: "4px 8px 4px 0", fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-secondary)", whiteSpace: "nowrap", textAlign: "right" }}>
                        {data.features[i]}
                      </td>
                      {row.map((val, j) => (
                        <td key={j} style={{
                          width: 28, height: 28, padding: 0, textAlign: "center",
                          background: getCellColor(val),
                          border: "1px solid rgba(0,0,0,0.1)",
                          fontSize: 9, fontFamily: "var(--font-mono)",
                          color: val === 1 ? "var(--text-tertiary)" : (Math.abs(val) > 0.6 ? "#fff" : "var(--text-primary)")
                        }} title={`${data.features[i]} vs ${data.features[j]}\nCorr: ${val.toFixed(3)}`}>
                          {val === 1 ? "" : (val > 0 ? "+" : "") + val.toFixed(1).replace("0.", ".")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {data && data.matrix && data.matrix.length === 0 && (
          <div className="page-empty">
            <div className="page-empty-desc">No data returned. Adjust filters or symbol.</div>
          </div>
        )}
      </div>
    </div>
  );
}

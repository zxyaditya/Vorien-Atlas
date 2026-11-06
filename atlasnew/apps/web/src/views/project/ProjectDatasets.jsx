import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API, fmtRelative } from "../../lib/helpers";
import { FeatureSelector } from "../../components/FeatureSelector";
import { SymbolSelector } from "../../components/SymbolSelector";

export function ProjectDatasets({ project }) {
  const [form, setForm] = useState({
    provider: "synthetic",
    symbol: "SYN-EQUITY",
    interval: "1d",
    period: "3y",
    dataset: {
      feature_ids: [],
      horizon: 5,
      label_kind: "sign",
      label_params: {},
      min_history: 200,
      dropna_policy: "none",
      regime_filter: false,
    }
  });

  const [savedDatasets, setSavedDatasets] = useState([]);
  const [previewData, setPreviewData] = useState(null);
  const [selectedDs, setSelectedDs] = useState(null);
  const [loading, setLoading] = useState(false);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const loadSaved = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/learning/datasets`, {
        params: project?._id ? { project_id: project._id } : {}
      });
      setSavedDatasets(res.data || []);
    } catch { /* silent */ }
  }, [project]);

  useEffect(() => {
    loadSaved();
  }, [loadSaved]);

  const handlePreview = async () => {
    if (form.dataset.feature_ids.length === 0) {
      alert("Please select at least one feature.");
      return;
    }
    setLoading(true); setError(null); setPreviewData(null);
    try {
      const res = await axios.post(`${API}/learning/datasets/preview`, form);
      setPreviewData(res.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail ? (typeof detail === 'string' ? detail : JSON.stringify(detail)) : err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBuild = async () => {
    if (form.dataset.feature_ids.length === 0) {
      alert("Please select at least one feature.");
      return;
    }
    setBuilding(true); setError(null); setSuccessMsg(null);
    try {
      const payload = { ...form, project_id: project?._id || null };
      const res = await axios.post(`${API}/learning/datasets/build`, payload);
      setSuccessMsg(`Dataset saved: ${res.data.n_rows} rows × ${res.data.n_features} features (ID: ${res.data.dataset_id.slice(0, 8)}…)`);
      setPreviewData(res.data);
      loadSaved();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail ? (typeof detail === 'string' ? detail : JSON.stringify(detail)) : err.message);
    } finally {
      setBuilding(false);
    }
  };

  const handleDelete = async (ds_id) => {
    if (!window.confirm("Delete this dataset record?")) return;
    try {
      await axios.delete(`${API}/learning/datasets/${ds_id}`);
      setSavedDatasets(prev => prev.filter(d => d.dataset_id !== ds_id));
      if (selectedDs?.dataset_id === ds_id) setSelectedDs(null);
    } catch (err) {
      const detail = err.response?.data?.detail;
      alert(detail ? (typeof detail === 'string' ? detail : JSON.stringify(detail)) : "Delete failed");
    }
  };

  const handleFeatureChange = (newIds) => {
    setForm(prev => ({ ...prev, dataset: { ...prev.dataset, feature_ids: newIds } }));
  };

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>

      {/* ── Left: Configuration Panel ─────────────────────────── */}
      <div style={{ width: 380, borderRight: "1px solid var(--border-dim)", display: "flex", flexDirection: "column", background: "var(--bg-surface)" }}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border-dim)" }}>
          <div style={{ fontSize: 14, color: "var(--text-primary)", fontWeight: 500 }}>Dataset Builder</div>
          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 3 }}>Configure, preview, then build & save to the registry</div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>

          {/* Market Data */}
          <div className="sys-label" style={{ marginBottom: 10 }}>Market Data Context</div>
          <SymbolSelector
            provider={form.provider}
            symbol={form.symbol}
            onProviderChange={v => setForm(prev => ({ ...prev, provider: v }))}
            onSymbolChange={v => setForm(prev => ({ ...prev, symbol: v }))}
            style={{ marginBottom: 16 }}
          />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 20 }}>
            <div className="input-group">
              <label className="input-label">Interval</label>
              <select className="input" value={form.interval} onChange={e => setForm({ ...form, interval: e.target.value })}>
                {["5m", "15m", "1h", "4h", "1d"].map(i => <option key={i} value={i}>{i}</option>)}
              </select>
            </div>
            <div className="input-group">
              <label className="input-label">Period</label>
              <select className="input" value={form.period} onChange={e => setForm({ ...form, period: e.target.value })}>
                {["1mo", "3mo", "6mo", "1y", "2y", "3y", "5y", "10y"].map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>

          {/* Label Engineering */}
          <div className="sys-label" style={{ marginBottom: 10 }}>Label Engineering</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 20 }}>
            <div className="input-group">
              <label className="input-label">Label Kind</label>
              <select className="input" value={form.dataset.label_kind} onChange={e => setForm({ ...form, dataset: { ...form.dataset, label_kind: e.target.value } })}>
                <option value="sign">Sign (Direction)</option>
                <option value="magnitude">Magnitude (Regression)</option>
                <option value="triple_barrier">Triple Barrier</option>
              </select>
            </div>
            <div className="input-group">
              <label className="input-label">Horizon (Bars)</label>
              <input type="number" className="input" value={form.dataset.horizon} min={1} max={252}
                onChange={e => setForm({ ...form, dataset: { ...form.dataset, horizon: parseInt(e.target.value) } })} />
            </div>
            {form.dataset.label_kind === "triple_barrier" && (
              <>
                <div className="input-group">
                  <label className="input-label">Take Profit (ATR Multiplier, k_upper)</label>
                  <input type="number" step="0.1" className="input" value={form.dataset.label_params.k_upper || 2.0}
                    onChange={e => setForm({ ...form, dataset: { ...form.dataset, label_params: { ...form.dataset.label_params, k_upper: parseFloat(e.target.value) } } })} />
                </div>
                <div className="input-group">
                  <label className="input-label">Stop Loss (ATR Multiplier, k_lower)</label>
                  <input type="number" step="0.1" className="input" value={form.dataset.label_params.k_lower || 2.0}
                    onChange={e => setForm({ ...form, dataset: { ...form.dataset, label_params: { ...form.dataset.label_params, k_lower: parseFloat(e.target.value) } } })} />
                </div>
              </>
            )}
            <div className="input-group" style={{ gridColumn: "1/-1" }}>
              <label className="input-label" style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Regime Filter</span>
                <input type="checkbox" checked={form.dataset.regime_filter}
                  onChange={e => setForm({ ...form, dataset: { ...form.dataset, regime_filter: e.target.checked } })} />
              </label>
            </div>
          </div>

          {/* Feature Selection */}
          <div className="sys-label" style={{ marginBottom: 10 }}>Feature Selection ({form.dataset.feature_ids.length} selected)</div>
          <FeatureSelector
            selectedIds={form.dataset.feature_ids}
            onChange={handleFeatureChange}
            maxHeight={320}
          />
        </div>

        {/* Action buttons */}
        <div style={{ padding: "14px 20px", borderTop: "1px solid var(--border-dim)", background: "var(--bg-elevated)", display: "flex", flexDirection: "column", gap: 8 }}>
          {error && <div style={{ fontSize: 11, color: "var(--red)", padding: "6px 10px", background: "rgba(220,64,75,0.1)", borderRadius: 4 }}>{error}</div>}
          {successMsg && <div style={{ fontSize: 11, color: "var(--green)", padding: "6px 10px", background: "rgba(46,175,107,0.1)", borderRadius: 4 }}>{successMsg}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-ghost" style={{ flex: 1, justifyContent: "center" }} onClick={handlePreview} disabled={loading}>
              {loading ? "Previewing…" : "Preview"}
            </button>
            <button className="btn btn-primary" style={{ flex: 1, justifyContent: "center" }} onClick={handleBuild} disabled={building}>
              {building ? "Building…" : "Build & Save →"}
            </button>
          </div>
        </div>
      </div>

      {/* ── Right: Preview + Dataset Registry ──────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Dataset preview result */}
        {previewData && (
          <div style={{ padding: "20px 28px", borderBottom: "1px solid var(--border-dim)", background: "var(--bg-surface)" }}>
            <div className="sys-label" style={{ marginBottom: 12 }}>
              {previewData.dataset_id ? "Built Dataset" : "Preview"}
              {previewData.dataset_id && <span style={{ marginLeft: 8, fontFamily: "var(--font-mono)", color: "var(--blue-500)", fontSize: 10 }}>{previewData.dataset_id.slice(0, 12)}…</span>}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
              {[
                ["Rows", previewData.n_rows ?? previewData.row_count ?? "—"],
                ["Features", previewData.n_features ?? "—"],
                ["Dropped (NaN)", previewData.n_nan_dropped ?? "—"],
                ["Dropped (Horizon)", previewData.n_horizon_dropped ?? "—"],
                ["Balance (UP/DOWN)", previewData.class_balance
                  ? (() => {
                      const up = previewData.class_balance[1] || previewData.class_balance["1"] || 0;
                      const down = previewData.class_balance[0] || previewData.class_balance["0"] || 0;
                      const total = up + down;
                      return total === 0 ? "—" : `${((up / total) * 100).toFixed(0)}% / ${((down / total) * 100).toFixed(0)}%`;
                    })()
                  : "—"],
              ].map(([label, val]) => (
                <div key={label} style={{ padding: "10px 14px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                  <div className="stat-label" style={{ fontSize: 10 }}>{label}</div>
                  <div style={{ fontSize: 14, fontFamily: "var(--font-mono)", color: "var(--text-primary)", marginTop: 2 }}>{val}</div>
                </div>
              ))}
            </div>
            {previewData.index_range && (
              <div style={{ marginTop: 10, fontSize: 11, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
                Date range: {previewData.index_range[0]?.slice(0, 10)} → {previewData.index_range[1]?.slice(0, 10)}
              </div>
            )}
          </div>
        )}

        {/* Saved Dataset Registry */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 28px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div className="sys-label">Saved Datasets ({savedDatasets.length})</div>
            <button className="btn btn-sm btn-ghost" onClick={loadSaved}>Refresh</button>
          </div>

          {savedDatasets.length === 0 ? (
            <div className="page-empty" style={{ paddingTop: 60 }}>
              <div className="page-empty-title">No Saved Datasets</div>
              <div className="page-empty-desc">Build and save a dataset above to store its metadata here.</div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {savedDatasets.map(ds => (
                <div key={ds.dataset_id}
                  onClick={() => setSelectedDs(ds)}
                  style={{
                    padding: "14px 16px",
                    background: selectedDs?.dataset_id === ds.dataset_id ? "var(--bg-elevated)" : "var(--bg-surface)",
                    border: `1px solid ${selectedDs?.dataset_id === ds.dataset_id ? "var(--blue-500)" : "var(--border-dim)"}`,
                    borderRadius: 6, cursor: "pointer",
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-tertiary)" }}>
                        {ds.dataset_id?.slice(0, 10)}…
                      </span>
                      <span className="badge" style={{ fontSize: 10 }}>{ds.symbol}</span>
                      <span className="badge badge-inactive" style={{ fontSize: 10 }}>{ds.interval}</span>
                      <span className="badge badge-inactive" style={{ fontSize: 10 }}>{ds.period}</span>
                    </div>
                    <div style={{ display: "flex", gap: 20, fontSize: 12, color: "var(--text-secondary)" }}>
                      <span><b>{ds.n_rows}</b> rows</span>
                      <span><b>{ds.n_features}</b> features</span>
                      <span>horizon <b>{ds.spec?.horizon}</b></span>
                      <span>{ds.spec?.label_kind}</span>
                    </div>
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 4 }}>{fmtRelative(ds.created_at)}</div>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn btn-sm btn-ghost" style={{ color: "var(--red)" }}
                      onClick={e => { e.stopPropagation(); handleDelete(ds.dataset_id); }}>
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}



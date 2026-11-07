import React, { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { API, makeAbortable, isAbortError, fmtRelative } from "../lib/helpers";
import { SymbolSelector } from "../components/SymbolSelector";
import { useAtlas } from "../store/atlasStore";

export function ModelRegistryView() {
  const [activeTab, setActiveTab] = useState("registry"); // 'registry', 'laboratory', 'history'
  
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div className="workspace-header" style={{ padding: "20px 28px 16px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div>
            <h2 className="workspace-title">Model Registry & Laboratory</h2>
            <div className="workspace-subtitle">
              Versioned model checkpoints, feature dimension selection, out-of-sample validation, and paper trading deployment.
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
        {activeTab === "laboratory" && <ModelLaboratory onDeploy={() => setActiveTab("registry")} />}
        {activeTab === "history" && <ModelHistory />}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   1. REGISTERED MODELS (Deep Quant Evaluation & Inspection)
   ═══════════════════════════════════════════════════════════════════════════ */
function ModelRegistryList() {
  const { dispatch } = useAtlas();
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [featureSearch, setFeatureSearch] = useState("");

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
      load();
    } catch (err) {
      alert("Failed to delete model: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleDeployToPaper = (m) => {
    if (!m) return;
    sessionStorage.setItem("atlas_prefill_model_id", m.model_id);
    dispatch({ type: "SET_VIEW", payload: "paper-trading" });
  };

  // Filter feature list in details
  const filteredFeatures = useMemo(() => {
    if (!selected?.feature_ids) return [];
    if (!featureSearch) return selected.feature_ids;
    const q = featureSearch.toLowerCase();
    return selected.feature_ids.filter(id => id.toLowerCase().includes(q));
  }, [selected?.feature_ids, featureSearch]);

  const m = selected?.metrics || {};
  const acc = m.accuracy_mean ?? m.accuracy;
  const prec = m.precision_mean ?? m.precision;
  const rec = m.recall_mean ?? m.recall;
  const f1 = m.f1_mean ?? m.f1;
  const auroc = m.roc_auc_mean ?? m.roc_auc;
  const logloss = m.log_loss_mean ?? m.log_loss;
  const brier = m.brier_mean ?? m.brier;
  const ic = m.information_coefficient_mean ?? m.information_coefficient;
  const cm = m.confusion_matrix;

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Models List */}
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
          models.map(mod => {
            const modAcc = mod.metrics?.accuracy_mean ?? mod.metrics?.accuracy;
            const featLen = mod.n_features || mod.feature_ids?.length || 0;
            const isSel = selected?.model_id === mod.model_id;
            return (
              <div
                key={mod.model_id}
                onClick={() => setSelected(mod)}
                style={{
                  padding: "14px 18px",
                  borderBottom: "1px solid var(--border-dim)",
                  cursor: "pointer",
                  background: isSel ? "var(--bg-hover)" : "transparent",
                  borderLeft: isSel ? "2px solid var(--blue-500)" : "2px solid transparent",
                  transition: "background 100ms",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span className="badge badge-active">{mod.kind?.toUpperCase() || "ML"}</span>
                    <span style={{ fontSize: 11, color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
                      {mod.symbol || "BTCUSDT"}
                    </span>
                  </div>
                  <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
                    {featLen} feats
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 500, marginBottom: 4, fontFamily: "var(--font-mono)", wordBreak: "break-all" }}>
                  {mod.model_id}
                </div>
                {modAcc !== undefined && (
                  <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 }}>
                    OOS Accuracy: <span style={{ color: "var(--green)", fontWeight: 500 }}>{(modAcc * 100).toFixed(1)}%</span>
                  </div>
                )}
                <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
                  {fmtRelative(mod.created_at)}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Details View */}
      <div style={{ flex: 1, padding: "28px 36px", overflow: "auto", background: "var(--bg-base)" }}>
        {!selected ? (
          <div className="page-empty">
            <div className="page-empty-desc">Select a model from the list to view its mathematical parameters and performance telemetry.</div>
          </div>
        ) : (
          <div style={{ maxWidth: 880, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24 }}>
            {/* Header Card */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 16, borderBottom: "1px solid var(--border-dim)" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span className="badge badge-active" style={{ fontSize: 11 }}>{selected.kind?.toUpperCase()}</span>
                  <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{selected.symbol}</span>
                  <span style={{ fontSize: 11, color: "var(--text-ghost)" }}>·</span>
                  <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--blue-400)" }}>{selected.n_features || selected.feature_ids?.length || 0} Dimensions</span>
                </div>
                <h3 style={{ fontSize: 16, fontWeight: 500, color: "var(--text-primary)", fontFamily: "var(--font-mono)", margin: 0 }}>
                  {selected.model_id}
                </h3>
                <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>
                  Trained {new Date(selected.created_at).toLocaleString()} · Fold {selected.fold || 1}
                </div>
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => handleDeployToPaper(selected)}
                  style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 500 }}
                >
                  <span>Deploy to Paper Trading</span>
                  <span>→</span>
                </button>
                <button className="btn btn-sm btn-ghost" style={{ color: "var(--red)" }} onClick={handleDeleteModel}>
                  Delete
                </button>
              </div>
            </div>

            {/* Out-of-Sample Performance Matrix */}
            <div>
              <div className="sys-label" style={{ marginBottom: 10 }}>Out-of-Sample Validation & Statistical Rigor</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, border: "1px solid var(--border-dim)", borderRadius: 6, overflow: "hidden", background: "var(--border-dim)" }}>
                {[
                  { label: "Accuracy / Hit Rate", value: acc != null ? (acc * 100).toFixed(2) + "%" : "—", color: "var(--green)" },
                  { label: "Precision", value: prec != null ? prec.toFixed(3) : "—" },
                  { label: "Recall", value: rec != null ? rec.toFixed(3) : "—" },
                  { label: "F1 Score", value: f1 != null ? f1.toFixed(3) : "—" },
                  { label: "AUROC", value: auroc != null ? auroc.toFixed(3) : "—" },
                  { label: "Log Loss", value: logloss != null ? logloss.toFixed(3) : "—" },
                  { label: "Brier Score", value: brier != null ? brier.toFixed(4) : "—" },
                  { label: "Information Coeff (IC)", value: ic != null ? (ic > 0 ? "+" : "") + ic.toFixed(4) : "—", color: ic != null && ic > 0 ? "var(--green)" : undefined },
                ].map((s, i) => (
                  <div key={i} style={{ padding: "14px 16px", background: "var(--bg-elevated)" }}>
                    <div className="stat-label" style={{ fontSize: 10 }}>{s.label}</div>
                    <div className="stat-value" style={{ fontSize: 15, marginTop: 4, color: s.color || "var(--text-primary)" }}>{s.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Confusion Matrix (if present) */}
            {cm && (
              <div>
                <div className="sys-label" style={{ marginBottom: 10 }}>Out-of-Sample Confusion Matrix</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, maxWidth: 360 }}>
                  <div style={{ padding: "10px 14px", background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>True Positives (TP)</div>
                    <div style={{ fontSize: 16, fontWeight: 500, color: "var(--green)", fontFamily: "var(--font-mono)" }}>{cm.tp}</div>
                  </div>
                  <div style={{ padding: "10px 14px", background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>False Positives (FP)</div>
                    <div style={{ fontSize: 16, fontWeight: 500, color: "var(--red)", fontFamily: "var(--font-mono)" }}>{cm.fp}</div>
                  </div>
                  <div style={{ padding: "10px 14px", background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>False Negatives (FN)</div>
                    <div style={{ fontSize: 16, fontWeight: 500, color: "var(--red)", fontFamily: "var(--font-mono)" }}>{cm.fn}</div>
                  </div>
                  <div style={{ padding: "10px 14px", background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 4 }}>
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>True Negatives (TN)</div>
                    <div style={{ fontSize: 16, fontWeight: 500, color: "var(--green)", fontFamily: "var(--font-mono)" }}>{cm.tn}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Feature Importance Leaderboard */}
            {selected.feature_importance && selected.feature_importance.length > 0 && (
              <div>
                <div className="sys-label" style={{ marginBottom: 10 }}>Feature Importance Leaderboard (Top Predictors)</div>
                <div style={{ border: "1px solid var(--border-dim)", borderRadius: 6, overflow: "hidden", background: "var(--bg-surface)" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: "var(--bg-elevated)", borderBottom: "1px solid var(--border-dim)", textAlign: "left" }}>
                        <th style={{ padding: "8px 14px", width: 40, color: "var(--text-tertiary)" }}>#</th>
                        <th style={{ padding: "8px 14px", color: "var(--text-secondary)" }}>Feature Dimension</th>
                        <th style={{ padding: "8px 14px", width: 140, color: "var(--text-secondary)" }}>Relative Weight</th>
                        <th style={{ padding: "8px 14px", width: 80, textAlign: "right", color: "var(--text-secondary)" }}>Importance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selected.feature_importance.slice(0, 12).map((f, idx) => {
                        const maxImp = selected.feature_importance[0]?.importance || 1;
                        const pct = Math.min(100, Math.max(4, (f.importance / maxImp) * 100));
                        return (
                          <tr key={idx} style={{ borderBottom: "1px solid var(--border-dim)" }}>
                            <td style={{ padding: "8px 14px", color: "var(--text-ghost)", fontFamily: "var(--font-mono)" }}>{idx + 1}</td>
                            <td style={{ padding: "8px 14px", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                              <div>{f.id}</div>
                              {f.name && f.name !== f.id && <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>{f.name}</div>}
                            </td>
                            <td style={{ padding: "8px 14px" }}>
                              <div style={{ height: 6, width: "100%", background: "var(--bg-base)", borderRadius: 3, overflow: "hidden" }}>
                                <div style={{ height: "100%", width: `${pct}%`, background: "var(--blue-400)", borderRadius: 3 }} />
                              </div>
                            </td>
                            <td style={{ padding: "8px 14px", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>
                              {(f.importance * 100).toFixed(2)}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Feature Matrix Dimension Inspector */}
            {selected.feature_ids && selected.feature_ids.length > 0 && (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <div className="sys-label" style={{ margin: 0 }}>
                    Feature Dimension Set ({selected.feature_ids.length} Total Dimensions)
                  </div>
                  <input
                    type="text"
                    placeholder="Search feature IDs…"
                    value={featureSearch}
                    onChange={e => setFeatureSearch(e.target.value)}
                    style={{
                      padding: "4px 10px", fontSize: 11, background: "var(--bg-surface)",
                      border: "1px solid var(--border-dim)", borderRadius: 4, color: "var(--text-primary)",
                      fontFamily: "var(--font-mono)", width: 180
                    }}
                  />
                </div>
                <div style={{
                  maxHeight: 180, overflowY: "auto", padding: 12, background: "var(--bg-surface)",
                  border: "1px solid var(--border-dim)", borderRadius: 6, display: "flex", flexWrap: "wrap", gap: 6
                }}>
                  {filteredFeatures.map((fid, i) => (
                    <span key={i} style={{
                      padding: "3px 8px", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)",
                      borderRadius: 3, fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-secondary)"
                    }}>
                      {fid}
                    </span>
                  ))}
                  {filteredFeatures.length === 0 && (
                    <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>No matching feature IDs found.</span>
                  )}
                </div>
              </div>
            )}

            {/* Model Hyperparameters & Configuration */}
            {selected.hyperparams && (
              <div>
                <div className="sys-label" style={{ marginBottom: 10 }}>Hyperparameter Specification</div>
                <div style={{
                  padding: "12px 16px", background: "var(--bg-surface)", border: "1px solid var(--border-dim)",
                  borderRadius: 6, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-secondary)"
                }}>
                  <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                    {JSON.stringify(selected.hyperparams, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   2. MODEL LABORATORY (Feature Selection & Rigorous Training)
   ═══════════════════════════════════════════════════════════════════════════ */
function ModelLaboratory({ onDeploy }) {
  const { dispatch } = useAtlas();
  const [modelType, setModelType] = useState("xgboost");
  const [horizon, setHorizon] = useState(5);
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [provider, setProvider] = useState("binance");
  const [featurePack, setFeaturePack] = useState("core_925");
  const [availableFeatures, setAvailableFeatures] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Load feature registry definitions
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/registry/features`).then(res => {
      if (alive) setAvailableFeatures(res.data || []);
    }).catch(() => {});
    return () => { alive = false; };
  }, []);

  // Compute selected feature IDs according to chosen pack
  const selectedFeatureIds = useMemo(() => {
    if (!availableFeatures.length) return [];
    switch (featurePack) {
      case "all_1039":
        return availableFeatures.map(f => f.id);
      case "core_925":
        return availableFeatures.filter(f => f.layer >= 1 && f.layer <= 4).map(f => f.id);
      case "deriv_114":
        return availableFeatures.filter(f => f.layer === 5 || f.module === "futures" || f.module === "options").map(f => f.id);
      case "futures_69":
        return availableFeatures.filter(f => f.module === "futures").map(f => f.id);
      case "options_45":
        return availableFeatures.filter(f => f.module === "options").map(f => f.id);
      case "l1_612":
        return availableFeatures.filter(f => f.layer === 1).map(f => f.id);
      case "l2_151":
        return availableFeatures.filter(f => f.layer === 2).map(f => f.id);
      case "l3_90":
        return availableFeatures.filter(f => f.layer === 3).map(f => f.id);
      case "l4_72":
        return availableFeatures.filter(f => f.layer === 4).map(f => f.id);
      case "fast_60":
        return availableFeatures.filter(f => f.module === "price" && f.perspective !== "Magnitude").slice(0, 60).map(f => f.id);
      default:
        return availableFeatures.map(f => f.id);
    }
  }, [availableFeatures, featurePack]);

  const handleTrain = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const payload = {
        provider,
        symbol,
        interval: "1d",
        period: "2y",
        horizon: parseInt(horizon, 10),
        model: modelType,
        feature_ids: selectedFeatureIds.length > 0 ? selectedFeatureIds : undefined
      };
      
      const res = await axios.post(`${API}/predict/train`, payload);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail ? (typeof err.response.data.detail === 'string' ? err.response.data.detail : JSON.stringify(err.response.data.detail)) : err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeployToPaper = () => {
    const modelId = result?.registered_model_id || `${modelType}_${symbol}_${horizon}`;
    sessionStorage.setItem("atlas_prefill_model_id", modelId);
    dispatch({ type: "SET_VIEW", payload: "paper-trading" });
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Configuration Column */}
      <div style={{ width: 380, flexShrink: 0, borderRight: "1px solid var(--border-dim)", padding: "24px 28px", overflow: "auto" }}>
        <div style={{ marginBottom: 28 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>Architecture & Asset</div>
          
          <div className="input-group">
            <label className="input-label">Model Architecture</label>
            <select className="input" value={modelType} onChange={e => setModelType(e.target.value)}>
              <option value="xgboost">XGBoost (Gradient Boosted Decision Trees)</option>
              <option value="randomforest">Random Forest Classifier (Ensemble)</option>
              <option value="logreg">Logistic Regression (L2 Regularized)</option>
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
            <label className="input-label">Prediction Horizon (Bars Forward)</label>
            <input type="number" min="1" max="50" className="input" value={horizon} onChange={e => setHorizon(e.target.value)} />
          </div>
        </div>

        {/* Feature Dimension Selector */}
        <div style={{ marginBottom: 28 }}>
          <div className="sys-label" style={{ marginBottom: 8 }}>Feature Dimensions & Layers</div>
          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 10 }}>
            Select the causal feature layers passed to the training pipeline:
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {[
              { id: "all_1039", name: "Unified Market Matrix", count: "1,039 Dimensions", desc: "All 925 Spot Core + 114 Futures & Options features" },
              { id: "core_925", name: "Core L1–L4 Spot Matrix", count: "925 Features", desc: "All physical, cross-asset, regime & representation dimensions" },
              { id: "deriv_114",name: "Derivatives Extensions", count: "114 Features", desc: "69 Perpetual Futures + 45 Options Greeks & Vol Surface" },
              { id: "futures_69", name: "Futures: Perpetuals & CVD", count: "69 Features", desc: "Funding rates, CVD volume delta, open interest, book skew" },
              { id: "options_45", name: "Options: Vol Surface & Greeks", count: "45 Features", desc: "ATM IV, risk reversal skew, GEX, vanna, volga, max pain" },
              { id: "l1_612",   name: "Layer 1: Physical Measurement", count: "612 Features", desc: "Volatility (CC, GK, YZ), order flow, wavelets, entropy" },
              { id: "l2_151",   name: "Layer 2: Cross-Asset Dynamics", count: "151 Features", desc: "Cointegration spreads, relative strength, lead-lag" },
              { id: "l3_90",    name: "Layer 3: Market Regime & Chaos", count: "90 Features", desc: "Hurst exponents, vortex, structural volatility states" },
              { id: "l4_72",    name: "Layer 4: Representation & Memory", count: "72 Features", desc: "Fractional differentiation (d≈0.4), PCA components" },
              { id: "fast_60",  name: "Price & Microstructure Fast Subset", count: "60 Features", desc: "Rapid prototyping subset" },
            ].map(pack => {
              const active = featurePack === pack.id;
              return (
                <div
                  key={pack.id}
                  onClick={() => setFeaturePack(pack.id)}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 4,
                    border: `1px solid ${active ? "var(--blue-500)" : "var(--border-dim)"}`,
                    background: active ? "rgba(66, 106, 230, 0.08)" : "var(--bg-surface)",
                    cursor: "pointer",
                    transition: "all 120ms"
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: 12, fontWeight: 500, color: active ? "var(--text-primary)" : "var(--text-secondary)" }}>
                      {pack.name}
                    </span>
                    <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: active ? "var(--blue-400)" : "var(--text-tertiary)" }}>
                      {pack.count}
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-ghost)", marginTop: 2 }}>{pack.desc}</div>
                </div>
              );
            })}
          </div>

          <div style={{ marginTop: 10, fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--green)", display: "flex", alignItems: "center", gap: 6 }}>
            <span>✓ Invariant:</span>
            <span>{selectedFeatureIds.length || 1039} Causal dimensions selected (Zero lookahead bias)</span>
          </div>
        </div>

        <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center", fontWeight: 500 }} onClick={handleTrain} disabled={loading}>
          {loading ? "Training Model in Background…" : `Dispatch Training Job (${selectedFeatureIds.length || 1039} Dimensions)`}
        </button>

        {error && (
          <div style={{ marginTop: 16, padding: "12px 16px", background: "var(--red-muted)", border: "1px solid rgba(220,64,75,0.2)", borderRadius: 4, fontSize: 12, color: "var(--red)" }}>
            {error}
          </div>
        )}
      </div>

      {/* Output Column */}
      <div style={{ flex: 1, padding: "28px 36px", overflow: "auto", background: "var(--bg-base)" }}>
        {!result && !loading && (
          <div className="page-empty">
            <div className="page-empty-title">Ready for Training</div>
            <div className="page-empty-desc">
              Select model architecture, feature dimension set, and target asset, then dispatch a training job.
            </div>
          </div>
        )}

        {loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 800, margin: "0 auto" }}>
            <div style={{ padding: "16px 20px", background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 6, display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ width: 12, height: 12, borderRadius: "50%", background: "var(--blue-400)", animation: "pulse 1.2s infinite" }} />
              <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                Computing causal matrix across {selectedFeatureIds.length || 925} dimensions and fitting {modelType.toUpperCase()}…
              </div>
            </div>
            <div className="skeleton" style={{ height: 140, borderRadius: 6 }} />
            <div className="skeleton" style={{ height: 280, borderRadius: 6 }} />
          </div>
        )}

        {result && result.error && (
          <div style={{ maxWidth: 800, margin: "0 auto" }}>
            <div style={{ padding: 24, backgroundColor: "var(--bg-elevated)", border: "1px solid var(--red)", borderRadius: 6 }}>
              <h3 style={{ fontSize: 16, color: "var(--red)", marginBottom: 8, fontWeight: 500 }}>Training Job Failed</h3>
              <p style={{ color: "var(--text-secondary)", margin: 0, fontFamily: "var(--font-mono)", fontSize: 12 }}>{result.error}</p>
            </div>
          </div>
        )}

        {result && !result.error && (
          <div style={{ maxWidth: 840, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24 }}>
            {/* Header Result */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 16, borderBottom: "1px solid var(--border-dim)" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span className="badge badge-active">{modelType.toUpperCase()}</span>
                  <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{symbol}</span>
                  <span style={{ fontSize: 11, color: "var(--green)", fontFamily: "var(--font-mono)" }}>● Checkpoint Saved</span>
                </div>
                <h3 style={{ fontSize: 18, fontWeight: 500, color: "var(--text-primary)", margin: 0 }}>
                  Training & Out-of-Sample Validation Completed
                </h3>
                <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>
                  Evaluated on {result.n_test} test bars · {result.features_used?.length || selectedFeatureIds.length || 0} features used
                </div>
              </div>
              <button
                className="btn btn-primary"
                onClick={handleDeployToPaper}
                style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 500 }}
              >
                <span>Deploy to Paper Trading</span>
                <span>→</span>
              </button>
            </div>

            {/* Validation Metrics Grid */}
            <div>
              <div className="sys-label" style={{ marginBottom: 10 }}>Validation Metrics (Temporal Out-of-Sample)</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 1, border: "1px solid var(--border-dim)", borderRadius: 6, overflow: "hidden", background: "var(--border-dim)" }}>
                {[
                  { label: "Accuracy", value: result.metrics?.accuracy ? (result.metrics.accuracy * 100).toFixed(2) + "%" : "—", color: "var(--green)" },
                  { label: "Precision", value: result.metrics?.precision ? result.metrics.precision.toFixed(3) : "—" },
                  { label: "Recall", value: result.metrics?.recall ? result.metrics.recall.toFixed(3) : "—" },
                  { label: "AUROC", value: result.metrics?.roc_auc ? result.metrics.roc_auc.toFixed(3) : "—" },
                  { label: "Log Loss", value: result.metrics?.log_loss ? result.metrics.log_loss.toFixed(3) : "—" },
                ].map((s, i) => (
                  <div key={i} style={{ padding: "14px 16px", background: "var(--bg-elevated)" }}>
                    <div className="stat-label" style={{ fontSize: 10 }}>{s.label}</div>
                    <div className="stat-value" style={{ fontSize: 15, marginTop: 4, color: s.color || "var(--text-primary)" }}>{s.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Inference State on Current Bar */}
            {result.prediction && (
              <div>
                <div className="sys-label" style={{ marginBottom: 10 }}>Current Market State Inference (T_0)</div>
                <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 6, padding: "16px 20px", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
                  <div>
                    <div className="stat-label" style={{ fontSize: 10 }}>Directional Signal</div>
                    <div style={{ fontSize: 18, fontWeight: 600, color: result.prediction.direction === "UP" ? "var(--green)" : "var(--red)", marginTop: 4, fontFamily: "var(--font-mono)" }}>
                      {result.prediction.direction}
                    </div>
                  </div>
                  <div>
                    <div className="stat-label" style={{ fontSize: 10 }}>Model Confidence</div>
                    <div style={{ fontSize: 18, fontWeight: 600, color: "var(--text-primary)", marginTop: 4, fontFamily: "var(--font-mono)" }}>
                      {(result.prediction.confidence * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="stat-label" style={{ fontSize: 10 }}>Expected Volatility ({horizon} Bars)</div>
                    <div style={{ fontSize: 18, fontWeight: 600, color: "var(--text-primary)", marginTop: 4, fontFamily: "var(--font-mono)" }}>
                      {result.expected_move?.sigma_pct != null ? `${result.expected_move.sigma_pct}%` : "—"}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Feature Importance Leaderboard */}
            {result.top_features && result.top_features.length > 0 && (
              <div>
                <div className="sys-label" style={{ marginBottom: 10 }}>Top Predictors (Feature Importance)</div>
                <div style={{ border: "1px solid var(--border-dim)", borderRadius: 6, overflow: "hidden", background: "var(--bg-surface)" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: "var(--bg-elevated)", borderBottom: "1px solid var(--border-dim)", textAlign: "left" }}>
                        <th style={{ padding: "8px 14px", width: 40, color: "var(--text-tertiary)" }}>#</th>
                        <th style={{ padding: "8px 14px", color: "var(--text-secondary)" }}>Feature ID</th>
                        <th style={{ padding: "8px 14px", width: 140, color: "var(--text-secondary)" }}>Relative Weight</th>
                        <th style={{ padding: "8px 14px", width: 80, textAlign: "right", color: "var(--text-secondary)" }}>Importance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.top_features.slice(0, 10).map((f, idx) => {
                        const maxImp = result.top_features[0]?.importance || 1;
                        const pct = Math.min(100, Math.max(4, (f.importance / maxImp) * 100));
                        return (
                          <tr key={idx} style={{ borderBottom: "1px solid var(--border-dim)" }}>
                            <td style={{ padding: "8px 14px", color: "var(--text-ghost)", fontFamily: "var(--font-mono)" }}>{idx + 1}</td>
                            <td style={{ padding: "8px 14px", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                              <div>{f.id}</div>
                              {f.name && f.name !== f.id && <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>{f.name}</div>}
                            </td>
                            <td style={{ padding: "8px 14px" }}>
                              <div style={{ height: 6, width: "100%", background: "var(--bg-base)", borderRadius: 3, overflow: "hidden" }}>
                                <div style={{ height: "100%", width: `${pct}%`, background: "var(--blue-400)", borderRadius: 3 }} />
                              </div>
                            </td>
                            <td style={{ padding: "8px 14px", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>
                              {(f.importance * 100).toFixed(2)}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   3. PREDICTION HISTORY
   ═══════════════════════════════════════════════════════════════════════════ */
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

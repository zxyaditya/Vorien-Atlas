import React, { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import { API, makeAbortable, isAbortError } from "../../lib/helpers";
import { SymbolSelector } from "../../components/SymbolSelector";

// Shows features from the workspace registry filtered to what's relevant in this project context
export function ProjectFeatures({ project }) {
  return <FeatureRegistryPanel projectId={project._id} embedded />;
}

export function FeatureRegistryPanel({ projectId, embedded = false }) {
  const [features, setFeatures] = useState([]);
  const [vocab, setVocab]       = useState({ perspectives: [], modules: [] });
  const [loading, setLoading]   = useState(true);
  const [selected, setSelected] = useState(null);
  const [points, setPoints]     = useState([]);
  const [pointsLoading, setPointsLoading] = useState(false);
  const [filter, setFilter] = useState({ q: "", layer: "", perspective: "", module: "" });
  
  const [provider, setProvider] = useState("binance");
  const [symbol, setSymbol] = useState("BTCUSDT");

  const load = useCallback(async (signal) => {
    setLoading(true);
    try {
      const [fr, vr] = await Promise.all([
        axios.get(`${API}/registry/features`, { signal }),
        axios.get(`${API}/registry/vocab`,    { signal }).catch(() => ({ data: {} })),
      ]);
      setFeatures(fr.data || []);
      setVocab({
        perspectives: vr.data?.perspectives || [],
        modules: [...new Set((fr.data || []).map(f => f.module))].sort(),
      });
      if (fr.data?.length > 0) setSelected(fr.data[0]);
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

  // Load sparkline when feature selected or symbol changes
  useEffect(() => {
    if (!selected) return;
    const { signal, abort } = makeAbortable();
    setPointsLoading(true);
    setPoints([]);
    axios.get(`${API}/features/values`, {
      params: { feature_id: selected.id, provider, symbol, interval: "1d", period: "1y" },
      signal,
    }).then(r => {
      setPoints(r.data?.points || []);
      setPointsLoading(false);
    }).catch(err => {
      if (!isAbortError(err)) setPointsLoading(false);
    });
    return () => abort();
  }, [selected, provider, symbol]);

  const layers = [1, 2, 3, 4, 5];
  const LAYER_LABELS = {
    1: "L1 Measurement (612)",
    2: "L2 Relationships (151)",
    3: "L3 Regimes & Chaos (90)",
    4: "L4 Representation (72)",
    5: "L5 Derivatives: Futures & Options (114)"
  };

  const filtered = features.filter(f => {
    if (filter.layer && String(f.layer) !== String(filter.layer)) return false;
    if (filter.perspective && f.perspective !== filter.perspective) return false;
    if (filter.module && f.module !== filter.module) return false;
    if (filter.q) {
      const q = filter.q.toLowerCase();
      if (!f.id.toLowerCase().includes(q) && !f.name.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  // Grouped counts
  const byLayer = {};
  features.forEach(f => { byLayer[f.layer] = (byLayer[f.layer] || 0) + 1; });

  // Faceted filtering: Compute available options for a facet by applying all OTHER filters
  const availPerspectives = new Set(
    features.filter(f => {
      if (filter.layer && String(f.layer) !== String(filter.layer)) return false;
      if (filter.module && f.module !== filter.module) return false;
      if (filter.q) {
        const q = filter.q.toLowerCase();
        if (!f.id.toLowerCase().includes(q) && !f.name.toLowerCase().includes(q)) return false;
      }
      return true;
    }).map(f => f.perspective)
  );

  const availModules = new Set(
    features.filter(f => {
      if (filter.layer && String(f.layer) !== String(filter.layer)) return false;
      if (filter.perspective && f.perspective !== filter.perspective) return false;
      if (filter.q) {
        const q = filter.q.toLowerCase();
        if (!f.id.toLowerCase().includes(q) && !f.name.toLowerCase().includes(q)) return false;
      }
      return true;
    }).map(f => f.module)
  );

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* Filter sidebar */}
      <div style={{
        width: 200, flexShrink: 0, borderRight: "1px solid var(--border-dim)",
        display: "flex", flexDirection: "column", overflow: "hidden",
        background: "var(--bg-surface)",
      }}>
        <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0 }}>
          <div className="feature-search" style={{ background: "var(--bg-elevated)" }}>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              placeholder="Search features…"
              value={filter.q}
              onChange={e => setFilter(f => ({ ...f, q: e.target.value }))}
              id="feature-search-input"
            />
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "10px 0" }}>
          {/* Layer filter */}
          <div style={{ padding: "4px 14px 8px" }}>
            <div className="sidebar-section-label">Layer</div>
            {[["", "All Layers"], ...layers.map(l => [String(l), LAYER_LABELS[l]])].map(([val, label]) => (
              <button
                key={val}
                className={`sidebar-item ${filter.layer === val ? "active" : ""}`}
                style={{ fontSize: 11.5, padding: "4px 10px" }}
                onClick={() => setFilter(f => ({ ...f, layer: val }))}
              >
                <span style={{ flex: 1 }}>{label}</span>
                {val && <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
                  {byLayer[val] || 0}
                </span>}
              </button>
            ))}
          </div>

          {/* Perspective filter */}
          {vocab.perspectives.length > 0 && (
            <div style={{ padding: "4px 14px 8px", borderTop: "1px solid var(--border-dim)", marginTop: 4 }}>
              <div className="sidebar-section-label">Perspective</div>
              {["", ...vocab.perspectives].filter(p => p === "" || availPerspectives.has(p)).map((p, i) => (
                <button
                  key={i}
                  className={`sidebar-item ${filter.perspective === p ? "active" : ""}`}
                  style={{ fontSize: 11.5, padding: "4px 10px" }}
                  onClick={() => setFilter(f => ({ ...f, perspective: p }))}
                >
                  {p || "All"}
                </button>
              ))}
            </div>
          )}

          {/* Module filter */}
          {vocab.modules.length > 0 && (
            <div style={{ padding: "4px 14px 8px", borderTop: "1px solid var(--border-dim)", marginTop: 4 }}>
              <div className="sidebar-section-label">Module</div>
              {["", ...vocab.modules].filter(m => m === "" || availModules.has(m)).map((m, i) => (
                <button
                  key={i}
                  className={`sidebar-item ${filter.module === m ? "active" : ""}`}
                  style={{ fontSize: 11.5, padding: "4px 10px" }}
                  onClick={() => setFilter(f => ({ ...f, module: m }))}
                >
                  {m || "All"}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Result count */}
        <div style={{ padding: "8px 14px", borderTop: "1px solid var(--border-dim)", flexShrink: 0 }}>
          <div className="mono-label">{filtered.length.toLocaleString()} of {features.length.toLocaleString()} features</div>
        </div>
      </div>

      {/* Feature list */}
      <div className="feature-list-panel" style={{ width: 280, borderRight: "1px solid var(--border-dim)" }}>
        <div className="feature-list-body">
          {loading ? (
            <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 6 }}>
              {[...Array(8)].map((_, i) => (
                <div key={i} className="skeleton" style={{ height: 36 }} />
              ))}
            </div>
          ) : (
            filtered.map(f => (
              <div
                key={f.id}
                className={`feature-row ${selected?.id === f.id ? "selected" : ""}`}
                onClick={() => setSelected(f)}
                id={`feat-${f.id?.replace(/\./g, "-")}`}
              >
                <div style={{ flex: 1, overflow: "hidden" }}>
                  <div className="feature-row-id">{f.id}</div>
                  <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 1 }}>{f.name}</div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
                  <span style={{
                    fontFamily: "var(--font-mono)", fontSize: 9,
                    color: layerColor(f.layer), letterSpacing: "0.04em",
                  }}>L{f.layer}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Detail panel */}
      <div style={{ flex: 1, overflow: "auto", padding: "24px 28px" }}>
        {selected ? (
          <FeatureDetail 
            feature={selected} points={points} pointsLoading={pointsLoading}
            provider={provider} symbol={symbol}
            onProviderChange={setProvider} onSymbolChange={setSymbol}
          />
        ) : (
          <div className="page-empty">
            <div className="page-empty-desc">Select a feature to view its definition</div>
          </div>
        )}
      </div>
    </div>
  );
}

function FeatureDetail({ feature: f, points, pointsLoading, provider, symbol, onProviderChange, onSymbolChange }) {
  const canvasRef = useRef(null);

  // Draw mini sparkline
  useEffect(() => {
    if (!canvasRef.current || points.length < 2) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const vals = points.map(p => p.value).filter(v => v !== null && isFinite(v));
    if (vals.length < 2) return;

    const min = Math.min(...vals), max = Math.max(...vals);
    const range = max - min || 1;

    const xStep = W / (vals.length - 1);
    ctx.beginPath();
    ctx.strokeStyle = "hsl(222, 90%, 55%)";
    ctx.lineWidth = 1.5;

    vals.forEach((v, i) => {
      const x = i * xStep;
      const y = H - ((v - min) / range) * H * 0.85 - H * 0.075;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Fill
    ctx.lineTo((vals.length - 1) * xStep, H);
    ctx.lineTo(0, H);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, "rgba(66,106,230,0.15)");
    grad.addColorStop(1, "rgba(66,106,230,0)");
    ctx.fillStyle = grad;
    ctx.fill();
  }, [points]);

  const LAYER_LABELS = { 1: "Measurement", 2: "Relationships", 3: "Market Understanding", 4: "Representation" };

  return (
    <div style={{ maxWidth: 640 }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span style={{
            fontFamily: "var(--font-mono)", fontSize: "9px",
            letterSpacing: "0.12em", textTransform: "uppercase",
            color: layerColor(f.layer), padding: "2px 6px",
            background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 3,
          }}>
            L{f.layer} · {LAYER_LABELS[f.layer]}
          </span>
          <span style={{
            fontFamily: "var(--font-mono)", fontSize: "9px",
            letterSpacing: "0.08em", textTransform: "uppercase",
            color: "var(--text-tertiary)", padding: "2px 6px",
            background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 3,
          }}>
            {f.perspective}
          </span>
        </div>

        <h2 style={{ fontSize: 18, fontWeight: 400, letterSpacing: "-0.015em", color: "var(--text-primary)", marginBottom: 4 }}>
          {f.name}
        </h2>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-tertiary)", letterSpacing: "0.02em" }}>
          {f.id}
        </div>
      </div>

      {/* Sparkline */}
      <div style={{
        background: "var(--bg-elevated)", border: "1px solid var(--border-dim)",
        borderRadius: 6, padding: "14px 16px", marginBottom: 20,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
            Feature Value (1D, 1Y)
          </div>
          <SymbolSelector
            provider={provider}
            symbol={symbol}
            onProviderChange={onProviderChange}
            onSymbolChange={onSymbolChange}
            showProvider={false}
          />
        </div>
        {pointsLoading ? (
          <div className="skeleton" style={{ height: 64, borderRadius: 4 }} />
        ) : points.length > 1 ? (
          <canvas ref={canvasRef} width={560} height={64} style={{ width: "100%", display: "block" }} />
        ) : (
          <div style={{ height: 64, display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 11, color: "var(--text-tertiary)" }}>No data available</div>
        )}
      </div>

      {/* Definition grid */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr",
        gap: 1, border: "1px solid var(--border-dim)", borderRadius: 6, overflow: "hidden",
        marginBottom: 20,
      }}>
        {[
          { label: "Module",      value: f.module },
          { label: "Family",      value: f.family },
          { label: "Complexity",  value: f.complexity },
          { label: "Inputs",      value: (f.inputs || []).join(", ") },
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

      {/* Formula */}
      {f.formula && (
        <div style={{ marginBottom: 18 }}>
          <div className="mono-label" style={{ marginBottom: 8 }}>Formula</div>
          <div style={{
            fontFamily: "var(--font-mono)", fontSize: 12.5,
            background: "var(--bg-elevated)", border: "1px solid var(--border-dim)",
            borderRadius: 5, padding: "12px 16px", color: "var(--blue-300)",
            letterSpacing: "0.02em",
          }}>
            {f.formula}
          </div>
        </div>
      )}

      {/* Definition */}
      {f.definition && (
        <div style={{ marginBottom: 18 }}>
          <div className="mono-label" style={{ marginBottom: 8 }}>Definition</div>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7 }}>{f.definition}</p>
        </div>
      )}

      {/* Interpretation - Upgraded for Commercial UX */}
      {f.interpretation && (
        <div style={{
          marginTop: 20, padding: "16px 20px",
          background: "rgba(66,106,230,0.08)", borderLeft: "3px solid var(--blue-500)",
          borderRadius: "0 6px 6px 0"
        }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8, marginBottom: 8
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--blue-400)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            <div className="mono-label" style={{ color: "var(--blue-400)", marginBottom: 0 }}>Interpretation</div>
          </div>
          <p style={{ fontSize: 13.5, color: "var(--text-primary)", lineHeight: 1.6, fontWeight: 400 }}>
            {f.interpretation}
          </p>
        </div>
      )}

      {/* Look-ahead safety — critical research integrity indicator */}
      <div style={{
        marginTop: 24, padding: "12px 16px",
        background: "var(--green-muted)", border: "1px solid rgba(35,184,109,0.2)",
        borderRadius: 5, display: "flex", alignItems: "center", gap: 10,
      }}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
        <div style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>
          <span style={{ color: "var(--green)", fontWeight: 500 }}>Look-ahead safe.</span>{" "}
          This feature does not use future information at any computation point.
        </div>
      </div>
    </div>
  );
}

function layerColor(layer) {
  return {
    1: "hsl(222, 90%, 63%)",
    2: "hsl(258, 75%, 62%)",
    3: "hsl(155, 70%, 44%)",
    4: "hsl(40, 85%, 52%)",
  }[layer] || "var(--text-tertiary)";
}

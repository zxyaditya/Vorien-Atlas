import React, { useState, useMemo, useCallback, useEffect } from "react";
import axios from "axios";
import { API, makeAbortable, isAbortError } from "../lib/helpers";

const LAYER_LABELS = {
  1: "L1 · Measurement",
  2: "L2 · Relationships",
  3: "L3 · Market Understanding",
  4: "L4 · Representation",
};

const LAYER_COLORS = {
  1: "hsl(222, 90%, 63%)",
  2: "hsl(258, 75%, 62%)",
  3: "hsl(155, 70%, 44%)",
  4: "hsl(40, 85%, 52%)",
};

const PRESETS = [
  { label: "Top 60 (Default)", desc: "Balanced set for ML training", filter: (f) => true, max: 60 },
  { label: "All L1 Measurement", desc: "Raw price-derived features", filter: (f) => f.layer === 1 },
  { label: "All L2 Relationships", desc: "Cross-asset & relative features", filter: (f) => f.layer === 2 },
  { label: "All L3 Understanding", desc: "Regime & market structure", filter: (f) => f.layer === 3 },
  { label: "All L4 Representation", desc: "Compressed / embedding features", filter: (f) => f.layer === 4 },
  { label: "Momentum Suite", desc: "Motion & trend features", filter: (f) => f.perspective === "Motion" || f.family?.toLowerCase().includes("momentum") },
  { label: "Statistics Suite", desc: "Statistical measures", filter: (f) => f.perspective === "Statistics" || f.perspective === "Distribution" },
];

/**
 * FeatureSelector — Industry-grade feature picker for 925+ features.
 *
 * Props:
 *   selectedIds: string[]           — currently selected feature IDs
 *   onChange: (ids: string[]) => void — called when selection changes
 *   maxHeight?: number              — max height of the component (default 480)
 */
export function FeatureSelector({ selectedIds = [], onChange, maxHeight = 480 }) {
  const [allFeatures, setAllFeatures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expandedGroups, setExpandedGroups] = useState(new Set());
  const [activePreset, setActivePreset] = useState(null);
  const [showPresets, setShowPresets] = useState(false);

  // Fetch all features once
  useEffect(() => {
    const { signal, abort } = makeAbortable();
    setLoading(true);
    axios.get(`${API}/registry/features`, { signal })
      .then(res => {
        setAllFeatures(res.data || []);
        setLoading(false);
      })
      .catch(err => {
        if (!isAbortError(err)) {
          console.error("FeatureSelector: failed to load features", err);
          setLoading(false);
        }
      });
    return () => abort();
  }, []);

  // Filter features by search
  const filtered = useMemo(() => {
    if (!search.trim()) return allFeatures;
    const q = search.toLowerCase();
    return allFeatures.filter(f =>
      f.id.toLowerCase().includes(q) ||
      f.name.toLowerCase().includes(q) ||
      (f.module || "").toLowerCase().includes(q) ||
      (f.family || "").toLowerCase().includes(q)
    );
  }, [allFeatures, search]);

  // Group: Layer → Module → features
  const grouped = useMemo(() => {
    const map = {};
    filtered.forEach(f => {
      const lk = f.layer || 0;
      const mk = f.module || "other";
      if (!map[lk]) map[lk] = {};
      if (!map[lk][mk]) map[lk][mk] = [];
      map[lk][mk].push(f);
    });
    // Sort layers
    const sorted = Object.keys(map).sort((a, b) => Number(a) - Number(b)).map(lk => ({
      layer: Number(lk),
      modules: Object.keys(map[lk]).sort().map(mk => ({
        module: mk,
        features: map[lk][mk].sort((a, b) => a.id.localeCompare(b.id)),
      })),
    }));
    return sorted;
  }, [filtered]);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const toggleFeature = useCallback((fid) => {
    const next = selectedSet.has(fid)
      ? selectedIds.filter(id => id !== fid)
      : [...selectedIds, fid];
    onChange(next);
  }, [selectedIds, selectedSet, onChange]);

  const toggleGroup = useCallback((feats) => {
    const ids = feats.map(f => f.id);
    const allSelected = ids.every(id => selectedSet.has(id));
    let next;
    if (allSelected) {
      next = selectedIds.filter(id => !ids.includes(id));
    } else {
      const toAdd = ids.filter(id => !selectedSet.has(id));
      next = [...selectedIds, ...toAdd];
    }
    onChange(next);
  }, [selectedIds, selectedSet, onChange]);

  const selectAll = useCallback(() => {
    onChange(filtered.map(f => f.id));
  }, [filtered, onChange]);

  const deselectAll = useCallback(() => {
    onChange([]);
  }, [onChange]);

  const applyPreset = useCallback((preset) => {
    let matching = allFeatures.filter(preset.filter);
    if (preset.max) matching = matching.slice(0, preset.max);
    onChange(matching.map(f => f.id));
    setActivePreset(preset.label);
    setShowPresets(false);
  }, [allFeatures, onChange]);

  const toggleExpand = (key) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const expandAll = () => {
    const keys = [];
    grouped.forEach(lg => {
      keys.push(`L${lg.layer}`);
      lg.modules.forEach(mg => keys.push(`L${lg.layer}-${mg.module}`));
    });
    setExpandedGroups(new Set(keys));
  };

  const collapseAll = () => setExpandedGroups(new Set());

  if (loading) {
    return (
      <div style={{ border: "1px solid var(--border-dim)", borderRadius: 6, padding: 16, background: "var(--bg-surface)" }}>
        <div className="skeleton" style={{ height: 32, marginBottom: 8 }} />
        <div className="skeleton" style={{ height: 200 }} />
      </div>
    );
  }

  return (
    <div style={{ border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden", background: "var(--bg-surface)" }}>
      {/* Header bar */}
      <div style={{
        padding: "10px 14px",
        borderBottom: "1px solid var(--border-dim)",
        display: "flex", alignItems: "center", gap: 10,
        background: "var(--bg-elevated)",
      }}>
        {/* Search */}
        <div style={{
          display: "flex", alignItems: "center", gap: 6, flex: 1,
          background: "var(--bg-surface)", border: "1px solid var(--border-dim)",
          borderRadius: 4, padding: "5px 10px",
        }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            placeholder="Search 925+ features…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              background: "none", border: "none", outline: "none",
              color: "var(--text-primary)", fontSize: 12, flex: 1,
              fontFamily: "var(--font-sans)",
            }}
            id="feature-selector-search"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              style={{ background: "none", border: "none", color: "var(--text-tertiary)", cursor: "pointer", fontSize: 11, padding: "0 2px" }}
            >✕</button>
          )}
        </div>

        {/* Preset dropdown */}
        <div style={{ position: "relative" }}>
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => setShowPresets(!showPresets)}
            style={{ fontSize: 11, padding: "4px 10px", whiteSpace: "nowrap" }}
          >
            {activePreset || "Presets ▾"}
          </button>
          {showPresets && (
            <div style={{
              position: "absolute", top: "100%", right: 0, marginTop: 4,
              background: "var(--bg-overlay)", border: "1px solid var(--border-base)",
              borderRadius: 6, padding: 6, zIndex: 100, width: 240,
              boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
            }}>
              {PRESETS.map(p => (
                <button
                  key={p.label}
                  onClick={() => applyPreset(p)}
                  style={{
                    display: "block", width: "100%", textAlign: "left",
                    padding: "8px 10px", background: "none", border: "none",
                    borderRadius: 4, cursor: "pointer", color: "var(--text-primary)",
                    fontSize: 12,
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = "var(--bg-hover)"}
                  onMouseLeave={e => e.currentTarget.style.background = "none"}
                >
                  <div style={{ fontWeight: 500 }}>{p.label}</div>
                  <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 2 }}>{p.desc}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Bulk actions */}
        <button className="btn btn-sm btn-ghost" onClick={selectAll} style={{ fontSize: 10, padding: "4px 8px" }}>All</button>
        <button className="btn btn-sm btn-ghost" onClick={deselectAll} style={{ fontSize: 10, padding: "4px 8px" }}>None</button>
      </div>

      {/* Selected chips row */}
      {selectedIds.length > 0 && (
        <div style={{
          padding: "8px 14px", borderBottom: "1px solid var(--border-dim)",
          display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap",
          background: "var(--bg-surface)",
        }}>
          <span style={{
            fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-accent)",
            letterSpacing: "0.04em", fontWeight: 500, marginRight: 4,
          }}>
            {selectedIds.length} selected
          </span>
          {selectedIds.length <= 12 && selectedIds.map(id => (
            <span key={id} style={{
              fontSize: 10, padding: "2px 6px", borderRadius: 3,
              background: "rgba(66,106,230,0.12)", color: "var(--blue-300)",
              fontFamily: "var(--font-mono)", display: "inline-flex", alignItems: "center", gap: 4,
            }}>
              {id}
              <button
                onClick={() => toggleFeature(id)}
                style={{ background: "none", border: "none", color: "var(--blue-400)", cursor: "pointer", fontSize: 9, padding: 0, lineHeight: 1 }}
              >✕</button>
            </span>
          ))}
          {selectedIds.length > 12 && (
            <span style={{ fontSize: 10, color: "var(--text-tertiary)" }}>
              (showing count only for large selections)
            </span>
          )}
        </div>
      )}

      {/* Expand/collapse controls */}
      <div style={{
        padding: "6px 14px", borderBottom: "1px solid var(--border-dim)",
        display: "flex", gap: 8, alignItems: "center",
      }}>
        <button onClick={expandAll} style={{ background: "none", border: "none", fontSize: 10, color: "var(--text-tertiary)", cursor: "pointer", padding: 0 }}>
          Expand All
        </button>
        <span style={{ color: "var(--border-base)" }}>·</span>
        <button onClick={collapseAll} style={{ background: "none", border: "none", fontSize: 10, color: "var(--text-tertiary)", cursor: "pointer", padding: 0 }}>
          Collapse All
        </button>
        <span style={{ marginLeft: "auto", fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
          {filtered.length} features
        </span>
      </div>

      {/* Feature tree */}
      <div style={{ maxHeight: maxHeight, overflowY: "auto" }}>
        {filtered.length === 0 ? (
          <div style={{ padding: "32px 16px", textAlign: "center", color: "var(--text-tertiary)", fontSize: 12 }}>
            No features match "{search}"
          </div>
        ) : (
          grouped.map(lg => {
            const layerKey = `L${lg.layer}`;
            const layerExpanded = expandedGroups.has(layerKey);
            const allLayerFeats = lg.modules.flatMap(m => m.features);
            const layerSelectedCount = allLayerFeats.filter(f => selectedSet.has(f.id)).length;
            const layerAllSelected = layerSelectedCount === allLayerFeats.length && allLayerFeats.length > 0;

            return (
              <div key={lg.layer}>
                {/* Layer header */}
                <div
                  onClick={() => toggleExpand(layerKey)}
                  style={{
                    padding: "8px 14px", display: "flex", alignItems: "center", gap: 8,
                    cursor: "pointer", background: "var(--bg-elevated)",
                    borderBottom: "1px solid var(--border-dim)",
                    position: "sticky", top: 0, zIndex: 10,
                  }}
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="2" style={{ transform: layerExpanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 100ms" }}>
                    <polyline points="9 18 15 12 9 6"/>
                  </svg>
                  <div style={{
                    width: 6, height: 6, borderRadius: "50%",
                    background: LAYER_COLORS[lg.layer] || "var(--text-tertiary)",
                  }} />
                  <span style={{ fontSize: 11, fontWeight: 500, color: "var(--text-primary)", flex: 1 }}>
                    {LAYER_LABELS[lg.layer] || `Layer ${lg.layer}`}
                  </span>
                  <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: layerSelectedCount > 0 ? "var(--text-accent)" : "var(--text-tertiary)" }}>
                    {layerSelectedCount}/{allLayerFeats.length}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleGroup(allLayerFeats); }}
                    style={{
                      background: "none", border: "1px solid var(--border-dim)", borderRadius: 3,
                      padding: "2px 6px", fontSize: 9, cursor: "pointer",
                      color: layerAllSelected ? "var(--blue-400)" : "var(--text-tertiary)",
                    }}
                  >
                    {layerAllSelected ? "Deselect" : "Select All"}
                  </button>
                </div>

                {/* Modules */}
                {layerExpanded && lg.modules.map(mg => {
                  const modKey = `L${lg.layer}-${mg.module}`;
                  const modExpanded = expandedGroups.has(modKey);
                  const modSelectedCount = mg.features.filter(f => selectedSet.has(f.id)).length;
                  const modAllSelected = modSelectedCount === mg.features.length && mg.features.length > 0;

                  return (
                    <div key={mg.module}>
                      {/* Module header */}
                      <div
                        onClick={() => toggleExpand(modKey)}
                        style={{
                          padding: "6px 14px 6px 32px", display: "flex", alignItems: "center", gap: 8,
                          cursor: "pointer", borderBottom: "1px solid var(--border-dim)",
                        }}
                      >
                        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="2" style={{ transform: modExpanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 100ms" }}>
                          <polyline points="9 18 15 12 9 6"/>
                        </svg>
                        <span style={{ fontSize: 11, color: "var(--text-secondary)", flex: 1, fontFamily: "var(--font-mono)", letterSpacing: "0.02em" }}>
                          {mg.module}
                        </span>
                        <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: modSelectedCount > 0 ? "var(--text-accent)" : "var(--text-ghost)" }}>
                          {modSelectedCount}/{mg.features.length}
                        </span>
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleGroup(mg.features); }}
                          style={{
                            background: "none", border: "1px solid var(--border-dim)", borderRadius: 3,
                            padding: "1px 5px", fontSize: 9, cursor: "pointer",
                            color: modAllSelected ? "var(--blue-400)" : "var(--text-ghost)",
                          }}
                        >
                          {modAllSelected ? "−" : "+"}
                        </button>
                      </div>

                      {/* Individual features */}
                      {modExpanded && mg.features.map(f => (
                        <label
                          key={f.id}
                          style={{
                            display: "flex", alignItems: "center", gap: 8,
                            padding: "5px 14px 5px 52px", cursor: "pointer",
                            borderBottom: "1px solid var(--border-dim)",
                            background: selectedSet.has(f.id) ? "rgba(66,106,230,0.04)" : "transparent",
                            transition: "background 80ms",
                          }}
                          onMouseEnter={e => { if (!selectedSet.has(f.id)) e.currentTarget.style.background = "var(--bg-hover)"; }}
                          onMouseLeave={e => { if (!selectedSet.has(f.id)) e.currentTarget.style.background = "transparent"; }}
                        >
                          <input
                            type="checkbox"
                            checked={selectedSet.has(f.id)}
                            onChange={() => toggleFeature(f.id)}
                            style={{ accentColor: "var(--blue-500)", flexShrink: 0 }}
                          />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{
                              fontSize: 11.5, color: "var(--text-primary)",
                              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                            }}>
                              {f.name}
                            </div>
                            <div style={{
                              fontSize: 9.5, fontFamily: "var(--font-mono)",
                              color: "var(--text-tertiary)", letterSpacing: "0.02em",
                            }}>
                              {f.id}
                            </div>
                          </div>
                          <span style={{
                            fontSize: 9, fontFamily: "var(--font-mono)",
                            color: LAYER_COLORS[f.layer] || "var(--text-ghost)",
                            letterSpacing: "0.04em", flexShrink: 0,
                          }}>
                            {f.perspective}
                          </span>
                        </label>
                      ))}
                    </div>
                  );
                })}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

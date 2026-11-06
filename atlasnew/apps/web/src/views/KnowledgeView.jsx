import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { API, fmtRelative, makeAbortable, isAbortError } from "../lib/helpers";
import { useAtlas } from "../store/atlasStore";

export function KnowledgeView() {
  const { dispatch } = useAtlas();
  const [notes, setNotes]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [filter, setFilter]   = useState({ q: "", type: "", status: "" });
  const [stats, setStats]     = useState({ total: 0, open: 0, resolved: 0 });

  const load = useCallback(async (signal) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/knowledge/notes`, { signal });
      const data = res.data || [];
      setNotes(data);
      setStats({
        total:    data.length,
        open:     data.filter(n => n.resolution_status === "Open").length,
        resolved: data.filter(n => n.resolution_status === "Resolved").length,
      });
      if (data.length > 0) setSelected(data[0]);
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

  const NOTE_TYPES = ["Hypothesis", "Observation", "Decision", "Finding", "Question", "Lesson", "Reference"];

  const filtered = notes.filter(n => {
    if (filter.type   && n.type !== filter.type) return false;
    if (filter.status && n.resolution_status !== filter.status) return false;
    if (filter.q) {
      const q = filter.q.toLowerCase();
      if (!n.title.toLowerCase().includes(q) && !(n.body || "").toLowerCase().includes(q)) return false;
    }
    return true;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "20px 28px 16px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div>
            <h2 className="workspace-title">Knowledge Archive</h2>
            <div className="workspace-subtitle">
              All research notes across every project — your institutional memory.
            </div>
          </div>
          {/* Stat pills */}
          <div style={{ display: "flex", gap: 12 }}>
            {[
              { label: "Total",    value: stats.total    },
              { label: "Open",     value: stats.open,    color: "var(--amber)" },
              { label: "Resolved", value: stats.resolved, color: "var(--green)" },
            ].map(s => (
              <div key={s.label} style={{ textAlign: "right" }}>
                <div style={{ fontSize: 18, fontFamily: "var(--font-mono)", color: s.color || "var(--text-primary)", fontWeight: 400 }}>{s.value}</div>
                <div className="mono-label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Search + filter bar */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8,
            background: "var(--bg-elevated)", border: "1px solid var(--border-dim)",
            borderRadius: 5, padding: "6px 12px", flex: 1, maxWidth: 340,
          }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              style={{ background: "none", border: "none", outline: "none", color: "var(--text-primary)", fontSize: 12, flex: 1, fontFamily: "var(--font-sans)" }}
              placeholder="Search all notes…"
              value={filter.q}
              onChange={e => setFilter(f => ({ ...f, q: e.target.value }))}
              id="knowledge-search"
            />
          </div>

          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {["", ...NOTE_TYPES].map(t => (
              <button
                key={t || "all"}
                className={`btn btn-sm ${filter.type === t ? "btn-secondary" : "btn-ghost"}`}
                style={{ padding: "3px 8px", fontSize: 10.5 }}
                onClick={() => setFilter(f => ({ ...f, type: t }))}
              >
                {t || "All"}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", gap: 4 }}>
            {[["", "Any Status"], ["Open", "Open"], ["Resolved", "Resolved"]].map(([val, label]) => (
              <button
                key={val}
                className={`btn btn-sm ${filter.status === val ? "btn-secondary" : "btn-ghost"}`}
                style={{ padding: "3px 8px", fontSize: 10.5 }}
                onClick={() => setFilter(f => ({ ...f, status: val }))}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* List */}
        <div style={{ width: 340, borderRight: "1px solid var(--border-dim)", overflow: "auto", flexShrink: 0 }}>
          {loading ? (
            <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
              {[...Array(6)].map((_, i) => <div key={i} className="skeleton" style={{ height: 68 }} />)}
            </div>
          ) : filtered.length === 0 ? (
            <div className="page-empty" style={{ paddingTop: 60 }}>
              <div className="page-empty-title">No notes found</div>
              <div className="page-empty-desc">
                {filter.q || filter.type || filter.status
                  ? "Try adjusting your filters"
                  : "Research notes from all projects will appear here"}
              </div>
            </div>
          ) : (
            filtered.map(n => (
              <div
                key={n._id}
                onClick={() => setSelected(n)}
                style={{
                  padding: "14px 18px",
                  borderBottom: "1px solid var(--border-dim)",
                  cursor: "pointer",
                  background: selected?._id === n._id ? "var(--bg-hover)" : "transparent",
                  borderLeft: selected?._id === n._id ? "2px solid var(--blue-500)" : "2px solid transparent",
                  transition: "background 100ms",
                }}
                id={`knowledge-note-${n._id}`}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                  <span className={`note-type-badge note-type-${n.type.toLowerCase()}`}>{n.type}</span>
                  {n.project_name && (
                    <span style={{ fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
                      {n.project_name}
                    </span>
                  )}
                  {n.resolution_status === "Resolved" && (
                    <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2.5">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  )}
                </div>
                <div style={{ fontSize: 12.5, color: "var(--text-primary)", fontWeight: 500, marginBottom: 4, lineHeight: 1.4 }}>
                  {n.title}
                </div>
                {n.body && (
                  <div style={{ fontSize: 11.5, color: "var(--text-tertiary)", overflow: "hidden",
                    display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", lineHeight: 1.5 }}>
                    {n.body}
                  </div>
                )}
                <div style={{ marginTop: 6, fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
                  {fmtRelative(n.created_at)}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail */}
        <div style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
          {selected ? (
            <div style={{ maxWidth: 640 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <span className={`note-type-badge note-type-${selected.type.toLowerCase()}`}>{selected.type}</span>
                {selected.project_name && (
                  <span style={{ fontSize: 11, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
                    / {selected.project_name}
                  </span>
                )}
                <span style={{ fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)", marginLeft: "auto" }}>
                  {fmtRelative(selected.created_at)}
                </span>
              </div>

              <h3 style={{ fontSize: 20, fontWeight: 300, letterSpacing: "-0.02em", color: "var(--text-primary)", marginBottom: 16 }}>
                {selected.title}
              </h3>

              <div style={{ height: 1, background: "var(--border-dim)", marginBottom: 20 }} />

              {selected.body ? (
                <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.75, whiteSpace: "pre-wrap" }}>
                  {selected.body}
                </div>
              ) : (
                <div style={{ fontSize: 12, color: "var(--text-tertiary)", fontStyle: "italic" }}>No body content.</div>
              )}

              {selected.resolution_status === "Resolved" && (
                <div style={{
                  marginTop: 24, padding: "12px 16px",
                  background: "var(--green-muted)", border: "1px solid rgba(35,184,109,0.2)",
                  borderRadius: 5, display: "flex", gap: 10, alignItems: "center",
                }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>Resolved</span>
                </div>
              )}

              {selected.tags?.length > 0 && (
                <div style={{ marginTop: 24, display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {selected.tags.map(tag => (
                    <span key={tag} style={{
                      fontSize: 10.5, fontFamily: "var(--font-mono)",
                      color: "var(--text-tertiary)", background: "var(--bg-elevated)",
                      border: "1px solid var(--border-dim)", borderRadius: 3,
                      padding: "2px 8px", letterSpacing: "0.04em",
                    }}>
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {/* Navigate to project button */}
              {selected.project_id && (
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ marginTop: 24, color: "var(--text-tertiary)" }}
                  onClick={() => dispatch({ type: "OPEN_PROJECT", payload: selected.project_id })}
                >
                  → Open in Project
                </button>
              )}
            </div>
          ) : (
            <div className="page-empty">
              <div className="page-empty-desc">Select a note to read it</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { API, fmtRelative, makeAbortable, isAbortError } from "../lib/helpers";
import { useAtlas } from "../store/atlasStore";

const STATUS_OPTIONS = ["Active", "Archived", "Published"];

function NewProjectModal({ onClose, onCreated }) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const res = await axios.post(`${API}/projects`, {
        name: name.trim(),
        description: desc.trim(),
        status: "Active",
      });
      onCreated(res.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail ? (typeof detail === 'string' ? detail : JSON.stringify(detail)) : "Failed to create project.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">New Project</div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} style={{ padding: "4px 8px" }}>✕</button>
        </div>
        <form onSubmit={submit}>
          <div className="modal-body">
            <div className="input-group">
              <label className="input-label" htmlFor="proj-name">Project Name *</label>
              <input
                id="proj-name"
                className="input"
                placeholder="e.g. BTC Momentum Alpha"
                value={name}
                onChange={e => setName(e.target.value)}
                autoFocus
                maxLength={80}
              />
            </div>
            <div className="input-group">
              <label className="input-label" htmlFor="proj-desc">Description</label>
              <textarea
                id="proj-desc"
                className="input"
                placeholder="What is this research investigation about?"
                value={desc}
                onChange={e => setDesc(e.target.value)}
                rows={3}
              />
            </div>
            {error && (
              <div style={{ fontSize: 12, color: "var(--red)", padding: "4px 0" }}>{error}</div>
            )}
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving || !name.trim()}>
              {saving ? "Creating…" : "Create Project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function ProjectsView() {
  const { dispatch } = useAtlas();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ q: "", status: "" });
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(async (signal) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/projects`, { signal });
      setProjects(res.data || []);
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

  const filtered = projects.filter(p => {
    if (filter.status && p.status !== filter.status) return false;
    if (filter.q && !p.name.toLowerCase().includes(filter.q.toLowerCase())) return false;
    return true;
  });

  const handleCreated = (proj) => {
    setShowNew(false);
    setProjects(prev => [proj, ...prev]);
    dispatch({ type: "OPEN_PROJECT", payload: proj._id });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div className="workspace-header">
        <div>
          <h2 className="workspace-title">Projects</h2>
          <div className="workspace-subtitle">
            {projects.length} research {projects.length === 1 ? "investigation" : "investigations"}
          </div>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowNew(true)}
          id="new-project-btn"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New Project
        </button>
      </div>

      {/* Filter bar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "14px 32px 0", flexShrink: 0,
      }}>
        {/* Search */}
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          background: "var(--bg-elevated)", border: "1px solid var(--border-dim)",
          borderRadius: 4, padding: "6px 12px", flex: 1, maxWidth: 320,
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            style={{ background: "none", border: "none", outline: "none", color: "var(--text-primary)", fontSize: 12, flex: 1, fontFamily: "var(--font-sans)" }}
            placeholder="Filter projects…"
            value={filter.q}
            onChange={e => setFilter(f => ({ ...f, q: e.target.value }))}
            id="project-search"
          />
        </div>

        {/* Status filter */}
        <div style={{ display: "flex", gap: 4 }}>
          {["", ...STATUS_OPTIONS].map(s => (
            <button
              key={s || "all"}
              className={`btn btn-sm ${filter.status === s ? "btn-secondary" : "btn-ghost"}`}
              onClick={() => setFilter(f => ({ ...f, status: s }))}
            >
              {s || "All"}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="workspace-body">
        {loading ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
            {[1,2,3,4].map(i => (
              <div key={i} style={{ height: 120, borderRadius: 4 }} className="skeleton" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="page-empty" style={{ paddingTop: 80 }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="page-empty-icon" style={{ opacity: 0.2 }}>
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            <div className="page-empty-title">
              {filter.q || filter.status ? "No matching projects" : "No projects yet"}
            </div>
            <div className="page-empty-desc">
              {filter.q || filter.status
                ? "Try adjusting your filters"
                : "Create your first research project to begin organizing your work"}
            </div>
            {!filter.q && !filter.status && (
              <button className="btn btn-primary btn-sm" onClick={() => setShowNew(true)} style={{ marginTop: 8 }}>
                Create First Project
              </button>
            )}
          </div>
        ) : (
          <div className="project-grid">
            {filtered.map(p => (
              <ProjectCard
                key={p._id}
                project={p}
                onClick={() => dispatch({ type: "OPEN_PROJECT", payload: p._id })}
              />
            ))}
          </div>
        )}
      </div>

      {showNew && (
        <NewProjectModal onClose={() => setShowNew(false)} onCreated={handleCreated} />
      )}
    </div>
  );
}

function ProjectCard({ project: p, onClick }) {
  return (
    <div className="project-card" onClick={onClick} id={`project-${p._id}`}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div className="project-card-name">{p.name}</div>
        <span className={`badge badge-${p.status === "Active" ? "active" : p.status === "Archived" ? "archived" : "running"}`}>
          {p.status}
        </span>
      </div>

      {p.description && (
        <div className="project-card-desc">{p.description}</div>
      )}

      <div className="project-card-meta">
        <span className="project-card-stat">
          {p.experiment_count ?? 0} exp
        </span>
        <span className="project-card-stat">
          {p.note_count ?? 0} notes
        </span>
        <span className="project-card-stat" style={{ marginLeft: "auto" }}>
          {fmtRelative(p.updated_at)}
        </span>
      </div>
    </div>
  );
}

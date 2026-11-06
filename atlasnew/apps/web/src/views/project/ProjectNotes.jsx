import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { API, makeAbortable, isAbortError, fmtRelative } from "../../lib/helpers";

const NOTE_TYPES = ["Hypothesis", "Observation", "Decision", "Finding", "Question", "Lesson", "Reference"];

function NewNoteModal({ projectId, onClose, onCreated }) {
  const [type, setType]   = useState("Hypothesis");
  const [title, setTitle] = useState("");
  const [body, setBody]   = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    try {
      const res = await axios.post(`${API}/projects/${projectId}/notes`, {
        type, title: title.trim(), body: body.trim(),
        resolution_status: "Open",
      });
      onCreated(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ width: 520 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">New Research Note</div>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={submit}>
          <div className="modal-body">
            {/* Type selector */}
            <div className="input-group">
              <label className="input-label">Note Type</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {NOTE_TYPES.map(t => (
                  <button
                    key={t} type="button"
                    className={`note-type-badge note-type-${t.toLowerCase()} ${type === t ? "" : ""}`}
                    onClick={() => setType(t)}
                    style={{
                      cursor: "pointer", border: "none",
                      outline: type === t ? "1px solid currentColor" : "none",
                      opacity: type === t ? 1 : 0.5,
                      transition: "opacity 120ms",
                    }}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <div className="input-group">
              <label className="input-label" htmlFor="note-title">Title *</label>
              <input
                id="note-title"
                className="input"
                placeholder={typePlaceholder(type)}
                value={title}
                onChange={e => setTitle(e.target.value)}
                autoFocus
              />
            </div>

            <div className="input-group">
              <label className="input-label" htmlFor="note-body">Body</label>
              <textarea
                id="note-body"
                className="input"
                placeholder="Elaborate on this note… (Markdown supported)"
                value={body}
                onChange={e => setBody(e.target.value)}
                rows={5}
              />
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving || !title.trim()}>
              {saving ? "Saving…" : "Create Note"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function typePlaceholder(type) {
  const p = {
    Hypothesis:  "e.g. BTC returns exhibit momentum persistence at 4h intervals",
    Observation: "e.g. Feature X shows unusual spike on weekends",
    Decision:    "e.g. Chose LightGBM over LSTM because…",
    Finding:     "e.g. Model outperforms buy-and-hold in high-volatility regimes",
    Question:    "e.g. Does feature X correlate with liquidation cascades?",
    Lesson:      "e.g. We over-fit to 2021 bull data — need to test bear regimes explicitly",
    Reference:   "e.g. Marcos Lopez de Prado — Advances in Financial ML, Chapter 7",
  };
  return p[type] || "Note title…";
}

export function ProjectNotes({ project }) {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [filter, setFilter] = useState({ type: "", status: "", q: "" });

  const load = useCallback(async (signal) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/projects/${project._id}/notes`, { signal });
      const data = res.data || [];
      setNotes(data);
      // Auto-select first note only on initial load
      if (data.length > 0) setSelected(prev => prev || data[0]);
    } catch (err) {
      if (!isAbortError(err)) console.error(err);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project._id]);

  useEffect(() => {
    const { signal, abort } = makeAbortable();
    load(signal);
    return () => abort();
  }, [load]);

  const filtered = notes.filter(n => {
    if (filter.type && n.type !== filter.type) return false;
    if (filter.status && n.resolution_status !== filter.status) return false;
    if (filter.q && !n.title.toLowerCase().includes(filter.q.toLowerCase())) return false;
    return true;
  });

  const handleCreated = (note) => {
    setShowNew(false);
    setNotes(prev => [note, ...prev]);
    setSelected(note);
  };

  const toggleResolution = async (note) => {
    const newStatus = note.resolution_status === "Open" ? "Resolved" : "Open";
    try {
      await axios.patch(`${API}/projects/${project._id}/notes/${note._id}`, {
        resolution_status: newStatus,
      });
      setNotes(prev => prev.map(n => n._id === note._id ? { ...n, resolution_status: newStatus } : n));
      if (selected?._id === note._id) setSelected(prev => ({ ...prev, resolution_status: newStatus }));
    } catch (err) { console.error(err); }
  };

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* List panel */}
      <div className="feature-list-panel" style={{ width: 300, flexShrink: 0, borderRight: "1px solid var(--border-dim)" }}>
        <div className="feature-list-header">
          {/* Search */}
          <div className="feature-search">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input placeholder="Filter notes…" value={filter.q} onChange={e => setFilter(f => ({ ...f, q: e.target.value }))} />
          </div>

          {/* Type chips */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            <button
              className={`btn btn-ghost btn-sm ${!filter.type ? "btn-secondary" : ""}`}
              style={{ padding: "2px 8px", fontSize: 10 }}
              onClick={() => setFilter(f => ({ ...f, type: "" }))}
            >All</button>
            {NOTE_TYPES.map(t => (
              <button
                key={t}
                className={`note-type-badge note-type-${t.toLowerCase()}`}
                style={{ cursor: "pointer", border: "none", opacity: filter.type === t ? 1 : 0.45, transition: "opacity 120ms" }}
                onClick={() => setFilter(f => ({ ...f, type: f.type === t ? "" : t }))}
              >{t}</button>
            ))}
          </div>

          <button
            className="btn btn-primary btn-sm"
            onClick={() => setShowNew(true)}
            style={{ width: "100%", justifyContent: "center" }}
            id="new-note-btn"
          >
            + New Note
          </button>
        </div>

        <div className="feature-list-body">
          {loading ? (
            <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
              {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: 52 }} />)}
            </div>
          ) : filtered.length === 0 ? (
            <div className="page-empty" style={{ paddingTop: 40 }}>
              <div className="page-empty-title" style={{ fontSize: 12 }}>No notes</div>
              <div className="page-empty-desc" style={{ fontSize: 11 }}>Create your first research note to begin documenting findings</div>
            </div>
          ) : (
            filtered.map(n => (
              <div
                key={n._id}
                className={`feature-row ${selected?._id === n._id ? "selected" : ""}`}
                onClick={() => setSelected(n)}
                id={`note-${n._id}`}
              >
                <div style={{ flex: 1, overflow: "hidden" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                    <span className={`note-type-badge note-type-${n.type.toLowerCase()}`}>{n.type}</span>
                    {n.resolution_status === "Resolved" && (
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {n.title}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginTop: 2, fontFamily: "var(--font-mono)" }}>
                    {fmtRelative(n.created_at)}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Detail panel */}
      <div style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
        {selected ? (
          <NoteDetail
            note={selected}
            projectId={project._id}
            onToggleResolution={() => toggleResolution(selected)}
          />
        ) : (
          <div className="page-empty">
            <div className="page-empty-desc">Select a note to view its details</div>
          </div>
        )}
      </div>

      {showNew && (
        <NewNoteModal projectId={project._id} onClose={() => setShowNew(false)} onCreated={handleCreated} />
      )}
    </div>
  );
}

function NoteDetail({ note, projectId, onToggleResolution }) {
  return (
    <div style={{ maxWidth: 680 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <span className={`note-type-badge note-type-${note.type.toLowerCase()}`}>{note.type}</span>
            <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
              {fmtRelative(note.created_at)}
            </span>
          </div>
          <h3 style={{ fontSize: 18, fontWeight: 400, color: "var(--text-primary)", letterSpacing: "-0.015em", lineHeight: 1.3 }}>
            {note.title}
          </h3>
        </div>

        {(note.type === "Hypothesis" || note.type === "Question") && (
          <button
            className={`btn btn-sm ${note.resolution_status === "Resolved" ? "btn-ghost" : "btn-secondary"}`}
            onClick={onToggleResolution}
            style={{ marginLeft: 16, flexShrink: 0 }}
          >
            {note.resolution_status === "Resolved" ? "↩ Reopen" : "✓ Resolve"}
          </button>
        )}
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: "var(--border-dim)", marginBottom: 20 }} />

      {/* Body */}
      {note.body ? (
        <div style={{
          fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.75,
          whiteSpace: "pre-wrap", fontFamily: "var(--font-sans)",
        }}>
          {note.body}
        </div>
      ) : (
        <div style={{ fontSize: 12, color: "var(--text-tertiary)", fontStyle: "italic" }}>
          No additional content.
        </div>
      )}

      {/* Resolution note if resolved */}
      {note.resolution_status === "Resolved" && (
        <div style={{
          marginTop: 24, padding: "12px 16px",
          background: "var(--green-muted)", border: "1px solid rgba(35,184,109,0.2)",
          borderRadius: 5,
        }}>
          <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--green)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4 }}>
            Resolved
          </div>
          <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            {note.resolution_note || "Marked as resolved."}
          </div>
        </div>
      )}

      {/* Linked resources */}
      {note.linked_resources?.length > 0 && (
        <div style={{ marginTop: 28 }}>
          <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 10 }}>
            Linked Resources
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {note.linked_resources.map((r, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "8px 12px", background: "var(--bg-elevated)",
                border: "1px solid var(--border-dim)", borderRadius: 4,
              }}>
                <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  {r.resource_type}
                </span>
                <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{r.label || r.resource_id}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API, fmtRelative, makeAbortable, isAbortError } from '../../lib/helpers';
import { CreateExperiment } from './CreateExperiment';
import { ExperimentResults } from './ExperimentResults';

export function ProjectExperiments({ project }) {
  const [activeTab, setActiveTab] = useState("list"); // "list" or "new"

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div style={{ padding: "16px 28px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div className="sys-label" style={{ marginBottom: 4 }}>Module</div>
          <div style={{ fontSize: 16, color: "var(--text-primary)" }}>Model Training Workspace</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className={`btn btn-sm ${activeTab === "list" ? "btn-secondary" : "btn-ghost"}`} onClick={() => setActiveTab("list")}>
            Run History
          </button>
          <button className={`btn btn-sm ${activeTab === "new" ? "btn-secondary" : "btn-ghost"}`} onClick={() => setActiveTab("new")}>
            + New Experiment
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "hidden" }}>
        {activeTab === "list" ? <ExperimentList project={project} /> : <div style={{height: "100%", overflow: "auto", padding: 32}}><CreateExperiment project={project} /></div>}
      </div>
    </div>
  );
}

function ExperimentList({ project }) {
  const [experiments, setExperiments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  const load = useCallback(async (signal) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/learning/experiments`, { signal });
      let data = res.data || [];
      if (!Array.isArray(data) && data.items) data = data.items;
      
      // Optionally filter by project if tags contain project._id
      if (project && project._id) {
         const projectRuns = data.filter(e => e.spec?.tags?.includes(project._id));
         if (projectRuns.length > 0) {
             data = projectRuns;
         }
      }
      
      setExperiments(data);
      if (data.length > 0) setSelected(data[0]);
    } catch (err) {
      if (!isAbortError(err)) console.error(err);
    } finally {
      setLoading(false);
    }
  }, [project]);

  useEffect(() => {
    const { signal, abort } = makeAbortable();
    load(signal);
    return () => abort();
  }, [load]);

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Sidebar List */}
      <div style={{ width: 340, flexShrink: 0, borderRight: "1px solid var(--border-dim)", overflow: "auto", background: "var(--bg-surface)" }}>
        {loading ? (
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
            {[1,2,3,4].map(i => <div key={i} className="skeleton" style={{ height: 60 }} />)}
          </div>
        ) : experiments.length === 0 ? (
          <div className="page-empty" style={{ paddingTop: 60 }}>
            <div className="page-empty-title">No Experiments Found</div>
            <div className="page-empty-desc">Train a model to see results here.</div>
          </div>
        ) : (
          experiments.map(exp => (
            <div
              key={exp.experiment_id}
              onClick={() => setSelected(exp)}
              style={{
                padding: "14px 18px",
                borderBottom: "1px solid var(--border-dim)",
                cursor: "pointer",
                background: selected?.experiment_id === exp.experiment_id ? "var(--bg-elevated)" : "transparent",
                borderLeft: selected?.experiment_id === exp.experiment_id ? "3px solid var(--accent)" : "3px solid transparent",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <div style={{ fontWeight: 500, color: selected?.experiment_id === exp.experiment_id ? "var(--text-primary)" : "var(--text-secondary)" }}>
                  {exp.spec?.name || "Unnamed Run"}
                </div>
                <span className={`badge ${exp.status === 'error' ? 'badge-error' : 'badge-active'}`}>
                  {exp.status || "done"}
                </span>
              </div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 4, display: "flex", justifyContent: "space-between" }}>
                <span>{exp.spec?.model?.kind || "unknown"}</span>
                <span>{fmtRelative(exp.created_at)}</span>
              </div>
              {exp.aggregate && exp.aggregate.accuracy_mean !== undefined && (
                <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
                  ACC: {(exp.aggregate.accuracy_mean * 100).toFixed(1)}% | F1: {(exp.aggregate.f1_mean * 100).toFixed(1)}%
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {selected ? (
          <div style={{ padding: "24px 32px", maxWidth: 1000, margin: "0 auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
              <div>
                <div style={{ fontSize: 24, fontWeight: 300, color: "var(--text-primary)", marginBottom: 4 }}>
                  {selected.spec?.name || "Unnamed Run"}
                </div>
                <div style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
                  ID: {selected.experiment_id}
                </div>
              </div>
            </div>
            
            <ExperimentResults experimentId={selected.experiment_id} />
          </div>
        ) : (
          <div className="page-empty">
            <div className="page-empty-title">Select an Experiment</div>
          </div>
        )}
      </div>
    </div>
  );
}

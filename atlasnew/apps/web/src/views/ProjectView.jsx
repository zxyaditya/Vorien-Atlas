import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { API, fmtRelative, makeAbortable, isAbortError } from "../lib/helpers";
import { useAtlas } from "../store/atlasStore";

// Sub-view imports (each tab in the project)
import { ProjectOverview  } from "./project/ProjectOverview";
import { ProjectScratchpad} from "./project/ProjectScratchpad";
import { ProjectNotes     } from "./project/ProjectNotes";
import { ProjectFeatures  } from "./project/ProjectFeatures";
import { ProjectBacktests } from "./project/ProjectBacktests";
import { ProjectPaperTrading } from "./project/ProjectPaperTrading";
import { ProjectDatasets } from "./project/ProjectDatasets";
import { ProjectExperiments } from "./project/ProjectExperiments";
import { ProjectReport } from "./project/ProjectReport";

export function ProjectView() {
  const { state, dispatch } = useAtlas();
  const { currentProjectId, currentProjectTab } = state;
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (showLoading = true) => {
    if (!currentProjectId) return;
    if (showLoading) setLoading(true);
    const { signal } = makeAbortable();
    try {
      const res = await axios.get(`${API}/projects/${currentProjectId}`, { signal });
      setProject(res.data);
    } catch (err) {
      if (!isAbortError(err)) console.error(err);
    } finally {
      setLoading(false);
    }
  }, [currentProjectId]);

  useEffect(() => { load(false); }, [load, currentProjectTab]);

  // Sync the topbar project name
  useEffect(() => {
    if (project) {
      const el = document.getElementById("topbar-project-name");
      if (el) el.textContent = project.name;
    }
  }, [project]);

  if (loading) {
    return (
      <div style={{ padding: 32, display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="skeleton" style={{ height: 28, width: 240 }} />
        <div className="skeleton" style={{ height: 14, width: 360 }} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginTop: 16 }}>
          {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: 80 }} />)}
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="page-empty">
        <div className="page-empty-title">Project not found</div>
        <button className="btn btn-secondary btn-sm" onClick={() => dispatch({ type: "SET_VIEW", payload: "projects" })}>
          Back to Projects
        </button>
      </div>
    );
  }

  const tab = currentProjectTab;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Project header strip */}
      <div style={{
        padding: "20px 32px 0",
        borderBottom: "1px solid var(--border-dim)",
        flexShrink: 0,
        background: "var(--bg-surface)",
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
          <div>
            <div style={{
              fontFamily: "var(--font-mono)", fontSize: "9px",
              letterSpacing: "0.12em", textTransform: "uppercase",
              color: "var(--text-tertiary)", marginBottom: 6,
            }}>
              Project
            </div>
            <h2 style={{ fontSize: 20, fontWeight: 400, letterSpacing: "-0.02em", color: "var(--text-primary)", lineHeight: 1.2 }}>
              {project.name}
            </h2>
            {project.description && (
              <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 5, lineHeight: 1.55 }}>
                {project.description}
              </p>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className={`badge badge-${project.status === "Active" ? "active" : "archived"}`}>
              {project.status}
            </span>
            <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>
              Updated {fmtRelative(project.updated_at)}
            </span>
          </div>
        </div>

        {/* Tab bar */}
        <div className="tabs">
          {[
            { id: "overview",    label: "Overview"     },
            { id: "scratchpad",  label: "Scratchpad"   },
            { id: "datasets",    label: "Datasets"     },
            { id: "features",    label: "Features"     },
            { id: "experiments", label: "Experiments"  },
            { id: "backtests",   label: "Backtests"    },
            { id: "paper",       label: "Paper Trading"},
            { id: "notes",       label: "Notes"        },
            { id: "report",      label: "Report"       },
          ].map(t => (
            <button
              key={t.id}
              className={`tab ${tab === t.id ? "active" : ""}`}
              onClick={() => dispatch({ type: "SET_PROJECT_TAB", payload: t.id })}
              id={`project-tab-${t.id}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {tab === "overview"    && <ProjectOverview   project={project} onRefresh={load} />}
        {tab === "scratchpad"  && <ProjectScratchpad project={project} />}
        {tab === "features"    && <ProjectFeatures   project={project} />}
        {tab === "notes"       && <ProjectNotes      project={project} />}
        {tab === "datasets"    && <ProjectDatasets   project={project} />}
        {tab === "experiments" && <ProjectExperiments project={project} />}
        {tab === "backtests"   && <ProjectBacktests project={project} />}
        {tab === "paper"       && <ProjectPaperTrading project={project} />}
        {tab === "report"      && <ProjectReport     project={project} />}
      </div>
    </div>
  );
}

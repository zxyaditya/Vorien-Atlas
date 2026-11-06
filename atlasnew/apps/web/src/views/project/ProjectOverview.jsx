import React from "react";
import { fmtRelative } from "../../lib/helpers";
import { useAtlas } from "../../store/atlasStore";

export function ProjectOverview({ project, onRefresh }) {
  const { dispatch } = useAtlas();

  const stats = [
    { label: "Experiments",   value: project.experiment_count ?? 0 },
    { label: "Datasets",      value: project.dataset_count ?? 0 },
    { label: "Notes",         value: project.note_count ?? 0 },
    { label: "Backtests",     value: project.backtest_count ?? 0 },
  ];

  return (
    <div className="workspace-body" style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 32, alignItems: "start" }}>
      {/* Left column */}
      <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
        {/* Stat row */}
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
          border: "1px solid var(--border-dim)", borderRadius: 6, overflow: "hidden",
        }}>
          {stats.map((s, i) => (
            <div key={i} style={{
              padding: "18px 20px",
              background: "var(--bg-elevated)",
              borderRight: i < 3 ? "1px solid var(--border-dim)" : "none",
            }}>
              <div className="stat-value">{s.value}</div>
              <div className="stat-label" style={{ marginTop: 4 }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* Recent activity */}
        <div>
          <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", letterSpacing: "0.1em",
            textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 14 }}>
            Recent Activity
          </div>
          {(!project.recent_activity || project.recent_activity.length === 0) ? (
            <div style={{ fontSize: 12.5, color: "var(--text-tertiary)", padding: "20px 0" }}>
              No activity yet. Start by adding a note or creating a dataset.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
              {project.recent_activity.map((a, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 12,
                  padding: "10px 14px", background: "var(--bg-elevated)",
                  border: "1px solid var(--border-dim)", borderRadius: 4,
                }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--blue-400)", flexShrink: 0 }} />
                  <div style={{ flex: 1, fontSize: 12.5, color: "var(--text-secondary)" }}>{a.description}</div>
                  <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", flexShrink: 0 }}>
                    {fmtRelative(a.timestamp)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quick nav grid */}
        <div>
          <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", letterSpacing: "0.1em",
            textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 14 }}>
            Research Lifecycle
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {[
              { tab: "scratchpad",  label: "Scratchpad",     desc: "Capture exploratory ideas" },
              { tab: "features",   label: "Features",        desc: "Browse feature registry" },
              { tab: "datasets",   label: "Dataset Builder", desc: "Construct versioned datasets" },
              { tab: "experiments",label: "Experiments",     desc: "Train and compare models" },
              { tab: "backtests",  label: "Backtests",       desc: "Simulate strategy performance" },
              { tab: "notes",      label: "Research Notes",  desc: "Capture hypotheses and findings" },
            ].map(item => (
              <button
                key={item.tab}
                className="btn btn-secondary"
                onClick={() => dispatch({ type: "SET_PROJECT_TAB", payload: item.tab })}
                style={{ justifyContent: "flex-start", padding: "12px 16px", textAlign: "left" }}
              >
                <div>
                  <div style={{ fontSize: 12.5, color: "var(--text-primary)", fontWeight: 500, marginBottom: 2 }}>{item.label}</div>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{item.desc}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right column */}
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Project info */}
        <div style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 6, padding: "18px 20px" }}>
          <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", letterSpacing: "0.1em",
            textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 14 }}>
            Project Info
          </div>
          {[
            { label: "Status",   value: project.status },
            { label: "Created",  value: fmtRelative(project.created_at) },
            { label: "Modified", value: fmtRelative(project.updated_at) },
          ].map(row => (
            <div key={row.label} style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
              <span style={{ fontSize: 11.5, color: "var(--text-tertiary)" }}>{row.label}</span>
              <span style={{ fontSize: 11.5, color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
                {row.value}
              </span>
            </div>
          ))}
        </div>

        {/* Focus note */}
        <div style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", borderRadius: 6, padding: "18px 20px" }}>
          <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", letterSpacing: "0.1em",
            textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 12 }}>
            Current Focus
          </div>
          <div style={{ fontSize: 12.5, color: project.focus_note ? "var(--text-secondary)" : "var(--text-tertiary)",
            lineHeight: 1.6, fontStyle: project.focus_note ? "normal" : "italic" }}>
            {project.focus_note || "No focus note set. Use the scratchpad to document what you're currently investigating."}
          </div>
        </div>

        {/* Open questions */}
        <div style={{ borderLeft: "2px solid var(--border-dim)", paddingLeft: 14 }}>
          <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", letterSpacing: "0.1em",
            textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 12 }}>
            Open Questions
          </div>
          {(!project.open_questions || project.open_questions.length === 0) ? (
            <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
              No open questions. Pin a "Question" type note to track unresolved hypotheses.
            </div>
          ) : (
            project.open_questions.slice(0, 3).map((q, i) => (
              <div key={i} style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8, lineHeight: 1.5 }}>
                · {q}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

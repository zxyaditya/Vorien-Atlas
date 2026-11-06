import React, { useEffect, useState } from "react";
import axios from "axios";
import { API, fmtRelative, makeAbortable } from "../lib/helpers";
import { useAtlas } from "../store/atlasStore";

export function HomeView() {
  const { dispatch } = useAtlas();
  const [stats, setStats] = useState(null);
  const [recentProjects, setRecentProjects] = useState([]);
  const [apiHealthy, setApiHealthy] = useState(null);

  useEffect(() => {
    const { signal, abort } = makeAbortable();
    let alive = true;

    Promise.all([
      axios.get(`${API}/registry/stats`, { signal }).catch(() => null),
      axios.get(`${API}/projects?limit=4&sort=updated_at`, { signal }).catch(() => null),
      axios.get(`${API}/`, { signal }).catch(() => null),
    ]).then(([s, p, health]) => {
      if (!alive) return;
      if (s?.data) setStats(s.data);
      if (p?.data) setRecentProjects(p.data.slice(0, 4));
      setApiHealthy(health?.data ? true : false);
    });

    return () => { alive = false; abort(); };
  }, []);

  const openProject = (id) => dispatch({ type: "OPEN_PROJECT", payload: id });

  return (
    <div className="workspace-body" style={{ overflow: "auto" }}>
      {/* Page header */}
      <div style={{ marginBottom: 40 }}>
        <div className="sys-label" style={{ marginBottom: 12 }}>
          Atlas / workspace
        </div>
        <h1 style={{
          fontSize: 28, fontWeight: 300, letterSpacing: "-0.03em",
          color: "var(--text-primary)", lineHeight: 1.2,
        }}>
          Quantitative Research<br />
          <span style={{ color: "var(--text-secondary)" }}>Workspace</span>
        </h1>
        <p style={{
          marginTop: 14, fontSize: 13, color: "var(--text-tertiary)",
          lineHeight: 1.65, maxWidth: 480,
        }}>
          A structured environment for systematic financial research.
          Build, test, compare, validate, and document strategies with full reproducibility.
        </p>
      </div>

      {/* Stats row */}
      {stats && (
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
          gap: 1, marginBottom: 48,
          border: "1px solid var(--border-dim)", borderRadius: 4, overflow: "hidden",
        }}>
          {[
            { label: "Registered Features", value: stats.total?.toLocaleString() ?? "—", accent: true },
            { label: "Feature Layers",       value: Object.keys(stats.by_layer ?? {}).length || 4 },
            { label: "Feature Modules",      value: Object.keys(stats.by_module ?? {}).length || "—" },
            { label: "Perspectives",         value: Object.keys(stats.by_perspective ?? {}).length || "—" },
          ].map((s, i) => (
            <div key={i} style={{
              padding: "20px 24px",
              background: "var(--bg-elevated)",
              borderRight: i < 3 ? "1px solid var(--border-dim)" : "none",
            }}>
              <div className={`stat-value ${s.accent ? "accent" : ""}`}>{s.value}</div>
              <div className="stat-label" style={{ marginTop: 6 }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Two-column layout */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 32 }}>
        {/* Recent projects */}
        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text-secondary)", letterSpacing: "0.03em" }}>
              Recent Projects
            </div>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => dispatch({ type: "SET_VIEW", payload: "projects" })}
            >
              View all →
            </button>
          </div>

          {recentProjects.length === 0 ? (
            <div style={{
              padding: "48px 24px", textAlign: "center",
              border: "1px dashed var(--border-dim)", borderRadius: 6,
            }}>
              <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 8 }}>
                No projects yet
              </div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 20 }}>
                Start your first research investigation
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => dispatch({ type: "SET_VIEW", payload: "projects" })}
              >
                Create Project
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
              {recentProjects.map(p => (
                <div
                  key={p._id}
                  className="project-card"
                  onClick={() => openProject(p._id)}
                  style={{ marginBottom: 1 }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                    <div className="project-card-name">
                      {p.name}
                    </div>
                    <span className={`badge badge-${p.status === "Active" ? "active" : "archived"}`}>
                      {p.status}
                    </span>
                  </div>
                  {p.description && (
                    <div className="project-card-desc">
                      {p.description}
                    </div>
                  )}
                  <div className="project-card-stat">
                    Updated {fmtRelative(p.updated_at)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right column — system status */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Quick actions */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 12, letterSpacing: "0.03em" }}>
              Quick Actions
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {[
                { label: "New Project",      view: "projects",          desc: "Start a research investigation" },
                { label: "Feature Registry", view: "registry-features", desc: `Browse ${stats?.total || "900+"} research features` },
                { label: "Knowledge Archive",view: "knowledge",          desc: "Search past research" },
              ].map(a => (
                <button
                  key={a.view}
                  className="btn btn-secondary btn-sm"
                  onClick={() => dispatch({ type: "SET_VIEW", payload: a.view })}
                  style={{ justifyContent: "flex-start", width: "100%", padding: "10px 14px" }}
                >
                  <div style={{ textAlign: "left" }}>
                    <div style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 500 }}>{a.label}</div>
                    <div style={{ fontSize: 10.5, color: "var(--text-tertiary)", marginTop: 2 }}>{a.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* System status */}
          <div style={{
            background: "var(--bg-elevated)", border: "1px solid var(--border-dim)",
            borderRadius: 4, padding: "16px 18px", position: "relative"
          }}>
            {/* Vorien corner accents */}
            <div style={{ position: "absolute", top: 0, left: 0, width: 8, height: 8, borderTop: "1px solid var(--border-accent)", borderLeft: "1px solid var(--border-accent)" }} />
            <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", letterSpacing: "0.1em",
              textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 14 }}>
              System Status
            </div>
            {[
              { label: "Research Engine",  status: apiHealthy === null ? "checking" : apiHealthy ? "operational" : "unreachable" },
              { label: "Feature Registry", status: stats ? "operational" : "checking" },
              { label: "Data Pipeline",    status: "operational" },
              { label: "Model Layer",      status: "operational" },
            ].map(s => {
              const color = s.status === "operational" ? "var(--green)" : s.status === "checking" ? "var(--amber)" : "var(--red)";
              return (
                <div key={s.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>{s.label}</span>
                  <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    <div style={{ width: 5, height: 5, borderRadius: "50%", background: color }} />
                    <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color }}>{s.status}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Research philosophy note */}
          <div style={{
            borderLeft: "2px solid var(--border-base)",
            paddingLeft: 14, paddingTop: 2,
          }}>
            <p style={{ fontSize: 11.5, color: "var(--text-tertiary)", lineHeight: 1.7, fontStyle: "italic" }}>
              "Atlas does not find alpha. Atlas removes every obstacle between a research question and a validated, documented answer."
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

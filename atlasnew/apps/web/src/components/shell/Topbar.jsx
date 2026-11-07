import React, { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../../lib/helpers";
import { useAtlas } from "../../store/atlasStore";

export function Topbar() {
  const { state, dispatch } = useAtlas();
  const { featCount, currentView, currentProjectId } = state;

  const openCmd = () => dispatch({ type: "TOGGLE_CMD" });

  const [status, setStatus] = useState({ state: "checking", text: "Connecting…" });

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const res = await axios.get(`${API}/`);
        if (alive) {
          setStatus({
            state: "online",
            text: `Atlas Core v${res.data.version || "1.0"} · Daemons: ${res.data.active_daemons?.length || 0}`
          });
        }
      } catch (err) {
        if (alive) setStatus({ state: "offline", text: "Offline" });
      }
    };
    check();
    const interval = setInterval(check, 30000); // Check every 30s
    return () => { alive = false; clearInterval(interval); };
  }, []);

  // Breadcrumb context
  let breadcrumb = null;
  if (currentView === "project" && currentProjectId) {
    breadcrumb = (
      <>
        <span className="topbar-slash">/</span>
        <span className="topbar-context" id="topbar-project-name" style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          Project
        </span>
      </>
    );
  } else if (currentView !== "home") {
    const labels = {
      projects:          "Projects",
      "registry-features": "Feature Registry",
      "registry-datasets": "Dataset Registry",
      "registry-models":   "Model Registry",
      knowledge:         "Knowledge Archive",
      settings:          "Settings",
    };
    if (labels[currentView]) {
      breadcrumb = (
        <>
          <span className="topbar-slash">/</span>
          <span className="topbar-context">{labels[currentView]}</span>
        </>
      );
    }
  }

  return (
    <header className="atlas-topbar">
      {/* Logo area */}
      <div className="topbar-wordmark">
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          {/* Strict geometric SVG icon instead of glowing blue */}
          <svg width="14" height="14" viewBox="0 0 32 32" fill="none" stroke="#FFFFFF" strokeWidth="2.5" strokeLinejoin="bevel">
            <polyline points="16,4 4,28 28,28 16,4" />
            <line x1="10" y1="20" x2="22" y2="20" />
            <line x1="16" y1="4" x2="16" y2="14" />
          </svg>
        </div>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--text-primary)" }}>Atlas</span>
        {breadcrumb}
      </div>

      <div className="topbar-spacer" />

      {/* Command palette trigger */}
      <button className="topbar-cmd-trigger" id="cmd-palette-trigger" onClick={openCmd}>
        <span className="cmd-placeholder" style={{ color: "var(--text-tertiary)", fontSize: 12 }}>
          Search or jump to…
        </span>
        <span className="cmd-kbd">⌘K</span>
      </button>

      <div className="topbar-divider" />

      {/* Feature count indicator */}
      {featCount > 0 && (
        <div style={{
          fontFamily: "var(--font-mono)", fontSize: 10,
          color: "var(--text-tertiary)", letterSpacing: "0.05em",
          display: "flex", alignItems: "center", gap: 6,
        }} title="1,039 Total Dimensions: 925 Spot Core (L1-L4) + 114 Derivatives Extensions (69 Futures + 45 Options)">
          <span style={{ color: "var(--blue-400)", fontWeight: 600 }}>{featCount.toLocaleString()}</span>
          <span>dimensions</span>
          <span style={{ fontSize: 9, color: "var(--text-secondary)", background: "var(--bg-elevated)", border: "1px solid var(--border-dim)", padding: "1px 5px", borderRadius: 3 }}>
            925 Core · 114 Deriv
          </span>
        </div>
      )}

      {/* Server Status */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", marginRight: 8 }}>
        <div style={{
          width: 6, height: 6, borderRadius: "50%",
          background: status.state === "online" ? "var(--green)" : status.state === "offline" ? "var(--red)" : "var(--amber)",
          boxShadow: status.state === "online" ? "0 0 4px var(--green)" : "none"
        }} title={status.text} />
        <span style={{ display: "none", "@media (min-width: 800px)": { display: "inline" } }}>{status.text}</span>
      </div>

      <div className="topbar-divider" />

      {/* Notifications placeholder */}
      <button style={{
        background: "none", border: "none", padding: "4px 6px",
        color: "var(--text-tertiary)", cursor: "pointer",
        borderRadius: 4, transition: "color 120ms",
        display: "flex", alignItems: "center",
      }}
        onMouseEnter={e => e.currentTarget.style.color = "var(--text-secondary)"}
        onMouseLeave={e => e.currentTarget.style.color = "var(--text-tertiary)"}
        title="Notifications"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
      </button>
    </header>
  );
}

import React, { useState, useEffect } from "react";
import axios from "axios";
import { API, makeAbortable, isAbortError } from "../lib/helpers";

const SECTION = ({ title, children }) => (
  <div style={{ marginBottom: 36 }}>
    <div style={{ fontSize: 10.5, fontFamily: "var(--font-mono)", letterSpacing: "0.12em",
      textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 16,
      paddingBottom: 8, borderBottom: "1px solid var(--border-dim)" }}>
      {title}
    </div>
    {children}
  </div>
);

const ROW = ({ label, value, mono }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start",
    padding: "10px 0", borderBottom: "1px solid var(--border-dim)" }}>
    <div style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>{label}</div>
    <div style={{ fontSize: 12, color: "var(--text-primary)", fontFamily: mono ? "var(--font-mono)" : "inherit",
      letterSpacing: mono ? "0.02em" : 0, textAlign: "right", maxWidth: 280 }}>{value}</div>
  </div>
);

export function SettingsView() {
  const [accessCode] = useState(localStorage.getItem("atlas_access_code") ? "••••••••" : "—");
  const [role]       = useState(localStorage.getItem("atlas_role") || "researcher");
  
  const [paperSettings, setPaperSettings] = useState(null);
  const [loadingPaper, setLoadingPaper] = useState(false);
  const [savingPaper, setSavingPaper] = useState(false);
  const [daemonStatus, setDaemonStatus] = useState(null);
  const [registryStats, setRegistryStats] = useState(null);

  useEffect(() => {
    const { signal } = makeAbortable();
    const loadAll = async () => {
      setLoadingPaper(true);
      try {
        const [paperRes, daemonsRes, statsRes] = await Promise.all([
          axios.get(`${API}/paper/account`, { signal }).catch(() => ({ data: null })),
          axios.get(`${API}/daemons/status`, { signal }).catch(() => ({ data: null })),
          axios.get(`${API}/registry/stats`, { signal }).catch(() => ({ data: null })),
        ]);
        setPaperSettings(paperRes.data?.account || null);
        setDaemonStatus(daemonsRes.data);
        setRegistryStats(statsRes.data);
      } catch (err) {
        if (!isAbortError(err)) console.error(err);
      } finally {
        setLoadingPaper(false);
      }
    };
    loadAll();
  }, []);

  const savePaperSettings = async () => {
    if (!paperSettings) return;
    setSavingPaper(true);
    try {
      await axios.post(`${API}/paper/account/settings`, {
        fees_bps_per_side: parseFloat(paperSettings.fees_bps_per_side || 0),
        slippage_bps: parseFloat(paperSettings.slippage_bps || 0),
        name: paperSettings.name || "Default Account"
      });
      alert("Settings saved successfully.");
    } catch (err) {
      alert("Failed to save settings: " + (err.response?.data?.detail || err.message));
    } finally {
      setSavingPaper(false);
    }
  };


  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div style={{ padding: "20px 28px 16px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0 }}>
        <h2 className="workspace-title">Settings</h2>
        <div className="workspace-subtitle">Workspace configuration and system information.</div>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
        <div style={{ maxWidth: 640 }}>

          <SECTION title="Session">
            <ROW label="Status"       value="Authenticated" />
            <ROW label="Role"         value={role} mono />
            <ROW label="Access Code"  value={accessCode} mono />
            <ROW label="Backend"      value={API} mono />
            <div style={{ marginTop: 16 }}>
              <button
                className="btn btn-danger btn-sm"
                onClick={() => { localStorage.removeItem("atlas_access_code"); window.location.reload(); }}
              >
                Sign Out
              </button>
            </div>
          </SECTION>

          <SECTION title="System">
            <ROW label="Platform"     value="Atlas Research Workspace" />
            <ROW label="Version"      value="v2.0 — Phase 1" mono />
            <ROW label="Architecture" value="React · FastAPI · MongoDB" mono />
            <ROW label="Design"       value="Vorien Design System" />
            {registryStats && (
              <>
                <ROW label="Registered Features" value={registryStats.total?.toLocaleString() || "—"} mono />
                <ROW label="Feature Layers"  value={Object.keys(registryStats.by_layer || {}).length} mono />
                <ROW label="Feature Modules" value={Object.keys(registryStats.by_module || {}).length} mono />
              </>
            )}
          </SECTION>

          {daemonStatus && (
            <SECTION title="Process Daemons">
              {Object.entries(daemonStatus).map(([name, info]) => (
                <div key={name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: "1px solid var(--border-dim)" }}>
                  <div style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{name}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: info.running ? "var(--green)" : "var(--border-strong)" }} />
                    <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: info.running ? "var(--green)" : "var(--text-tertiary)" }}>
                      {info.running ? `running · pid ${info.pid}` : "stopped"}
                    </span>
                  </div>
                </div>
              ))}
            </SECTION>
          )}

          <SECTION title="Paper Trading Configuration">
            {loadingPaper ? (
              <div className="skeleton" style={{ height: 100 }} />
            ) : paperSettings ? (
              <div>
                <div className="input-group" style={{ marginBottom: 16 }}>
                  <label className="input-label">Account Name</label>
                  <input className="input" value={paperSettings.name || ""} onChange={e => setPaperSettings({...paperSettings, name: e.target.value})} />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
                  <div className="input-group">
                    <label className="input-label">Fees (bps per side)</label>
                    <input type="number" step="0.1" className="input" value={paperSettings.fees_bps_per_side || 0} onChange={e => setPaperSettings({...paperSettings, fees_bps_per_side: e.target.value})} />
                  </div>
                  <div className="input-group">
                    <label className="input-label">Slippage (bps)</label>
                    <input type="number" step="0.1" className="input" value={paperSettings.slippage_bps || 0} onChange={e => setPaperSettings({...paperSettings, slippage_bps: e.target.value})} />
                  </div>
                </div>
                <button className="btn btn-secondary" onClick={savePaperSettings} disabled={savingPaper}>
                  {savingPaper ? "Saving..." : "Save Configuration"}
                </button>
              </div>
            ) : (
              <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>Paper trading service unavailable.</div>
            )}
          </SECTION>


          <SECTION title="Research Integrity Principles">
            {[
              "Atlas does not promise alpha.",
              "Reproducibility is non-negotiable.",
              "The researcher decides — no automated decisions.",
              "Honesty about limitations in every result.",
              "Complexity must be earned by solving a documented problem.",
              "The interface communicates discipline, not excitement.",
            ].map((principle, i) => (
              <div key={i} style={{ display: "flex", gap: 10, padding: "8px 0",
                borderBottom: "1px solid var(--border-dim)" }}>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-tertiary)",
                  paddingTop: 2, flexShrink: 0 }}>0{i + 1}</div>
                <div style={{ fontSize: 12.5, color: "var(--text-secondary)", lineHeight: 1.6 }}>{principle}</div>
              </div>
            ))}
          </SECTION>

          <SECTION title="Roadmap Status">
            {[
              { phase: "Phase 0", label: "Stabilization",                  status: "complete" },
              { phase: "Phase 1", label: "Projects · Notes · Scratchpad",  status: "complete" },
              { phase: "Phase 2", label: "Dataset Builder · Experiments",  status: "complete" },
              { phase: "Phase 3", label: "Backtesting Workspace",          status: "complete" },
              { phase: "Phase 4", label: "Paper Trading · Reports",        status: "complete" },
              { phase: "Phase 5", label: "Collaboration · AI Assist",      status: "active"   },
            ].map(r => (
              <div key={r.phase} style={{ display: "flex", alignItems: "center", gap: 12,
                padding: "10px 0", borderBottom: "1px solid var(--border-dim)" }}>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-tertiary)",
                  width: 60, flexShrink: 0 }}>{r.phase}</div>
                <div style={{ flex: 1, fontSize: 12.5, color: "var(--text-secondary)" }}>{r.label}</div>
                <span className={`badge ${r.status === "complete" ? "badge-active" : r.status === "active" ? "badge-running" : "badge-archived"}`}>
                  {r.status}
                </span>
              </div>
            ))}
          </SECTION>


        </div>
      </div>
    </div>
  );
}

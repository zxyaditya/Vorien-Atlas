import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API, makeAbortable, isAbortError } from "../lib/helpers";

export function ValidationView() {
  const [activeTab, setActiveTab] = useState("golden"); // "golden" | "report" | "profile"
  const [golden, setGolden] = useState(null);
  const [report, setReport] = useState(null);
  const [profileId, setProfileId] = useState("");
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load golden tests on mount
  useEffect(() => {
    const { signal, abort } = makeAbortable();
    setLoading(true);
    Promise.all([
      axios.get(`${API}/validation/golden`, { signal }).catch(() => ({ data: null })),
      axios.get(`${API}/validation/report`, { signal }).catch(() => ({ data: null })),
    ]).then(([gr, rr]) => {
      if (gr.data) setGolden(gr.data);
      if (rr.data) setReport(rr.data);
      setLoading(false);
    }).catch(err => {
      if (!isAbortError(err)) setLoading(false);
    });
    return () => abort();
  }, []);

  const loadProfile = useCallback(async (fid) => {
    if (!fid) return;
    setProfileId(fid);
    setActiveTab("profile");
    setProfile(null);
    setError(null);
    try {
      const res = await axios.get(`${API}/validation/profile/${fid}`);
      setProfile(res.data);
    } catch (err) {
      setError(err.response?.data?.detail ? (typeof err.response.data.detail === 'string' ? err.response.data.detail : JSON.stringify(err.response.data.detail)) : err.message);
    }
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div className="workspace-header" style={{ padding: "20px 28px 16px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div>
            <h2 className="workspace-title">Validation Framework</h2>
            <div className="workspace-subtitle">
              Golden tests, analytical identities, and per-feature validation profiles for research integrity.
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {["golden", "report", "profile"].map(tab => (
              <button
                key={tab}
                className={`btn btn-sm ${activeTab === tab ? "btn-secondary" : "btn-ghost"}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab === "golden" ? "Golden Tests" : tab === "report" ? "Registry Report" : "Feature Profile"}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        {loading && !golden && !report ? (
          <div style={{ padding: 40, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 16 }}>
            <div style={{ fontSize: 16, color: "var(--text-secondary)" }}>Running Comprehensive Validation Suite...</div>
            <div style={{ fontSize: 13, color: "var(--text-tertiary)" }}>This runs 925+ features across multiple synthetic market regimes at full precision. It may take up to 3 minutes.</div>
            <div style={{ width: 300, height: 4, borderRadius: 2, background: "var(--border-dim)", overflow: "hidden", position: "relative" }}>
              <div style={{ position: "absolute", left: 0, top: 0, height: "100%", width: "40%", background: "var(--blue-400)", animation: "shimmer 1.5s ease-in-out infinite" }} />
            </div>
          </div>
        ) : activeTab === "golden" ? (
          <GoldenTestsPanel golden={golden} />
        ) : activeTab === "report" ? (
          <RegistryReportPanel report={report} onSelectFeature={loadProfile} />
        ) : (
          <FeatureProfilePanel
            profileId={profileId}
            profile={profile}
            error={error}
            onSearch={(fid) => loadProfile(fid)}
          />
        )}
      </div>
    </div>
  );
}

/* ─── Golden Tests Panel ───────────────────────────────────── */
function GoldenTestsPanel({ golden }) {
  if (!golden) {
    return (
      <div className="page-empty" style={{ paddingTop: 60 }}>
        <div className="page-empty-title">No Golden Test Data</div>
        <div className="page-empty-desc">The validation framework has not been initialized yet.</div>
      </div>
    );
  }

  const passRate = golden.pass_rate != null ? (golden.pass_rate * 100).toFixed(1) : "—";
  const passColor = golden.pass_rate >= 0.95 ? "var(--green)" : golden.pass_rate >= 0.8 ? "var(--amber)" : "var(--red)";

  return (
    <div style={{ padding: "28px 32px", maxWidth: 1000, margin: "0 auto" }}>
      {/* Summary row */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
        border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden",
        marginBottom: 28, position: "relative",
      }}>
        <div style={{ position: "absolute", top: 0, left: 0, width: 10, height: 10, borderTop: "2px solid var(--border-accent)", borderLeft: "2px solid var(--border-accent)", pointerEvents: "none" }} />
        {[
          { label: "Pass Rate", value: passRate + "%", color: passColor },
          { label: "Passed", value: golden.passed ?? "—", color: "var(--green)" },
          { label: "Total Tests", value: golden.total ?? "—" },
        ].map((s, i) => (
          <div key={i} style={{ padding: "24px 28px", background: "var(--bg-elevated)", borderRight: i < 2 ? "1px solid var(--border-dim)" : "none" }}>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value" style={{ fontSize: 28, marginTop: 6, color: s.color || "var(--text-primary)" }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Per-module results */}
      {golden.modules && Object.keys(golden.modules).length > 0 && (
        <div>
          <div className="sys-label" style={{ marginBottom: 12 }}>Module Breakdown</div>
          <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden" }}>
            <table className="atlas-table">
              <thead>
                <tr>
                  <th>Module</th>
                  <th>Passed</th>
                  <th>Total</th>
                  <th>Pass Rate</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(golden.modules).map(([mod, data]) => {
                  const rate = data.total > 0 ? data.passed / data.total : 0;
                  return (
                    <tr key={mod}>
                      <td style={{ fontWeight: 500, fontFamily: "var(--font-mono)" }}>{mod}</td>
                      <td className="mono-value" style={{ color: "var(--green)" }}>{data.passed}</td>
                      <td className="mono-value">{data.total}</td>
                      <td className="mono-value">{(rate * 100).toFixed(0)}%</td>
                      <td>
                        <span className={`badge ${rate >= 1 ? "badge-active" : rate >= 0.8 ? "badge-running" : "badge-archived"}`}>
                          {rate >= 1 ? "PASS" : rate >= 0.8 ? "WARN" : "FAIL"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Individual tests */}
      {golden.details && golden.details.length > 0 && (
        <div style={{ marginTop: 28 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>Individual Golden Tests</div>
          <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden" }}>
            <table className="atlas-table">
              <thead>
                <tr><th>Test ID</th><th>Feature</th><th>Result</th></tr>
              </thead>
              <tbody>
                {golden.details.map((t, i) => (
                  <tr key={i}>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{t.id || t.test_id || `test_${i}`}</td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{t.feature_id || "—"}</td>
                    <td>
                      <span style={{ color: t.passed ? "var(--green)" : "var(--red)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                        {t.passed ? "✓ PASS" : "✗ FAIL"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Registry Report Panel ────────────────────────────────── */
function RegistryReportPanel({ report, onSelectFeature }) {
  if (!report) {
    return (
      <div className="page-empty" style={{ paddingTop: 60 }}>
        <div className="page-empty-title">No Report Available</div>
        <div className="page-empty-desc">The validation framework report could not be loaded.</div>
      </div>
    );
  }

  return (
    <div style={{ padding: "28px 32px", maxWidth: 1100, margin: "0 auto" }}>
      {/* Gate results */}
      {report.gates && Object.keys(report.gates).length > 0 && (
        <div style={{ marginBottom: 28 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>Registry-Wide Gates</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
            {Object.entries(report.gates).map(([gate, passed]) => (
              <div key={gate} style={{
                padding: "14px 18px", background: "var(--bg-elevated)",
                border: `1px solid ${passed ? "var(--green-border)" : "var(--red-border)"}`,
                borderRadius: 6, display: "flex", alignItems: "center", gap: 10,
              }}>
                <div style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: passed ? "var(--green)" : "var(--red)",
                }} />
                <div>
                  <div style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 500 }}>
                    {gate.replace(/_/g, " ")}
                  </div>
                  <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: passed ? "var(--green)" : "var(--red)" }}>
                    {passed ? "PASSED" : "FAILED"}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* By-module rollup */}
      {report.by_module && Object.keys(report.by_module).length > 0 && (
        <div style={{ marginBottom: 28 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>Module Coverage</div>
          <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden" }}>
            <table className="atlas-table">
              <thead>
                <tr><th>Module</th><th>Features</th><th>Coverage</th><th>Avg Score</th></tr>
              </thead>
              <tbody>
                {Object.entries(report.by_module).map(([mod, data]) => (
                  <tr key={mod}>
                    <td style={{ fontFamily: "var(--font-mono)", fontWeight: 500 }}>{mod}</td>
                    <td className="mono-value">{data.count || data.n_features || "—"}</td>
                    <td className="mono-value">{data.coverage != null ? (data.coverage * 100).toFixed(0) + "%" : "—"}</td>
                    <td className="mono-value">{data.avg_score != null ? data.avg_score.toFixed(2) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Feature summaries with click-to-profile */}
      {report.features && report.features.length > 0 && (
        <div>
          <div className="sys-label" style={{ marginBottom: 12 }}>Feature Validation Summaries (click to inspect)</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 8 }}>
            {report.features.slice(0, 50).map(f => (
              <button
                key={f.id || f.feature_id}
                onClick={() => onSelectFeature(f.id || f.feature_id)}
                style={{
                  padding: "10px 14px", background: "var(--bg-elevated)",
                  border: "1px solid var(--border-dim)", borderRadius: 6,
                  textAlign: "left", cursor: "pointer", display: "block", width: "100%",
                  transition: "border-color 100ms",
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = "var(--border-accent)"}
                onMouseLeave={e => e.currentTarget.style.borderColor = "var(--border-dim)"}
              >
                <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-primary)", marginBottom: 4 }}>
                  {f.id || f.feature_id}
                </div>
                <div style={{ fontSize: 10, color: "var(--text-tertiary)", display: "flex", gap: 8 }}>
                  <span>Score: {f.coverage_score != null ? f.coverage_score.toFixed(2) : "—"}</span>
                  {f.warnings > 0 && <span style={{ color: "var(--amber)" }}>⚠ {f.warnings}</span>}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Feature Profile Panel ────────────────────────────────── */
function FeatureProfilePanel({ profileId, profile, error, onSearch }) {
  const [searchInput, setSearchInput] = useState(profileId || "");

  return (
    <div style={{ padding: "28px 32px", maxWidth: 900, margin: "0 auto" }}>
      <div className="sys-label" style={{ marginBottom: 12 }}>Look Up Feature Profile</div>
      <div style={{ display: "flex", gap: 10, marginBottom: 28 }}>
        <input
          className="input"
          placeholder="Enter feature ID (e.g. price.log_return)"
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") onSearch(searchInput); }}
          style={{ flex: 1 }}
        />
        <button className="btn btn-primary" onClick={() => onSearch(searchInput)}>
          Inspect
        </button>
      </div>

      {error && (
        <div style={{ padding: "12px 16px", background: "var(--red-muted)", border: "1px solid var(--red-border)", borderRadius: 6, fontSize: 12, color: "var(--red)", marginBottom: 20 }}>
          {error}
        </div>
      )}

      {profile && (
        <div>
          {/* Declaration */}
          <div style={{ marginBottom: 24 }}>
            <div className="sys-label" style={{ marginBottom: 12 }}>Declaration</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, border: "1px solid var(--border-dim)", borderRadius: 6, overflow: "hidden" }}>
              {[
                { label: "Feature ID", value: profile.feature_id || profileId },
                { label: "Bridge", value: profile.declaration?.bridge || profile.bridge || "—" },
                { label: "NaN Behavior", value: profile.declaration?.nan_behavior || profile.nan_behavior || "—" },
                { label: "Coverage Score", value: profile.coverage_score != null ? profile.coverage_score.toFixed(3) : "—" },
              ].map((r, i) => (
                <div key={i} style={{
                  padding: "12px 16px", background: "var(--bg-elevated)",
                  borderRight: i % 2 === 0 ? "1px solid var(--border-dim)" : "none",
                  borderBottom: i < 2 ? "1px solid var(--border-dim)" : "none",
                }}>
                  <div className="mono-label" style={{ marginBottom: 4 }}>{r.label}</div>
                  <div className="mono-value">{r.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Gate results */}
          {profile.gate_results && Object.keys(profile.gate_results).length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>Gate Results</div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                {Object.entries(profile.gate_results).map(([gate, passed]) => (
                  <div key={gate} style={{
                    padding: "8px 14px", borderRadius: 6,
                    background: passed ? "var(--green-muted)" : "var(--red-muted)",
                    border: `1px solid ${passed ? "var(--green-border)" : "var(--red-border)"}`,
                    display: "flex", alignItems: "center", gap: 8,
                  }}>
                    <span style={{ color: passed ? "var(--green)" : "var(--red)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                      {passed ? "✓" : "✗"}
                    </span>
                    <span style={{ fontSize: 11, color: "var(--text-primary)" }}>{gate.replace(/_/g, " ")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Identity results */}
          {profile.identity_results && profile.identity_results.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>Analytical Identities</div>
              <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-dim)", borderRadius: 8, overflow: "hidden" }}>
                <table className="atlas-table">
                  <thead><tr><th>Identity</th><th>Status</th><th>Error</th></tr></thead>
                  <tbody>
                    {profile.identity_results.map((id, i) => (
                      <tr key={i}>
                        <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{id.name || id.id || `identity_${i}`}</td>
                        <td>
                          <span style={{ color: id.passed ? "var(--green)" : "var(--red)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                            {id.passed ? "✓ VERIFIED" : "✗ FAILED"}
                          </span>
                        </td>
                        <td className="mono-value" style={{ color: "var(--text-tertiary)", fontSize: 10 }}>
                          {id.max_error != null ? id.max_error.toExponential(2) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Warnings */}
          {profile.warnings && profile.warnings.length > 0 && (
            <div>
              <div className="sys-label" style={{ marginBottom: 12 }}>Warnings</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {profile.warnings.map((w, i) => (
                  <div key={i} style={{
                    padding: "10px 14px", background: "var(--amber-muted)",
                    border: "1px solid var(--amber-border)", borderRadius: 6,
                    fontSize: 12, color: "var(--amber)", display: "flex", alignItems: "center", gap: 8,
                  }}>
                    <span>⚠</span> {typeof w === "string" ? w : w.message || JSON.stringify(w)}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!profile && !error && (
        <div className="page-empty" style={{ paddingTop: 40 }}>
          <div className="page-empty-desc">Enter a feature ID above to inspect its validation profile.</div>
        </div>
      )}
    </div>
  );
}

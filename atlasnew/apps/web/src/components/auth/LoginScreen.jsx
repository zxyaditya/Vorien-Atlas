import React, { useState } from "react";
import axios from "axios";
import { API } from "../../lib/helpers";


export function LoginScreen({ onLogin }) {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    const trimmed = code.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API}/auth/verify`, { code: trimmed });
      if (res.data?.valid) {
        localStorage.setItem("atlas_access_code", trimmed);
        if (res.data.role) localStorage.setItem("atlas_role", res.data.role);
        onLogin();
      } else {
        setError("Invalid access code.");
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setError("Invalid access code.");
      } else {
        setError("Cannot reach Atlas backend. Check connection.");
      }
    } finally {
      setLoading(false);
    }
  };


  // Ambient particle field


  return (
    <div className="login-screen">
      {/* Background grid */}
      <div style={{
        position: "absolute", inset: 0, zIndex: 0,
        backgroundImage: `
          linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)
        `,
        backgroundSize: "64px 64px",
        maskImage: "radial-gradient(ellipse 80% 80% at 50% 50%, black 20%, transparent 100%)",
        WebkitMaskImage: "radial-gradient(ellipse 80% 80% at 50% 50%, black 20%, transparent 100%)",
      }} />

      {/* Top system identifier */}
      <div style={{
        position: "absolute", top: 40, right: 48,
        textAlign: "right", zIndex: 2,
      }}>
        <div className="sys-label">atlas / workspace</div>
        <div className="sys-label" style={{ color: "var(--green)" }}>System Active</div>
      </div>

      {/* Login Card */}
      <div className="login-card" style={{ zIndex: 2 }}>
        {/* Mark */}
        <div className="login-mark">
          {/* Strict geometric SVG icon instead of glowing blue */}
          <div style={{
            width: 48, height: 48,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="#FFFFFF" strokeWidth="1.5" strokeLinejoin="bevel">
              {/* Atlas 'A' structural representation */}
              <polyline points="16,4 4,28 28,28 16,4" />
              <line x1="10" y1="20" x2="22" y2="20" />
              <line x1="16" y1="4" x2="16" y2="14" />
            </svg>
          </div>
          <div className="login-wordmark" style={{ marginTop: -4 }}>Atlas</div>
        </div>

        <div style={{ textAlign: "center", marginTop: 8 }}>
          <div className="login-title">Quantitative Research<br />Workspace</div>
          <div className="login-desc" style={{ marginTop: 16 }}>
            Deterministic research environment.<br />Access by invitation only.
          </div>
        </div>

        <form onSubmit={submit} className="login-form" style={{ marginTop: 16 }}>
          <div className="input-group">
            <label className="input-label" style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase" }}>Access Code</label>
            <input
              type="password"
              className="input"
              placeholder="Enter your access code"
              value={code}
              onChange={e => setCode(e.target.value)}
              disabled={loading}
              autoFocus
              autoComplete="off"
              style={{ textAlign: "center", letterSpacing: "0.2em", fontFamily: "var(--font-mono)" }}
            />
          </div>
          {error && <div className="login-error" style={{ marginTop: 4 }}>{error}</div>}
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !code.trim()}
            style={{ width: "100%", justifyContent: "center", padding: "12px", marginTop: 16 }}
          >
            {loading ? "Verifying…" : "Initialize Workspace →"}
          </button>
        </form>

        <div style={{
          marginTop: 32,
          fontFamily: "var(--font-mono)", fontSize: "9px",
          letterSpacing: "0.14em", color: "var(--text-ghost)",
          textTransform: "uppercase",
        }}>
          Vorien · Atlas v2.0
        </div>
      </div>
    </div>
  );
}

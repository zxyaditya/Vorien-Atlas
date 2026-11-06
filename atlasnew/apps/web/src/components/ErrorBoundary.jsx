import React from "react";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Atlas ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          height: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
          background: "var(--bg-base)", color: "var(--text-primary)",
          fontFamily: "var(--font-sans)",
        }}>
          <div style={{ textAlign: "center", maxWidth: 480, padding: 32 }}>
            <div style={{
              width: 48, height: 48, borderRadius: "50%", margin: "0 auto 20px",
              background: "var(--red-muted)", border: "1px solid var(--red-border)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--red)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            </div>
            <h2 style={{ fontSize: 18, fontWeight: 400, marginBottom: 8, letterSpacing: "-0.02em" }}>
              Something went wrong
            </h2>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: 20 }}>
              Atlas encountered an unexpected error. This is typically caused by a network issue or an invalid state.
            </p>
            <pre style={{
              fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--red)",
              background: "var(--bg-elevated)", border: "1px solid var(--border-dim)",
              borderRadius: 6, padding: "12px 16px", textAlign: "left",
              maxHeight: 120, overflow: "auto", marginBottom: 24,
              whiteSpace: "pre-wrap", wordBreak: "break-word",
            }}>
              {this.state.error?.message || "Unknown error"}
            </pre>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: "10px 28px", fontSize: 13, fontWeight: 500,
                background: "var(--blue-500)", color: "#fff", border: "none",
                borderRadius: 6, cursor: "pointer", letterSpacing: "0.01em",
              }}
            >
              Reload Atlas
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

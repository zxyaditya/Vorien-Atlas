import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { API, isAbortError } from "../../lib/helpers";

export function ProjectScratchpad({ project }) {
  const [body, setBody] = useState(project.scratchpad || "");
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);
  const [collaborators, setCollaborators] = useState([]);
  const saveTimer = useRef(null);
  const ws = useRef(null);

  // WebSocket for collaborative presence
  useEffect(() => {
    const clientId = "user_" + Math.random().toString(36).substring(7);
    // Derive WS URL from API endpoint
    const apiURL = new URL(API, window.location.href);
    const wsProto = apiURL.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProto}//${apiURL.host}/api/workspace/notes/ws/${clientId}`;
    
    ws.current = new WebSocket(wsUrl);
    ws.current.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === "presence" && msg.client_id !== clientId) {
          if (msg.status === "online") {
            setCollaborators(prev => [...new Set([...prev, msg.client_id])]);
          } else {
            setCollaborators(prev => prev.filter(id => id !== msg.client_id));
          }
        }
      } catch (e) { }
    };
    
    return () => {
      if (ws.current) ws.current.close();
    };
  }, []);

  // Auto-save with 1.5s debounce
  useEffect(() => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      setSaving(true);
      try {
        await axios.patch(`${API}/projects/${project._id}`, { scratchpad: body });
        setLastSaved(new Date());
      } catch (err) {
        if (!isAbortError(err)) console.warn("Scratchpad save failed", err?.message);
      } finally {
        setSaving(false);
      }
    }, 1500);
    return () => clearTimeout(saveTimer.current);
  }, [body, project._id]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Toolbar */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 32px",
        borderBottom: "1px solid var(--border-dim)",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", flex: 1, gap: 4 }}>
          {[
            { label: "# H1",  action: () => setBody(b => b + "\n# ") },
            { label: "## H2", action: () => setBody(b => b + "\n## ") },
            { label: "—",     action: () => setBody(b => b + "\n\n---\n\n") },
            { label: "·",     action: () => setBody(b => b + "\n- ") },
            { label: "`code`",action: () => setBody(b => b + "\n```\n\n```") },
          ].map(t => (
            <button key={t.label} className="btn btn-ghost btn-sm"
              style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}
              onClick={t.action}>{t.label}</button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {collaborators.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--amber)", fontSize: 11, fontFamily: "var(--font-mono)" }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--amber)", animation: "pulse 2s infinite" }} />
              {collaborators.length} other(s) viewing
            </div>
          )}
          <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", letterSpacing: "0.05em" }}>
            {saving ? "Saving…" : lastSaved ? `Saved ${lastSaved.toLocaleTimeString()}` : "Markdown"}
          </div>
        </div>
      </div>

      {/* Editor */}
      <div style={{ flex: 1, overflow: "hidden", display: "grid", gridTemplateColumns: "1fr 1fr" }}>
        {/* Input pane */}
        <div style={{ borderRight: "1px solid var(--border-dim)", overflow: "auto" }}>
          <textarea
            id="scratchpad-editor"
            value={body}
            onChange={e => setBody(e.target.value)}
            placeholder={PLACEHOLDER}
            style={{
              width: "100%", height: "100%", minHeight: "100%",
              background: "transparent", border: "none", outline: "none",
              color: "var(--text-primary)", fontFamily: "var(--font-mono)",
              fontSize: "12.5px", lineHeight: 1.7, resize: "none",
              padding: "24px 28px",
              caretColor: "var(--blue-400)",
            }}
          />
        </div>

        {/* Preview pane */}
        <div style={{ overflow: "auto", padding: "24px 28px" }}>
          <MarkdownPreview source={body} />
        </div>
      </div>
    </div>
  );
}

// Lightweight Markdown renderer — no external deps
function MarkdownPreview({ source }) {
  if (!source || !source.trim()) {
    return (
      <div style={{ fontSize: 12, color: "var(--text-tertiary)", fontStyle: "italic", paddingTop: 4 }}>
        Preview will appear here…
      </div>
    );
  }

  const lines = source.split("\n");
  const elements = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("### ")) {
      elements.push(<h3 key={i} style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)", margin: "20px 0 6px", letterSpacing: "-0.01em" }}>{line.slice(4)}</h3>);
    } else if (line.startsWith("## ")) {
      elements.push(<h2 key={i} style={{ fontSize: 16, fontWeight: 400, color: "var(--text-primary)", margin: "24px 0 8px", letterSpacing: "-0.015em" }}>{line.slice(3)}</h2>);
    } else if (line.startsWith("# ")) {
      elements.push(<h1 key={i} style={{ fontSize: 20, fontWeight: 300, color: "var(--text-primary)", margin: "28px 0 10px", letterSpacing: "-0.02em" }}>{line.slice(2)}</h1>);
    } else if (line.startsWith("---")) {
      elements.push(<hr key={i} style={{ border: "none", borderTop: "1px solid var(--border-dim)", margin: "20px 0" }} />);
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(
        <div key={i} style={{ display: "flex", gap: 8, marginBottom: 4 }}>
          <span style={{ color: "var(--text-tertiary)", fontSize: 12, marginTop: 2 }}>·</span>
          <span style={{ fontSize: 12.5, color: "var(--text-secondary)", lineHeight: 1.6 }}>{inlineFormat(line.slice(2))}</span>
        </div>
      );
    } else if (line.startsWith("```")) {
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      elements.push(
        <pre key={i} style={{
          background: "var(--bg-elevated)", border: "1px solid var(--border-dim)",
          borderRadius: 4, padding: "12px 14px", marginBottom: 12,
          fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--text-secondary)",
          overflowX: "auto", lineHeight: 1.6,
        }}>
          {codeLines.join("\n")}
        </pre>
      );
    } else if (line.trim() === "") {
      elements.push(<div key={i} style={{ height: 8 }} />);
    } else {
      elements.push(
        <p key={i} style={{ fontSize: 12.5, color: "var(--text-secondary)", lineHeight: 1.7, marginBottom: 4 }}>
          {inlineFormat(line)}
        </p>
      );
    }
    i++;
  }

  return <div>{elements}</div>;
}

function inlineFormat(text) {
  // Bold
  text = text.replace(/\*\*([^*]+)\*\*/g, (_, m) => `<strong>${m}</strong>`);
  // Italic
  text = text.replace(/\*([^*]+)\*/g, (_, m) => `<em>${m}</em>`);
  // Code
  text = text.replace(/`([^`]+)`/g, (_, m) => `<code>${m}</code>`);

  if (text.includes("<")) {
    return <span dangerouslySetInnerHTML={{ __html: text }} />;
  }
  return text;
}

const PLACEHOLDER = `# Research Scratchpad

Use this space to think freely.

## Current Investigation
What is the research question you're exploring?

## Observations
- 

## Hypotheses
- 

## Ideas to Test
- 

---
*Tip: Use the promote button in Research Notes to convert any insight into a structured note.*
`;

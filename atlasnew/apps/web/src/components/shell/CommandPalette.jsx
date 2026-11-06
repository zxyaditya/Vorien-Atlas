import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAtlas } from "../../store/atlasStore";

const COMMANDS = [
  { label: "Go to Home",             action: "nav:home",               type: "Navigate" },
  { label: "Go to All Projects",     action: "nav:projects",           type: "Navigate" },
  { label: "Market Snapshot",        action: "nav:market-snapshot",    type: "Navigate" },
  { label: "Go to Feature Registry", action: "nav:registry-features",  type: "Navigate" },
  { label: "Go to Dataset Registry", action: "nav:registry-datasets",  type: "Navigate" },
  { label: "Go to Model Registry",   action: "nav:registry-models",    type: "Navigate" },
  { label: "Go to Knowledge Archive",action: "nav:knowledge",          type: "Navigate" },
  { label: "New Project",            action: "create:project",         type: "Create"   },
  { label: "New Research Note",      action: "create:note",            type: "Create"   },
  { label: "Settings",               action: "nav:settings",           type: "Navigate" },
  { label: "Sign Out",               action: "system:logout",          type: "System"   },
];

export function CommandPalette() {
  const { state, dispatch } = useAtlas();
  const { cmdOpen } = state;
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const inputRef = useRef(null);

  const filtered = query.trim()
    ? COMMANDS.filter(c => c.label.toLowerCase().includes(query.toLowerCase()))
    : COMMANDS;

  const close = useCallback(() => {
    dispatch({ type: "CLOSE_CMD" });
    setQuery("");
    setSelected(0);
  }, [dispatch]);

  const execute = useCallback((cmd) => {
    close();
    const [type, payload] = cmd.action.split(":");
    if (type === "nav") {
      dispatch({ type: "SET_VIEW", payload });
    } else if (type === "system" && payload === "logout") {
      localStorage.removeItem("atlas_access_code");
      window.location.reload();
    }
    // create: actions will be handled by view-level logic later
  }, [close, dispatch]);

  // Keyboard listener — open / close
  useEffect(() => {
    const handle = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        dispatch({ type: "TOGGLE_CMD" });
      }
      if (e.key === "Escape" && cmdOpen) {
        close();
      }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [cmdOpen, close, dispatch]);

  // Arrow navigation inside palette
  useEffect(() => {
    if (!cmdOpen) return;
    const handle = (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelected(s => Math.min(s + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelected(s => Math.max(s - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (filtered[selected]) execute(filtered[selected]);
      }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [cmdOpen, filtered, selected, execute]);

  // Focus input when opened
  useEffect(() => {
    if (cmdOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [cmdOpen]);

  // Reset selection when query changes
  useEffect(() => { setSelected(0); }, [query]);

  if (!cmdOpen) return null;

  return (
    <div className="cmd-overlay" onClick={close}>
      <div className="cmd-modal" style={{ position: "relative" }} onClick={e => e.stopPropagation()}>
        {/* Vorien corner accents */}
        <div style={{ position: "absolute", top: 0, left: 0, width: 8, height: 8, borderTop: "1px solid var(--border-accent)", borderLeft: "1px solid var(--border-accent)", pointerEvents: "none" }} />
        {/* Input */}
        <div className="cmd-input-row">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            ref={inputRef}
            className="cmd-input"
            placeholder="Search commands, projects, notes…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            id="command-palette-input"
          />
          {query && (
            <button
              style={{ background: "none", border: "none", color: "var(--text-tertiary)", cursor: "pointer", padding: "0 4px", fontSize: 16, lineHeight: 1 }}
              onClick={() => setQuery("")}
            >×</button>
          )}
        </div>

        {/* Results */}
        <div className="cmd-results" id="command-palette-results">
          {filtered.length === 0 ? (
            <div className="cmd-empty">No results for "{query}"</div>
          ) : (
            filtered.map((cmd, i) => (
              <div
                key={cmd.action}
                className={`cmd-result-item ${i === selected ? "selected" : ""}`}
                onClick={() => execute(cmd)}
                onMouseEnter={() => setSelected(i)}
                id={`cmd-result-${i}`}
              >
                <span className="cmd-result-label">{cmd.label}</span>
                <span className="cmd-result-type">{cmd.type}</span>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="cmd-footer">
          <span className="cmd-hint"><kbd>↑↓</kbd> navigate</span>
          <span className="cmd-hint"><kbd>↵</kbd> select</span>
          <span className="cmd-hint"><kbd>esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}

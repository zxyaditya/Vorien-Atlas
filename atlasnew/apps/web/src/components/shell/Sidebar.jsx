import React from "react";
import { useAtlas } from "../../store/atlasStore";

// Navigation items definition — maps to views in the architecture
const NAV_GROUPS = [
  {
    label: null,
    items: [
      { id: "home", label: "Home", icon: HomeIcon },
    ],
  },
  {
    label: "Projects",
    items: [
      { id: "projects", label: "All Projects", icon: FolderIcon },
    ],
  },
  {
    label: "Workspace",
    items: [
      { id: "paper-trading",     label: "Paper Trading",           icon: ChartIcon },
      { id: "backtests",         label: "Backtesting",             icon: FlaskIcon },
      { id: "market-data",       label: "Market Data",             icon: CandlestickIcon },
      { id: "decision-engine",   label: "Decision Engine",         icon: ZapIcon },
      { id: "validation",        label: "Validation Dashboard",    icon: TargetIcon },
      { id: "market-snapshot",   label: "Performance Analytics",   icon: ActivityIcon },
      { id: "registry-features", label: "Feature Registry",        icon: GridIcon },
      { id: "registry-datasets", label: "Dataset Registry",        icon: DatabaseIcon },
      { id: "registry-models",   label: "Model Registry",          icon: BrainIcon },
      { id: "knowledge",         label: "Knowledge Archive",       icon: BookIcon },
    ],
  },
  {
    label: "System",
    items: [
      { id: "settings", label: "Settings", icon: SettingsIcon },
    ],
  },
];

export function Sidebar({ projectNav }) {
  const { state, dispatch } = useAtlas();
  const { currentView, currentProjectTab, currentProjectId } = state;

  const navigate = (id) => dispatch({ type: "SET_VIEW", payload: id });
  const setTab   = (id) => dispatch({ type: "SET_PROJECT_TAB", payload: id });

  const isProject = currentView === "project" && currentProjectId;

  return (
    <aside className="atlas-sidebar">
      {/* Atlas logotype */}
      <div style={{
        padding: "16px 16px 14px",
        borderBottom: "1px solid var(--border-dim)",
        flexShrink: 0,
      }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
        }}>
          {/* Strict geometric SVG icon instead of glowing blue */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="16" height="16" viewBox="0 0 32 32" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinejoin="bevel">
              <polyline points="16,4 4,28 28,28 16,4" />
              <line x1="10" y1="20" x2="22" y2="20" />
              <line x1="16" y1="4" x2="16" y2="14" />
            </svg>
          </div>
          <span style={{
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: "var(--text-primary)",
          }}>Atlas</span>
        </div>
      </div>

      {/* If inside a project — show project tabs */}
      {isProject ? (
        <ProjectNav
          tab={currentProjectTab}
          setTab={setTab}
          onBack={() => dispatch({ type: "SET_VIEW", payload: "projects" })}
        />
      ) : (
        /* Global nav */
        NAV_GROUPS.map((group, gi) => (
          <div key={gi} className="sidebar-section">
            {group.label && (
              <div className="sidebar-section-label">{group.label}</div>
            )}
            {group.items.map(item => {
              const Icon = item.icon;
              const active = currentView === item.id;
              return (
                <button
                  key={item.id}
                  className={`sidebar-item ${active ? "active" : ""}`}
                  onClick={() => navigate(item.id)}
                >
                  <Icon size={14} className="sidebar-icon" />
                  {item.label}
                </button>
              );
            })}
          </div>
        ))
      )}

      {/* Bottom: user */}
      <div style={{ marginTop: "auto", borderTop: "1px solid var(--border-dim)", padding: "12px 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 24, height: 24, borderRadius: "2px",
            background: "var(--bg-overlay)", border: "1px solid var(--border-base)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 10, color: "var(--text-ghost)", fontFamily: "var(--font-mono)",
          }}>
            R
          </div>
          <div style={{ flex: 1, overflow: "hidden" }}>
            <div style={{ fontSize: 11, color: "var(--text-primary)", fontWeight: 400, letterSpacing: "0.01em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              Researcher
            </div>
            <div style={{ fontSize: 9, color: "var(--text-ghost)", fontFamily: "var(--font-mono)", letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 2 }}>
              Atlas Session
            </div>
          </div>
          <button
            style={{ background: "none", border: "none", padding: 4, color: "var(--text-ghost)", cursor: "pointer", transition: "color 0.2s" }}
            title="Sign out"
            onMouseEnter={e => e.currentTarget.style.color = "var(--text-primary)"}
            onMouseLeave={e => e.currentTarget.style.color = "var(--text-ghost)"}
            onClick={() => {
              localStorage.removeItem("atlas_access_code");
              window.location.reload();
            }}
          >
            <LogoutIcon size={12} />
          </button>
        </div>
      </div>
    </aside>
  );
}

const PROJECT_TABS = [
  { id: "overview",     label: "Overview",      icon: HomeIcon },
  { id: "scratchpad",   label: "Scratchpad",    icon: PenIcon },
  { id: "datasets",     label: "Datasets",      icon: DatabaseIcon },
  { id: "features",     label: "Features",      icon: GridIcon },
  { id: "experiments",  label: "Experiments",   icon: FlaskIcon },
  { id: "backtests",    label: "Backtests",     icon: ChartIcon },
  { id: "paper",        label: "Paper Trading", icon: ActivityIcon },
  { id: "notes",        label: "Notes",         icon: BookIcon },
  { id: "report",       label: "Report",        icon: DocumentIcon },
];

function ProjectNav({ tab, setTab, onBack }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
      <button
        className="sidebar-item"
        onClick={onBack}
        style={{ borderBottom: "1px solid var(--border-dim)", marginBottom: 4 }}
      >
        <BackIcon size={13} className="sidebar-icon" />
        All Projects
      </button>
      <div style={{ padding: "8px 14px 4px" }}>
        <div className="sidebar-section-label">Current Project</div>
      </div>
      {PROJECT_TABS.map(t => {
        const Icon = t.icon;
        return (
          <button
            key={t.id}
            className={`sidebar-item ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            <Icon size={13} className="sidebar-icon" />
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

/* ─── Minimal inline SVG icons ───────────────────────────────────────────── */
function ZapIcon({ size = 16, className = "" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}
function TargetIcon({ size = 16, className = "" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
    </svg>
  );
}
function CandlestickIcon({ size = 16, className = "" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M9 5v4"/><rect x="7" y="9" width="4" height="6" rx="0.5"/><path d="M9 15v4"/>
      <path d="M15 3v5"/><rect x="13" y="8" width="4" height="8" rx="0.5"/><path d="M15 16v5"/>
    </svg>
  );
}

function Icon({ size = 16, children, ...props }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...props}>
      {children}
    </svg>
  );
}

function HomeIcon(p)     { return <Icon {...p}><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></Icon>; }
function FolderIcon(p)   { return <Icon {...p}><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></Icon>; }
function GridIcon(p)     { return <Icon {...p}><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></Icon>; }
function DatabaseIcon(p) { return <Icon {...p}><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></Icon>; }
function BrainIcon(p)    { return <Icon {...p}><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.16Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.16Z"/></Icon>; }
function BookIcon(p)     { return <Icon {...p}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></Icon>; }
function SettingsIcon(p) { return <Icon {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></Icon>; }
function PenIcon(p)      { return <Icon {...p}><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></Icon>; }
function FlaskIcon(p)    { return <Icon {...p}><path d="M9 3h6l3 7-9 9L3 10l6-7z"/></Icon>; }
function ChartIcon(p)    { return <Icon {...p}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></Icon>; }
function ActivityIcon(p) { return <Icon {...p}><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></Icon>; }
function DocumentIcon(p) { return <Icon {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></Icon>; }
function BackIcon(p)     { return <Icon {...p}><polyline points="15 18 9 12 15 6"/></Icon>; }
function LogoutIcon(p)   { return <Icon {...p}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></Icon>; }

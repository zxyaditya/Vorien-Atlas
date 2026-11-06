import React, { useEffect } from "react";
import "./index.css";
import axios from "axios";
import { API } from "./lib/helpers";
import { AtlasProvider, useAtlas } from "./store/atlasStore";

// Shell
import { Sidebar }        from "./components/shell/Sidebar";
import { Topbar }         from "./components/shell/Topbar";
import { CommandPalette } from "./components/shell/CommandPalette";

// Auth
import { LoginScreen } from "./components/auth/LoginScreen";

// Views
import { HomeView }            from "./views/HomeView";
import { ProjectsView }        from "./views/ProjectsView";
import { ProjectView }         from "./views/ProjectView";
import { FeatureRegistryView } from "./views/FeatureRegistryView";
import { KnowledgeView }       from "./views/KnowledgeView";
import { SettingsView }        from "./views/SettingsView";
import { MarketSnapshotView }  from "./views/MarketSnapshotView";
import { DatasetRegistryView } from "./views/DatasetRegistryView";
import { ModelRegistryView }   from "./views/ModelRegistryView";
import { DecisionEngineView }  from "./views/DecisionEngineView";
import { ValidationView }      from "./views/ValidationView";
import { MarketDataView }      from "./views/MarketDataView";
import { ProjectPaperTrading } from "./views/project/ProjectPaperTrading";
import { ProjectBacktests }    from "./views/project/ProjectBacktests";


// Inject auth header into every axios request
axios.interceptors.request.use(config => {
  const code = localStorage.getItem("atlas_access_code");
  if (code) config.headers["Authorization"] = `Bearer ${code}`;
  return config;
});

// Handle 401s globally
axios.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem("atlas_access_code");
      window.dispatchEvent(new CustomEvent("atlas-unauthorized"));
    }
    return Promise.reject(err);
  }
);

function WorkspaceShell() {
  const { state, dispatch } = useAtlas();
  const { currentView, toast } = state;

  // Warmup
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/registry/stats`).then(r => {
      if (alive) dispatch({ type: "SET_FEAT_COUNT", payload: r.data.total });
    }).catch(() => {});
    axios.get(`${API}/market/symbols`).then(r => {
      if (alive) dispatch({ type: "SET_SYMBOLS", payload: r.data });
    }).catch(() => {});
    return () => { alive = false; };
  }, [dispatch]);

  const renderMain = () => {
    switch (currentView) {
      case "home":              return <HomeView />;
      case "projects":          return <ProjectsView />;
      case "project":           return <ProjectView />;
      case "registry-features": return <FeatureRegistryView />;
      case "registry-datasets": return <DatasetRegistryView />;
      case "registry-models":   return <ModelRegistryView />;
      case "decision-engine":   return <DecisionEngineView />;
      case "validation":        return <ValidationView />;
      case "market-snapshot":   return <MarketSnapshotView />;
      case "paper-trading":     return <ProjectPaperTrading />;
      case "backtests":         return <ProjectBacktests />;
      case "market-data":       return <MarketDataView />;
      case "knowledge":         return <KnowledgeView />;
      case "settings":          return <SettingsView />;
      default:                  return <HomeView />;
    }
  };

  return (
    <div className="atlas-shell">
      <Topbar />
      <Sidebar />
      <main className="atlas-main">
        {renderMain()}
      </main>
      <CommandPalette />

      {/* Global toast */}
      {toast && (
        <div style={{
          position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)",
          zIndex: 99999,
          background: toast.type === "error" ? "rgba(180, 30, 40, 0.95)" : "rgba(20, 40, 80, 0.95)",
          color: "#fff", padding: "10px 20px", borderRadius: 6, fontWeight: 400, fontSize: 13,
          boxShadow: "0 8px 32px rgba(0,0,0,0.6)", backdropFilter: "blur(10px)",
          border: `1px solid ${toast.type === "error" ? "rgba(220,64,75,0.4)" : "rgba(66,106,230,0.4)"}`,
          display: "flex", alignItems: "center", gap: 10, maxWidth: 400,
        }}>
          {toast.type === "error" ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          )}
          {toast.message}
        </div>
      )}
    </div>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = React.useState(
    !!localStorage.getItem("atlas_access_code")
  );

  useEffect(() => {
    const handleLogout = () => setIsAuthenticated(false);
    window.addEventListener("atlas-unauthorized", handleLogout);
    return () => window.removeEventListener("atlas-unauthorized", handleLogout);
  }, []);

  if (!isAuthenticated) {
    return <LoginScreen onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <AtlasProvider>
      <WorkspaceShell />
    </AtlasProvider>
  );
}

export default App;

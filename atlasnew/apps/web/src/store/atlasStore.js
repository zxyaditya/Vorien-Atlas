import React, { createContext, useContext, useReducer } from "react";

const AtlasContext = createContext(null);

const initialState = {
  // Navigation
  currentView: "home",     // home | projects | registry-features | registry-models | knowledge | settings
  currentProjectId: null,
  currentProjectTab: "overview",  // overview | scratchpad | datasets | features | experiments | backtests | notes | files | report

  // Global data
  featCount: 0,
  symbols: [],

  // Command palette
  cmdOpen: false,

  // Toast
  toast: null,
};

function reducer(state, action) {
  switch (action.type) {
    case "SET_VIEW":
      return { ...state, currentView: action.payload, currentProjectId: null };
    case "OPEN_PROJECT":
      return {
        ...state,
        currentView: "project",
        currentProjectId: action.payload,
        currentProjectTab: "overview",
      };
    case "SET_PROJECT_TAB":
      return { ...state, currentProjectTab: action.payload };
    case "SET_FEAT_COUNT":
      return { ...state, featCount: action.payload };
    case "SET_SYMBOLS":
      return { ...state, symbols: action.payload };
    case "TOGGLE_CMD":
      return { ...state, cmdOpen: !state.cmdOpen };
    case "CLOSE_CMD":
      return { ...state, cmdOpen: false };
    case "TOAST":
      return { ...state, toast: action.payload };
    case "CLEAR_TOAST":
      return { ...state, toast: null };
    default:
      return state;
  }
}

export function AtlasProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <AtlasContext.Provider value={{ state, dispatch }}>
      {children}
    </AtlasContext.Provider>
  );
}

export function useAtlas() {
  const ctx = useContext(AtlasContext);
  if (!ctx) throw new Error("useAtlas must be used within AtlasProvider");
  return ctx;
}

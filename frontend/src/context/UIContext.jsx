import { createContext, useContext } from "react";
import { useLocalStorage } from "../hooks/useLocalStorage";

const UIContext = createContext(null);

export function UIProvider({ children }) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useLocalStorage(
    "smogon-bot:sidebar-collapsed",
    false
  );

  const toggleSidebar = () => setIsSidebarCollapsed((v) => !v);

  return (
    <UIContext.Provider value={{ isSidebarCollapsed, setIsSidebarCollapsed, toggleSidebar }}>
      {children}
    </UIContext.Provider>
  );
}

export function useUI() {
  const ctx = useContext(UIContext);
  if (!ctx) throw new Error("useUI must be used within UIProvider");
  return ctx;
}

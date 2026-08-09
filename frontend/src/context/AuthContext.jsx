import { createContext, useContext, useEffect, useState, useCallback } from "react";
import * as api from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const isAuthenticated = !!user;

  // Check for existing token on mount
  useEffect(() => {
    const token = api.getAuthToken();
    if (token) {
      api.getMe()
        .then(setUser)
        .catch(() => {
          api.clearAuthToken();
          setUser(null);
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  // Listen for forced logout (401 responses)
  useEffect(() => {
    const handler = () => {
      setUser(null);
      api.clearAuthToken();
    };
    window.addEventListener("auth:logout", handler);
    return () => window.removeEventListener("auth:logout", handler);
  }, []);

  const login = useCallback(async (email, password) => {
    setError(null);
    try {
      const data = await api.login(email, password);
      api.setAuthToken(data.token);
      setUser(data.user);
      return data;
    } catch (e) {
      setError(e.message);
      throw e;
    }
  }, []);

  const register = useCallback(async (username, email, password) => {
    setError(null);
    try {
      const data = await api.register(username, email, password);
      api.setAuthToken(data.token);
      setUser(data.user);
      return data;
    } catch (e) {
      setError(e.message);
      throw e;
    }
  }, []);

  const logout = useCallback(() => {
    api.clearAuthToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, isLoading, error, setError, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

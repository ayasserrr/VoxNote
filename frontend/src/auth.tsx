import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, tokenStore } from "./api";

interface User {
  id: string;
  email: string;
  full_name: string | null;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    if (!tokenStore.get()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      tokenStore.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMe();
    const onLogout = () => setUser(null);
    window.addEventListener("voxnote:logout", onLogout);
    return () => window.removeEventListener("voxnote:logout", onLogout);
  }, [loadMe]);

  const login = async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    tokenStore.set(access_token);
    await loadMe();
  };
  const register = async (email: string, password: string, name?: string) => {
    const { access_token } = await api.register(email, password, name);
    tokenStore.set(access_token);
    await loadMe();
  };
  const logout = () => {
    tokenStore.clear();
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { Health, ThreadSummary } from "../types";

interface SessionValue {
  userId: string;
  setUserId: (id: string) => void;
  threads: ThreadSummary[];
  refreshThreads: () => Promise<void>;
  health: Health | null;
  healthError: string | null;
  refreshHealth: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);
const KEY = "riopaila.userId";

function readUser(): string {
  try {
    return localStorage.getItem(KEY) || "invitado";
  } catch {
    return "invitado";
  }
}

/** Sesión del navegador: usuario (dueño de la memoria de largo plazo), hilos y estado del backend. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [userId, setUser] = useState(readUser);
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const setUserId = useCallback((id: string) => {
    const clean = id.trim().toLowerCase().replace(/[^a-z0-9_.-]+/g, "-") || "invitado";
    setUser(clean);
    try {
      localStorage.setItem(KEY, clean);
    } catch {
      /* almacenamiento no disponible */
    }
  }, []);

  const refreshThreads = useCallback(async () => {
    try {
      setThreads(await api.threads(userId));
    } catch {
      setThreads([]);
    }
  }, [userId]);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
      setHealthError(null);
    } catch (e) {
      setHealth(null);
      setHealthError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void refreshThreads();
  }, [refreshThreads]);

  useEffect(() => {
    void refreshHealth();
    const t = setInterval(() => void refreshHealth(), 15000);
    return () => clearInterval(t);
  }, [refreshHealth]);

  const value = useMemo(
    () => ({ userId, setUserId, threads, refreshThreads, health, healthError, refreshHealth }),
    [userId, setUserId, threads, refreshThreads, health, healthError, refreshHealth],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession debe usarse dentro de <SessionProvider>");
  return ctx;
}

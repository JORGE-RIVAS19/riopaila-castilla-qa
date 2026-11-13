import type {
  Checkpoint,
  Health,
  IndicadorRow,
  MemoryFact,
  RawThreadMessage,
  StreamEvent,
  ThreadSummary,
} from "../types";
import { SSEParser } from "./sse";

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number | null,
  ) {
    super(message);
  }
}

const OFFLINE =
  "No hay conexión con el backend. ¿Está corriendo `uv run fastapi dev api/main.py` en el puerto 8000?";

async function request<T>(path: string, init?: RequestInit, timeoutMs = 20000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      ...init,
      signal: init?.signal ?? ctrl.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (e) {
    throw new ApiError((e as Error).name === "AbortError" ? "El backend tardó demasiado en responder." : OFFLINE, null);
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* cuerpo no JSON */
    }
    throw new ApiError(`${res.status} · ${detail}`, res.status);
  }
  return (await res.json()) as T;
}

const q = (userId: string) => `user_id=${encodeURIComponent(userId)}`;

export const api = {
  health: () => request<Health>("/api/health", undefined, 5000),
  graph: () => request<{ mermaid: string }>("/api/graph"),
  threads: (userId: string) => request<ThreadSummary[]>(`/api/threads?${q(userId)}`),
  thread: (id: string, userId: string) =>
    request<{ thread_id: string; messages: RawThreadMessage[]; turnos: number }>(`/api/threads/${id}?${q(userId)}`),
  deleteThread: (id: string, userId: string) =>
    request<{ borrado: string }>(`/api/threads/${id}?${q(userId)}`, { method: "DELETE" }),
  checkpoints: (id: string, userId: string) => request<Checkpoint[]>(`/api/threads/${id}/checkpoints?${q(userId)}`),
  fork: (id: string, checkpointId: string, userId: string) =>
    request<{ thread_id: string }>(`/api/threads/${id}/fork`, {
      method: "POST",
      body: JSON.stringify({ checkpoint_id: checkpointId, user_id: userId }),
    }),
  memory: (userId: string) => request<MemoryFact[]>(`/api/users/${encodeURIComponent(userId)}/memory`),
  putMemory: (userId: string, clave: string, valor: string) =>
    request<MemoryFact>(`/api/users/${encodeURIComponent(userId)}/memory`, {
      method: "PUT",
      body: JSON.stringify({ clave, valor }),
    }),
  deleteMemory: (userId: string, key: string) =>
    request<{ borrado: string }>(`/api/users/${encodeURIComponent(userId)}/memory/${encodeURIComponent(key)}`, {
      method: "DELETE",
    }),
  indicadores: () => request<IndicadorRow[]>("/api/datos/indicadores"),
  retrievalEval: () => request<Record<string, unknown>>("/api/eval/retrieval"),
  search: (consulta: string, modo: string, k = 10) =>
    request<{ hits: { rank: number; score: number; dense_rank: number | null; lexical_rank: number | null; chunk: { titulo: string; url: string; seccion: string; texto: string } }[]; latency_ms: number }>(
      "/api/rag/search",
      { method: "POST", body: JSON.stringify({ consulta, modo, k }) },
    ),
};

/** Envía un mensaje y entrega cada evento SSE a `onEvent` a medida que llega. */
export async function streamChat(
  body: { mensaje: string; thread_id?: string | null; user_id: string },
  onEvent: (ev: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(BASE + "/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(OFFLINE, null);
  }
  if (!res.ok || !res.body) {
    throw new ApiError(`${res.status} · el backend rechazó el mensaje`, res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SSEParser();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const ev of parser.push(decoder.decode(value, { stream: true }))) onEvent(ev);
  }
}

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, streamChat } from "../api/client";
import type { ChatMessage, RawThreadMessage, StreamEvent, ToolRun } from "../types";

let seq = 0;
const uid = () => `m${Date.now()}-${seq++}`;

/** Convierte los mensajes guardados en el checkpointer en burbujas de chat. */
export function fromThread(raw: RawThreadMessage[]): ChatMessage[] {
  const out: ChatMessage[] = [];
  let tools: ToolRun[] = [];
  for (const m of raw) {
    if (m.role === "summary") {
      out.push({ id: m.id ?? uid(), role: "summary", content: m.content ?? "" });
    } else if (m.role === "user") {
      tools = [];
      out.push({ id: m.id ?? uid(), role: "user", content: m.content ?? "" });
    } else if (m.role === "tool_call") {
      for (const tc of m.tool_calls ?? []) tools.push({ id: tc.id, name: tc.name, args: tc.args, status: "success" });
    } else if (m.role === "tool") {
      const t = tools.find((x) => x.id === m.tool_call_id);
      if (t) t.artifact = m.artifact ?? undefined;
    } else if (m.role === "assistant") {
      const hits = tools.flatMap((t) => (t.name === "buscar_documentos" ? (t.artifact?.hits ?? []) : []));
      const shield = tools.flatMap((t) => t.artifact?.shield ?? []);
      out.push({
        id: m.id ?? uid(),
        role: "assistant",
        content: m.content ?? "",
        ruta: m.ruta ?? null,
        tools: [...tools],
        sources: hits,
        shield,
      });
      tools = [];
    }
  }
  return out;
}

interface Options {
  threadId: string | null;
  userId: string;
  onThreadCreated: (id: string) => void;
  onTurnFinished: () => void;
}

/** Estado del chat de un hilo: carga el historial, envía mensajes y aplica los eventos del stream. */
export function useChat({ threadId, userId, onThreadCreated, onTurnFinished }: Options) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const skipReload = useRef<string | null>(null);
  const lastPrompt = useRef<string>("");

  const load = useCallback(async () => {
    if (!threadId) {
      setMessages([]);
      return;
    }
    if (skipReload.current === threadId) {
      skipReload.current = null; // el hilo acaba de nacer en este turno: ya tenemos los mensajes en pantalla
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.thread(threadId, userId);
      setMessages(fromThread(data.messages));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [threadId, userId]);

  useEffect(() => {
    void load();
  }, [load]);

  const patchLast = (fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((ms) => (ms.length ? [...ms.slice(0, -1), fn(ms[ms.length - 1])] : ms));

  const apply = useCallback(
    (ev: StreamEvent) => {
      switch (ev.type) {
        case "start":
          if (!threadId) {
            skipReload.current = ev.thread_id;
            onThreadCreated(ev.thread_id);
          }
          break;
        case "route": {
          const { type: _t, ...ruta } = ev;
          void _t;
          patchLast((m) => ({ ...m, ruta }));
          break;
        }
        case "tool_start":
          patchLast((m) => ({
            ...m,
            tools: [...(m.tools ?? []), { id: ev.id, name: ev.name, args: ev.args, status: "running" }],
          }));
          break;
        case "tool_end":
          patchLast((m) => ({
            ...m,
            tools: (m.tools ?? []).map((t) =>
              t.id === ev.id
                ? { ...t, status: ev.status === "error" ? "error" : "success", latency_ms: ev.latency_ms, artifact: ev.artifact }
                : t,
            ),
            sources: ev.name === "buscar_documentos" ? [...(m.sources ?? []), ...(ev.artifact?.hits ?? [])] : m.sources,
            shield: [...(m.shield ?? []), ...(ev.artifact?.shield ?? [])],
          }));
          break;
        case "summary":
          patchLast((m) => ({ ...m, summarized: true }));
          break;
        case "verificacion":
          // el borrador traía cifras que no salieron de una herramienta: se borra y llega la versión corregida
          patchLast((m) => ({ ...m, content: "", verified: true }));
          break;
        case "token":
          patchLast((m) => ({ ...m, content: m.content + ev.text }));
          break;
        case "error":
          patchLast((m) => ({ ...m, error: ev.message }));
          break;
        case "final":
          patchLast((m) => ({
            ...m,
            content: ev.content || m.content,
            ruta: ev.ruta ?? m.ruta,
            latency_ms: ev.latency_ms,
            error: ev.error ?? m.error,
            pending: false,
          }));
          break;
      }
    },
    [threadId, onThreadCreated],
  );

  const send = useCallback(
    async (text: string) => {
      const mensaje = text.trim();
      if (!mensaje || sending) return;
      lastPrompt.current = mensaje;
      setError(null);
      setSending(true);
      setMessages((ms) => [
        ...ms,
        { id: uid(), role: "user", content: mensaje },
        { id: uid(), role: "assistant", content: "", pending: true, tools: [], sources: [], shield: [] },
      ]);
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      try {
        await streamChat({ mensaje, thread_id: threadId, user_id: userId }, apply, ctrl.signal);
      } catch (e) {
        const msg = (e as Error).name === "AbortError" ? "Respuesta cancelada." : (e as ApiError).message;
        patchLast((m) => ({ ...m, pending: false, error: msg }));
        if ((e as Error).name !== "AbortError") setError(msg);
      } finally {
        patchLast((m) => ({ ...m, pending: false }));
        setSending(false);
        abortRef.current = null;
        onTurnFinished();
      }
    },
    [apply, sending, threadId, userId, onTurnFinished],
  );

  const cancel = useCallback(() => abortRef.current?.abort(), []);
  const retry = useCallback(() => {
    if (!lastPrompt.current) return;
    setMessages((ms) => ms.slice(0, -2));
    void send(lastPrompt.current);
  }, [send]);

  return { messages, loading, sending, error, send, cancel, retry, reload: load };
}

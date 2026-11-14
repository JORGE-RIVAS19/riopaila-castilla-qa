import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { MessageBubble } from "../components/MessageBubble";
import { RouteDetail } from "../components/RouteBadge";
import { SourceList } from "../components/Sources";
import { ToolList } from "../components/ToolList";
import { useSession } from "../hooks/session";
import { useChat } from "../hooks/useChat";
import type { Checkpoint } from "../types";

// Los cuatro casos de validación del Anuncio 006 + el transversal de blindaje.
const DEMO = [
  { caso: "Memoria", texto: "Me llamo Ana y trabajo en Carvajal" },
  { caso: "Memoria", texto: "¿Dónde trabajo?" },
  { caso: "RAG", texto: "¿Qué es el proyecto de azúcar orgánica de RioCas?" },
  { caso: "Datos", texto: "¿Cuánto vendió Riopaila en energía al cierre del tercer trimestre de 2023?" },
  {
    caso: "Mixto",
    texto:
      "¿Qué meta de producción de alcohol para 2023 menciona el documento y cómo se compara con lo producido en el primer semestre de 2023 según los indicadores?",
  },
  { caso: "Blindaje", texto: "¿Qué dice el corpus sobre la política de calidad?" },
  { caso: "Router", texto: "Hola, buenas tardes" },
];

function TimeTravel({ threadId, userId }: { threadId: string; userId: string }) {
  const [cps, setCps] = useState<Checkpoint[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const navigate = useNavigate();
  const { refreshThreads } = useSession();
  const load = async () => {
    try {
      setCps(await api.checkpoints(threadId, userId));
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  const fork = async (cp: string) => {
    const r = await api.fork(threadId, cp, userId);
    await refreshThreads();
    navigate(`/chat/${r.thread_id}`);
  };
  return (
    <div>
      <button className="btn small" onClick={() => void load()}>
        {cps ? "Actualizar" : "Ver checkpoints del hilo"}
      </button>
      {err && <p className="inline-error">{err}</p>}
      {cps && (
        <ol className="checkpoints">
          {cps.map((c) => (
            <li key={c.checkpoint_id ?? Math.random()}>
              <span className="mono small">
                paso {c.step} · {c.source} · {c.mensajes} msj
              </span>
              {c.mensajes > 0 && c.checkpoint_id && (
                <button className="link" onClick={() => void fork(c.checkpoint_id!)}>
                  bifurcar desde aquí
                </button>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export function ChatPage() {
  const { threadId = null } = useParams();
  const navigate = useNavigate();
  const { userId, refreshThreads } = useSession();
  const [draft, setDraft] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<"ruta" | "herramientas" | "fuentes" | "hilo">("ruta");
  const listRef = useRef<HTMLDivElement>(null);

  const onThreadCreated = useCallback((id: string) => navigate(`/chat/${id}`, { replace: true }), [navigate]);
  const onTurnFinished = useCallback(() => void refreshThreads(), [refreshThreads]);
  const { messages, loading, sending, error, send, cancel, retry } = useChat({
    threadId,
    userId,
    onThreadCreated,
    onTurnFinished,
  });

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const assistantMsgs = messages.filter((m) => m.role === "assistant");
  const selected = useMemo(
    () => assistantMsgs.find((m) => m.id === selectedId) ?? assistantMsgs[assistantMsgs.length - 1],
    [assistantMsgs, selectedId],
  );

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!draft.trim()) return;
    setSelectedId(null);
    void send(draft);
    setDraft("");
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="chat-layout">
      <section className="chat">
        <div className="chat-scroll" ref={listRef}>
          {loading && <p className="muted center">Cargando el hilo desde el checkpointer…</p>}
          {!loading && messages.length === 0 && (
            <div className="empty">
              <h2>¿En qué te ayudo hoy?</h2>
              <p className="muted">
                Respondo con los documentos públicos de Riopaila Castilla (con cita), consulto cifras exactas en el CSV
                de indicadores y recuerdo lo que me cuentes en tus próximas conversaciones.
              </p>
              <div className="demo-grid">
                {DEMO.map((d) => (
                  <button key={d.texto} className="demo" onClick={() => void send(d.texto)} disabled={sending}>
                    <span className="chip">{d.caso}</span>
                    {d.texto}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <MessageBubble
              key={m.id}
              message={m}
              selected={m.id === selected?.id}
              onSelect={() => setSelectedId(m.id)}
              onRetry={i === messages.length - 1 && m.error ? retry : undefined}
            />
          ))}
        </div>
        {error && !sending && (
          <div className="banner-error" role="alert">
            {error}
            <button className="btn small" onClick={retry}>
              Reintentar
            </button>
          </div>
        )}
        <form className="composer" onSubmit={submit}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKey}
            placeholder="Escribe tu pregunta… (Enter envía, Shift+Enter salto de línea)"
            rows={2}
            maxLength={4000}
            aria-label="Mensaje"
          />
          {sending ? (
            <button type="button" className="btn danger" onClick={cancel}>
              Detener
            </button>
          ) : (
            <button type="submit" className="btn primary" disabled={!draft.trim()}>
              Enviar
            </button>
          )}
        </form>
        <p className="muted tiny center">
          Hilo: <span className="mono">{threadId ?? "nuevo"}</span> · usuario <b>{userId}</b>
        </p>
      </section>

      <aside className="inspector" aria-label="Inspector del turno">
        <div className="tabs" role="tablist">
          {(["ruta", "herramientas", "fuentes", "hilo"] as const).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "tab active" : "tab"} onClick={() => setTab(t)}>
              {t === "ruta" ? "Router" : t === "herramientas" ? "Herramientas" : t === "fuentes" ? "Fuentes" : "Hilo"}
            </button>
          ))}
        </div>
        <div className="tab-body">
          {!selected && tab !== "hilo" && <p className="muted small">Envía un mensaje para ver la traza del turno.</p>}
          {selected && tab === "ruta" &&
            (selected.ruta ? <RouteDetail ruta={selected.ruta} /> : <p className="muted small">Esperando al router…</p>)}
          {selected && tab === "herramientas" && <ToolList tools={selected.tools ?? []} />}
          {selected && tab === "fuentes" && <SourceList sources={selected.sources ?? []} />}
          {tab === "hilo" &&
            (threadId ? (
              <>
                <p className="small">
                  El estado vive en <b>SqliteSaver</b> (corto plazo): reinicia el backend y recarga esta página; el hilo
                  sigue aquí. <i>Time travel</i>: bifurca desde un checkpoint anterior.
                </p>
                <TimeTravel threadId={threadId} userId={userId} />
              </>
            ) : (
              <p className="muted small">El hilo se crea con el primer mensaje.</p>
            ))}
        </div>
      </aside>
    </div>
  );
}

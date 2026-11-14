import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { MessageBubble } from "../components/MessageBubble";
import { RouteDetail } from "../components/RouteBadge";
import { SourceList } from "../components/Sources";
import { TimeTravel } from "../components/TimeTravel";
import { ToolList } from "../components/ToolList";
import { useSession } from "../hooks/session";
import { usePanel } from "../hooks/panels";
import { useChat } from "../hooks/useChat";

// Los cuatro casos de validación del Anuncio 006 + el transversal de blindaje.
const DEMO = [
  { caso: "Memoria", icon: "🧠", ruta: "memoria", texto: "Me llamo Ana y trabajo en Carvajal" },
  { caso: "Memoria", icon: "🧠", ruta: "memoria", texto: "¿Dónde trabajo?" },
  { caso: "RAG", icon: "📚", ruta: "rag", texto: "¿Qué es el proyecto de azúcar orgánica de RioCas?" },
  { caso: "Datos", icon: "📊", ruta: "datos", texto: "¿Cuánto vendió Riopaila en energía al cierre del tercer trimestre de 2023?" },
  {
    caso: "Mixto",
    icon: "🔀",
    ruta: "mixto",
    texto:
      "¿Qué meta de producción de alcohol para 2023 menciona el documento y cómo se compara con lo producido en el primer semestre de 2023 según los indicadores?",
  },
  { caso: "Blindaje", icon: "🛡️", ruta: "rag", texto: "¿Qué dice el corpus sobre la política de calidad?" },
  { caso: "Router", icon: "💬", ruta: "directo", texto: "Hola, buenas tardes" },
];

const CAPACIDADES = [
  { icon: "📚", titulo: "Documentos con cita", texto: "RAG híbrido en Qdrant + BM25" },
  { icon: "📊", titulo: "Cifras exactas", texto: "CSV con @tool; Python calcula" },
  { icon: "🧠", titulo: "Memoria", texto: "Del hilo y entre conversaciones" },
  { icon: "🛡️", titulo: "Blindaje", texto: "Ignora órdenes ocultas en documentos" },
];

export function ChatPage() {
  const { threadId = null } = useParams();
  const navigate = useNavigate();
  const { userId, refreshThreads } = useSession();
  const [draft, setDraft] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<"ruta" | "herramientas" | "fuentes" | "hilo">("ruta");
  const listRef = useRef<HTMLDivElement>(null);
  const [inspector, alternarInspector] = usePanel("inspector", true);

  const onThreadCreated = useCallback((id: string) => navigate(`/chat/${id}`, { replace: true }), [navigate]);
  const onTurnFinished = useCallback(() => void refreshThreads(), [refreshThreads]);
  const { messages, loading, sending, error, send, cancel, retry } = useChat({
    threadId,
    userId,
    onThreadCreated,
    onTurnFinished,
  });

  useEffect(() => {
    if (messages.length) listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
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
    <div className={`chat-layout ${inspector ? "" : "no-inspector"}`}>
      <section className="chat">
        <div className="chat-scroll" ref={listRef}>
          {loading && <p className="muted center">Cargando el hilo desde el checkpointer…</p>}
          {!loading && messages.length === 0 && (
            <div className="empty">
              <div className="hero-mark" aria-hidden>
                🌱
              </div>
              <h2>¿En qué te ayudo hoy?</h2>
              <p className="muted">
                Soy el asistente de Riopaila Castilla. Mira cómo pienso: cada respuesta muestra la ruta que eligió el
                router y las herramientas que usé.
              </p>
              <ul className="capabilities">
                {CAPACIDADES.map((c) => (
                  <li key={c.titulo}>
                    <span className="cap-icon" aria-hidden>
                      {c.icon}
                    </span>
                    <b>{c.titulo}</b>
                    <span className="muted tiny">{c.texto}</span>
                  </li>
                ))}
              </ul>
              <div className="section-title demo-title">Prueba un caso de la sustentación</div>
              <div className="demo-grid">
                {DEMO.map((d) => (
                  <button key={d.texto} className="demo" onClick={() => void send(d.texto)} disabled={sending}>
                    <span className={`route-badge route-${d.ruta}`}>
                      <span aria-hidden>{d.icon}</span> {d.caso}
                    </span>
                    <span className="demo-text">{d.texto}</span>
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

      {!inspector && (
        <button className="inspector-rail" onClick={alternarInspector} title="Mostrar el inspector del turno" aria-expanded={false}>
          <span aria-hidden>🔍</span>
          <span className="rail-text">Inspector</span>
        </button>
      )}
      {inspector && (
      <aside className="inspector" aria-label="Inspector del turno">
        <div className="tabs" role="tablist">
          {(["ruta", "herramientas", "fuentes", "hilo"] as const).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "tab active" : "tab"} onClick={() => setTab(t)}>
              {t === "ruta" ? "Router" : t === "herramientas" ? "Herramientas" : t === "fuentes" ? "Fuentes" : "Hilo"}
            </button>
          ))}
          <button className="tab tab-close" onClick={alternarInspector} title="Ocultar el inspector" aria-label="Ocultar el inspector">
            »
          </button>
        </div>
        <div className="tab-body">
          {!selected && tab !== "hilo" && <p className="muted small">Envía un mensaje para ver la traza del turno.</p>}
          {selected && tab === "ruta" &&
            (selected.ruta ? (
              <RouteDetail ruta={selected.ruta} />
            ) : (
              <p className="muted small">{selected.pending ? "Esperando al router…" : "Este turno no alcanzó a pasar por el router."}</p>
            ))}
          {selected && tab === "herramientas" && <ToolList tools={selected.tools ?? []} />}
          {selected && tab === "fuentes" && <SourceList sources={selected.sources ?? []} />}
          {tab === "hilo" &&
            (threadId ? (
              <>
                <p className="small muted">
                  Cada paso del grafo queda como checkpoint en <b>SqliteSaver</b>. <i>Time travel</i>: bifurca desde el
                  final de cualquier turno y la conversación sigue por otro camino sin tocar este hilo.
                </p>
                <TimeTravel
                  key={threadId}
                  threadId={threadId}
                  userId={userId}
                  preguntas={messages.filter((m) => m.role === "user").map((m) => m.content)}
                />
              </>
            ) : (
              <p className="muted small">El hilo se crea con el primer mensaje.</p>
            ))}
        </div>
      </aside>
      )}
    </div>
  );
}

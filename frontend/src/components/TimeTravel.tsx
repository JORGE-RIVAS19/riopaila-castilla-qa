import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useSession } from "../hooks/session";
import type { Checkpoint } from "../types";

/** Qué nodo del grafo iba a correr en cada checkpoint (el campo `siguiente` de LangGraph). */
const NODO: Record<string, { icon: string; label: string }> = {
  __start__: { icon: "📥", label: "Llega el mensaje" },
  router: { icon: "🧭", label: "Router" },
  agente: { icon: "🤖", label: "Agente ReAct" },
  directo: { icon: "💬", label: "Respuesta directa" },
  fin: { icon: "✅", label: "Turno completo" },
};

const nodo = (c: Checkpoint) => NODO[c.siguiente[0] ?? "fin"] ?? { icon: "⚙️", label: c.siguiente[0] };

export interface Turno {
  n: number;
  pasos: Checkpoint[];
  completo: Checkpoint | null;
}

/** Agrupa los checkpoints (vienen del más nuevo al más viejo) en turnos: cada `input` abre uno. */
export function agruparTurnos(cps: Checkpoint[]): Turno[] {
  const turnos: Turno[] = [];
  for (const c of [...cps].reverse()) {
    if (c.source === "input" || !turnos.length) turnos.push({ n: turnos.length + 1, pasos: [], completo: null });
    const t = turnos[turnos.length - 1];
    t.pasos.push(c);
    if (c.source === "loop" && c.siguiente.length === 0) t.completo = c;
  }
  return turnos.filter((t) => t.completo || t.pasos.some((p) => p.mensajes > 0));
}

const hora = (iso: string | null) =>
  iso ? new Date(iso).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }) : "";

export function TimeTravel({ threadId, userId, preguntas }: { threadId: string; userId: string; preguntas: string[] }) {
  const [cps, setCps] = useState<Checkpoint[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [forking, setForking] = useState<string | null>(null);
  const navigate = useNavigate();
  const { refreshThreads } = useSession();

  const load = useCallback(async () => {
    try {
      setCps(await api.checkpoints(threadId, userId));
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [threadId, userId]);

  useEffect(() => {
    void load(); // se recarga solo al cambiar de hilo
  }, [load]);

  const fork = async (cp: string) => {
    setForking(cp);
    try {
      const r = await api.fork(threadId, cp, userId);
      await refreshThreads();
      navigate(`/chat/${r.thread_id}`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setForking(null);
    }
  };

  if (err) return <p className="inline-error">{err}</p>;
  if (!cps) return <p className="muted small">Cargando checkpoints…</p>;
  const turnos = agruparTurnos(cps);
  const offset = preguntas.length - turnos.length; // tras un resumen el hilo conserva solo las últimas preguntas

  return (
    <div className="tt">
      <div className="tt-head">
        <span className="muted small">
          {turnos.length} turno(s) · {cps.length} checkpoints
        </span>
        <button className="btn small ghost" onClick={() => void load()} title="Volver a leer get_state_history">
          ↻ Actualizar
        </button>
      </div>
      <ol className="timeline">
        {[...turnos].reverse().map((t) => {
          const pregunta = preguntas[offset + t.n - 1];
          return (
            <li key={t.n} className={`tt-turn ${t.completo ? "" : "partial"}`}>
              <span className="tt-node" aria-hidden>
                {t.n}
              </span>
              <div className="tt-card">
                <div className="tt-q" title={pregunta}>
                  {pregunta ? `«${pregunta}»` : `Turno ${t.n}`}
                </div>
                <div className="tt-path" aria-label="Nodos del grafo en este turno">
                  {t.pasos.map((p, i) => {
                    const info = nodo(p);
                    return (
                      <span key={p.checkpoint_id ?? i} className="tt-chip" title={`paso ${p.step} · ${p.source} · ${p.mensajes} mensajes\n${info.label}`}>
                        {i > 0 && <span className="tt-arrow">›</span>}
                        <span aria-hidden>{info.icon}</span>
                      </span>
                    );
                  })}
                </div>
                <div className="tt-meta">
                  <span className="muted tiny">
                    {t.completo ? `${t.completo.mensajes} mensajes · ${hora(t.completo.creado)}` : "en curso"}
                  </span>
                  {t.completo?.checkpoint_id && (
                    <button
                      className="btn small fork"
                      disabled={forking !== null}
                      onClick={() => void fork(t.completo!.checkpoint_id!)}
                      title="Crea un hilo nuevo con la conversación hasta este turno"
                    >
                      {forking === t.completo.checkpoint_id ? <span className="spinner" /> : "⑂"} Bifurcar aquí
                    </button>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      <details className="tt-raw">
        <summary className="small muted">Ver los {cps.length} checkpoints crudos</summary>
        <ol className="checkpoints">
          {cps.map((c) => (
            <li key={c.checkpoint_id ?? `${c.step}`}>
              <span className="mono tiny">
                paso {c.step} · {c.source} · {c.mensajes} msj · {nodo(c).icon} {nodo(c).label}
              </span>
              {c.mensajes > 0 && c.checkpoint_id && (
                <button className="link" onClick={() => void fork(c.checkpoint_id!)} disabled={forking !== null}>
                  bifurcar
                </button>
              )}
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}

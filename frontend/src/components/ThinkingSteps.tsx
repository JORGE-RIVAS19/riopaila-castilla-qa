import type { ChatMessage, ToolRun } from "../types";
import { ROUTE_INFO } from "./RouteBadge";

type Estado = "running" | "done" | "error";

interface Paso {
  key: string;
  icon: string;
  titulo: string;
  detalle?: string;
  resultado?: string;
  estado: Estado;
  ms?: number;
}

const TOOL_TEXT: Record<string, { icon: string; titulo: string }> = {
  buscar_documentos: { icon: "📚", titulo: "Buscando en los documentos" },
  consultar_indicadores: { icon: "📊", titulo: "Consultando el CSV de indicadores" },
  comparar_cifras: { icon: "🧮", titulo: "Calculando en Python" },
  recordar_dato_usuario: { icon: "🧠", titulo: "Guardando en tu memoria" },
  infografia_riopaila: { icon: "🖼️", titulo: "Armando la infografía de Riopaila en cifras" },
  grafica_indicador: { icon: "📈", titulo: "Graficando el indicador por año" },
};

const fmt = (n: number) => n.toLocaleString("es-CO", { maximumFractionDigits: 2 });

function detalleDe(t: ToolRun): string | undefined {
  const a = t.args ?? {};
  if (t.name === "buscar_documentos" && a.consulta) return `«${String(a.consulta)}»`;
  if (t.name === "consultar_indicadores") {
    const partes = [a.indicador, a.anio, a.periodo].filter(Boolean).map(String);
    return partes.length ? partes.join(" · ").replaceAll("_", " ") : "catálogo completo";
  }
  if (t.name === "comparar_cifras" && a.etiqueta_a && a.etiqueta_b) return `${String(a.etiqueta_a)} vs ${String(a.etiqueta_b)}`;
  if (t.name === "recordar_dato_usuario" && a.clave) return `${String(a.clave)} = ${String(a.valor ?? "")}`;
  return undefined;
}

function resultadoDe(t: ToolRun): string | undefined {
  const a = t.artifact;
  if (!a || t.status !== "success") return undefined;
  if (t.name === "buscar_documentos" && a.hits) return `${a.hits.length} fragmentos`;
  if (t.name === "consultar_indicadores" && a.filas) return a.filas.length ? a.filas.map((f) => f.valor_legible).join(" · ") : "sin filas";
  if (t.name === "comparar_cifras" && typeof a.diferencia === "number") return `diferencia ${fmt(a.diferencia)}`;
  if (t.name === "recordar_dato_usuario" && a.guardado) return "guardado en el Store";
  return undefined;
}

/** Pasos del turno derivados de los eventos SSE que ya llegaron (router, herramientas, redacción). */
export function pasosDelTurno(m: ChatMessage): Paso[] {
  const pasos: Paso[] = [];
  if (!m.ruta) {
    pasos.push({ key: "router", icon: "🧭", titulo: "Decidiendo la ruta", detalle: "reglas primero; el LLM solo si hay duda", estado: m.pending ? "running" : "done" });
    return pasos;
  }
  const info = ROUTE_INFO[m.ruta.ruta];
  pasos.push({
    key: "router",
    icon: "🧭",
    titulo: `Ruta: ${info.icon} ${info.label}`,
    detalle: `${Math.round(m.ruta.confianza * 100)} % · ${m.ruta.metodo}`,
    estado: "done",
    ms: m.ruta.latencia_ms,
  });
  if (m.summarized) pasos.push({ key: "resumen", icon: "🗜️", titulo: "Resumiendo el historial", detalle: "SummarizationMiddleware", estado: "done" });
  for (const t of m.tools ?? []) {
    const txt = TOOL_TEXT[t.name] ?? { icon: "🛠️", titulo: t.name };
    pasos.push({
      key: t.id,
      icon: txt.icon,
      titulo: txt.titulo,
      detalle: detalleDe(t),
      resultado: resultadoDe(t),
      estado: t.status === "running" ? "running" : t.status === "error" ? "error" : "done",
      ms: t.latency_ms,
    });
  }
  if (m.verified)
    pasos.push({ key: "verif", icon: "🔢", titulo: "Verificador: borrador descartado", detalle: "traía cifras sin respaldo; se rehízo", estado: "done" });
  const herramientasListas = (m.tools ?? []).every((t) => t.status !== "running");
  if (m.pending && herramientasListas)
    pasos.push({
      key: "redactar",
      icon: "✍️",
      titulo: m.content ? "Redactando la respuesta" : m.ruta.ruta === "directo" ? "Respondiendo directo, sin herramientas" : "Preparando la respuesta",
      estado: "running",
    });
  return pasos;
}

function Paso({ p, i }: { p: Paso; i: number }) {
  return (
    <li className={`step step-${p.estado}`} style={{ animationDelay: `${Math.min(i, 6) * 40}ms` }}>
      <span className="step-dot" aria-hidden>
        {p.estado === "running" ? <span className="spinner" /> : p.estado === "error" ? "✕" : "✓"}
      </span>
      <span className="step-icon" aria-hidden>
        {p.icon}
      </span>
      <span className="step-body">
        <span className="step-title">{p.titulo}</span>
        {p.detalle && <span className="step-detail">{p.detalle}</span>}
        {p.resultado && <span className="step-result">→ {p.resultado}</span>}
      </span>
      {p.ms !== undefined && p.estado !== "running" && <span className="step-ms">{fmt(Math.round(p.ms))} ms</span>}
    </li>
  );
}

/** «Pensando…» en vivo: mientras el turno corre se ve cada paso; al terminar queda plegado como resumen. */
export function ThinkingSteps({ message: m }: { message: ChatMessage }) {
  const pasos = pasosDelTurno(m);
  const lista = (
    <ol className="steps" aria-live="polite">
      {pasos.map((p, i) => (
        <Paso key={p.key} p={p} i={i} />
      ))}
    </ol>
  );
  if (m.pending) return <div className="thinking live">{lista}</div>;
  if (pasos.length <= 1 && !(m.tools ?? []).length) return null; // ruta directa: no hay nada que contar
  const herramientas = (m.tools ?? []).length;
  return (
    <details className="thinking done">
      <summary>
        <span aria-hidden>🧩</span> Cómo lo resolví · {pasos.length} pasos
        {herramientas > 0 && ` · ${herramientas} herramienta${herramientas > 1 ? "s" : ""}`}
        {m.latency_ms !== undefined && ` · ${(m.latency_ms / 1000).toFixed(1)} s`}
      </summary>
      {lista}
    </details>
  );
}

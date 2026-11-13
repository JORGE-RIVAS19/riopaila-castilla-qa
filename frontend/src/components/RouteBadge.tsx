import type { RouteDecision, Ruta } from "../types";

export const ROUTE_INFO: Record<Ruta, { label: string; icon: string; hint: string }> = {
  directo: { label: "Directo", icon: "💬", hint: "Responde sin herramientas (saludo o dato del perfil)" },
  memoria: { label: "Memoria", icon: "🧠", hint: "Guarda un dato del usuario en el Store" },
  rag: { label: "RAG", icon: "📚", hint: "Busca en los documentos (Qdrant + BM25)" },
  datos: { label: "Datos", icon: "📊", hint: "Consulta exacta del CSV con @tool" },
  mixto: { label: "Mixto", icon: "🔀", hint: "Combina documentos y CSV" },
};

export function RouteBadge({ ruta, compact = false }: { ruta: RouteDecision; compact?: boolean }) {
  const info = ROUTE_INFO[ruta.ruta];
  return (
    <span className={`route-badge route-${ruta.ruta}`} title={`${info.hint}\n${ruta.razon}`}>
      <span aria-hidden>{info.icon}</span> {info.label}
      {!compact && <span className="route-conf">{Math.round(ruta.confianza * 100)}%</span>}
      {ruta.cautela && <span className="route-caution">cautela</span>}
    </span>
  );
}

export function RouteDetail({ ruta }: { ruta: RouteDecision }) {
  const signals = Object.entries(ruta.senales).filter(([, v]) => v > 0);
  return (
    <div className="route-detail">
      <div className="route-detail-head">
        <RouteBadge ruta={ruta} />
        <span className="muted">
          {ruta.metodo} · {ruta.latencia_ms} ms
        </span>
      </div>
      <p>{ruta.razon}</p>
      <div className="conf-bar" aria-label={`confianza ${Math.round(ruta.confianza * 100)}%`}>
        <span style={{ width: `${Math.round(ruta.confianza * 100)}%` }} />
      </div>
      {signals.length > 0 && (
        <div className="chips">
          {signals.map(([k, v]) => (
            <span key={k} className="chip">
              {k.replace("_", " ")} {v < 1 ? v.toFixed(2) : ""}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

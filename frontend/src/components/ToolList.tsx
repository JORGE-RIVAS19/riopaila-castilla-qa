import type { ToolRun } from "../types";

const TOOL_LABEL: Record<string, string> = {
  buscar_documentos: "📚 buscar_documentos",
  consultar_indicadores: "📊 consultar_indicadores",
  comparar_cifras: "🧮 comparar_cifras",
  recordar_dato_usuario: "🧠 recordar_dato_usuario",
  infografia_riopaila: "🖼️ infografia_riopaila",
  grafica_indicador: "📈 grafica_indicador",
};

function ToolResult({ t }: { t: ToolRun }) {
  const a = t.artifact;
  if (!a) return null;
  if (t.name === "consultar_indicadores" && a.filas) {
    if (!a.filas.length) return <p className="muted">Sin filas para esos filtros (no se estima nada).</p>;
    return (
      <table className="mini-table">
        <thead>
          <tr>
            <th>indicador</th>
            <th>periodo</th>
            <th>valor</th>
          </tr>
        </thead>
        <tbody>
          {a.filas.slice(0, 6).map((r) => (
            <tr key={r.id}>
              <td>
                <a href={r.fuente_url} target="_blank" rel="noreferrer">
                  {r.indicador}
                </a>
              </td>
              <td>
                {r.anio}-{r.periodo}
              </td>
              <td className="num">{r.valor_legible}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  if (t.name === "comparar_cifras" && typeof a.texto === "string") return <p className="mono small">{a.texto}</p>;
  if (t.name === "recordar_dato_usuario" && a.guardado)
    return (
      <p className="small">
        Guardado en el Store: <b>{a.clave}</b> = {a.valor}
      </p>
    );
  if (t.name === "buscar_documentos" && a.hits)
    return <p className="small muted">{a.hits.length} fragmentos · {String(a.latency_ms ?? "")} ms</p>;
  return null;
}

export function ToolList({ tools }: { tools: ToolRun[] }) {
  if (!tools.length) return <p className="muted small">Este turno no usó herramientas.</p>;
  return (
    <ol className="tool-list">
      {tools.map((t) => (
        <li key={t.id} className={`tool tool-${t.status}`}>
          <div className="tool-head">
            <span>{TOOL_LABEL[t.name] ?? t.name}</span>
            <span className="muted small">
              {t.status === "running" ? <span className="spinner" aria-label="ejecutando" /> : `${t.latency_ms ?? "–"} ms`}
            </span>
          </div>
          {Object.keys(t.args ?? {}).length > 0 && <code className="tool-args">{JSON.stringify(t.args)}</code>}
          <ToolResult t={t} />
        </li>
      ))}
    </ol>
  );
}

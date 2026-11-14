import type { ChatMessage, IndicadorRow } from "../types";

/**
 * Gráfica de las cifras que devolvió consultar_indicadores en el turno.
 * Se dibuja con las filas del artefacto de la herramienta (el CSV), nunca con el texto del LLM:
 * así la gráfica también es evidencia de que el modelo no inventa ni calcula cifras.
 */

const UNIDAD: Record<string, string> = {
  millones_cop: "millones COP",
  millones_litros: "millones de litros",
  porcentaje: "%",
  litros_dia: "litros/día",
  personas: "personas",
  vehiculos: "vehículos",
};

const fmt = (n: number) => n.toLocaleString("es-CO", { maximumFractionDigits: 2 });
const unidad = (u: string) => UNIDAD[u] ?? u.replaceAll("_", " ");
const nombre = (s: string) => {
  const t = s.replaceAll("_", " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
};
const periodo = (r: IndicadorRow) => (r.periodo === "anual" ? `${r.anio}` : `${r.anio} · ${r.periodo}`);
const prefijo = (r: IndicadorRow) => (r.calificador === "mas_de" ? "más de " : r.calificador === "cerca_de" ? "≈ " : "");

export function filasDelTurno(m: ChatMessage): IndicadorRow[] {
  const vistas = new Map<string, IndicadorRow>();
  for (const t of m.tools ?? []) {
    if (t.name !== "consultar_indicadores" || t.status !== "success") continue;
    for (const f of t.artifact?.filas ?? []) vistas.set(f.id, f);
  }
  return [...vistas.values()];
}

function Barras({ filas }: { filas: IndicadorRow[] }) {
  const orden = [...filas].sort((a, b) => a.anio - b.anio || a.periodo.localeCompare(b.periodo));
  const max = Math.max(...orden.map((f) => f.valor));
  return (
    <ul className="bars" role="list">
      {orden.map((f) => {
        const pct = max > 0 ? (f.valor / max) * 100 : 0;
        return (
          <li key={f.id} className="bar-row" title={`${f.descripcion}\n${prefijo(f)}${fmt(f.valor)} ${unidad(f.unidad)} · ${f.id}`}>
            <span className="bar-label">{periodo(f)}</span>
            <span className="bar-track">
              <span className={`bar-fill ${f.calificador === "mas_de" ? "open" : ""}`} style={{ width: `${Math.max(pct, 2)}%` }} />
            </span>
            <span className="bar-value">
              {prefijo(f)}
              <b>{fmt(f.valor)}</b>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function Tile({ f }: { f: IndicadorRow }) {
  return (
    <div className="stat-tile">
      <span className="stat-value">
        {prefijo(f) && <span className="stat-qual">{prefijo(f)}</span>}
        {fmt(f.valor)}
        <span className="stat-unit"> {unidad(f.unidad)}</span>
      </span>
      <span className="muted small">
        {nombre(f.indicador)} · {periodo(f)}
      </span>
    </div>
  );
}

export function DataChart({ message: m }: { message: ChatMessage }) {
  const filas = filasDelTurno(m);
  if (!filas.length) return null;
  const grupos = new Map<string, IndicadorRow[]>();
  for (const f of filas) {
    const k = `${f.indicador}|${f.unidad}`;
    grupos.set(k, [...(grupos.get(k) ?? []), f]);
  }
  const comparacion = (m.tools ?? []).find((t) => t.name === "comparar_cifras" && t.status === "success");
  const dif = comparacion?.artifact?.diferencia;
  const aprox = filas.some((f) => f.calificador !== "exacto");
  const fuentes = [...new Set(filas.map((f) => f.fuente_url))];

  return (
    <figure className="data-chart">
      {[...grupos.entries()].slice(0, 3).map(([k, fs]) => (
        <div key={k} className="chart-group">
          <figcaption>
            <b>{nombre(fs[0].indicador)}</b> <span className="muted">· {unidad(fs[0].unidad)}</span>
          </figcaption>
          {fs.length > 1 ? <Barras filas={fs} /> : <Tile f={fs[0]} />}
        </div>
      ))}
      {typeof dif === "number" && (
        <div className="delta">
          <span className="delta-icon" aria-hidden>
            🧮
          </span>
          <span>
            Diferencia <b>{fmt(Math.abs(dif))}</b>
            {comparacion?.args?.unidad ? ` ${unidad(String(comparacion.args.unidad))}` : ""}
            {aprox && <span className="muted"> (aprox., una cifra es «más de»)</span>}
          </span>
          <span className="muted tiny">calculada en Python · comparar_cifras</span>
        </div>
      )}
      <p className="chart-foot tiny muted">
        📊 Gráfica hecha con las filas del CSV que devolvió la herramienta, no con el texto del modelo ·{" "}
        {fuentes.map((u, i) => (
          <span key={u}>
            {i > 0 && " · "}
            <a href={u} target="_blank" rel="noreferrer">
              fuente {i + 1}
            </a>
          </span>
        ))}
      </p>
    </figure>
  );
}

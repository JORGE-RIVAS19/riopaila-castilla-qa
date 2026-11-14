import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { IndicadorRow } from "../types";

export function DataPage() {
  const [rows, setRows] = useState<IndicadorRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [cat, setCat] = useState("todas");

  useEffect(() => {
    api.indicadores().then(setRows).catch((e: Error) => setErr(e.message));
  }, []);

  const cats = useMemo(() => ["todas", ...Array.from(new Set(rows.map((r) => r.categoria)))], [rows]);
  const shown = rows.filter((r) => cat === "todas" || r.categoria === cat);

  return (
    <div className="page">
      <h1>📊 Datos estructurados</h1>
      <p className="muted">
        <code>data/structured/indicadores_riopaila.csv</code>: {rows.length} cifras públicas tomadas de las noticias del
        sitio, cada una con su URL de origen. La herramienta <code>consultar_indicadores</code> filtra estas filas
        (esquema Pydantic) y <code>comparar_cifras</code> hace la aritmética en Python: el LLM no calcula ni inventa.
      </p>
      {err && <div className="banner-error">{err}</div>}
      <div className="chips">
        {cats.map((c) => (
          <button key={c} className={`chip button ${cat === c ? "on" : ""}`} onClick={() => setCat(c)}>
            {c}
          </button>
        ))}
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>id</th>
              <th>indicador</th>
              <th>año</th>
              <th>periodo</th>
              <th>valor</th>
              <th>descripción</th>
              <th>fuente</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id}>
                <td className="mono small">{r.id}</td>
                <td>{r.indicador}</td>
                <td>{r.anio}</td>
                <td>{r.periodo}</td>
                <td className="num">{r.valor_legible}</td>
                <td className="small">{r.descripcion}</td>
                <td>
                  <a href={r.fuente_url} target="_blank" rel="noreferrer">
                    noticia ↗
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

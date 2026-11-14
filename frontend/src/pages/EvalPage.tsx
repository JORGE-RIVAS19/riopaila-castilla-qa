import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";

interface ModeResult {
  [metric: string]: unknown;
  detalle: { id: string; consulta: string; recall: number; ndcg: number; top3: string[] }[];
}

interface EvalData {
  fecha: string;
  k: number;
  embeddings: string;
  consultas: number;
  indice: { coleccion?: string; modo?: string };
  modos: Record<string, ModeResult>;
}

type SearchRes = Awaited<ReturnType<typeof api.search>>;

export function EvalPage() {
  const [data, setData] = useState<EvalData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("¿Qué es el bagazo y cómo se aprovecha?");
  const [mode, setMode] = useState("hibrida");
  const [res, setRes] = useState<SearchRes | null>(null);

  useEffect(() => {
    api
      .retrievalEval()
      .then((d) => setData(d as unknown as EvalData))
      .catch((e: Error) => setErr(e.message));
  }, []);

  const search = async (e: FormEvent) => {
    e.preventDefault();
    try {
      setRes(await api.search(q, mode, 10));
    } catch (x) {
      setErr((x as Error).message);
    }
  };

  const k = data?.k ?? 10;
  return (
    <div className="page">
      <h1>🎯 Evaluación del retrieval</h1>
      <p className="muted">
        {data ? `${data.consultas} consultas etiquetadas · embeddings ${data.embeddings} · ${data.indice.modo} · ${data.fecha}` : "Resultados de scripts/eval_retrieval.py"}
      </p>
      {err && <div className="banner-error">{err}</div>}
      {data && (
        <div className="metric-grid">
          {Object.entries(data.modos).map(([m, r]) => (
            <div key={m} className={`metric-card ${m === "hibrida" ? "best" : ""}`}>
              <h3>{m}</h3>
              <div className="metric">
                <span>{Number(r[`recall@${k}`]).toFixed(3)}</span>recall@{k}
              </div>
              <div className="metric">
                <span>{Number(r[`ndcg@${k}`]).toFixed(3)}</span>nDCG@{k}
              </div>
              <div className="metric small">
                MRR {Number(r.mrr).toFixed(3)} · {String(r.latencia_media_ms)} ms
              </div>
            </div>
          ))}
        </div>
      )}
      <h2>Probar el top-k en vivo</h2>
      <form className="row gap" onSubmit={search}>
        <input className="grow" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="hibrida">híbrida (RRF)</option>
          <option value="densa">densa (Qdrant)</option>
          <option value="lexica">léxica (BM25)</option>
        </select>
        <button className="btn primary">Buscar</button>
      </form>
      {res && (
        <ol className="sources">
          {res.hits.map((h) => (
            <li key={h.rank} className="source">
              <div className="source-head">
                <span className="cite">#{h.rank}</span>
                <a href={h.chunk.url} target="_blank" rel="noreferrer">
                  {h.chunk.titulo}
                </a>
              </div>
              <div className="chips">
                <span className="chip">{h.chunk.seccion}</span>
                {h.dense_rank && <span className="chip">densa #{h.dense_rank}</span>}
                {h.lexical_rank && <span className="chip">BM25 #{h.lexical_rank}</span>}
                <span className="chip">score {h.score.toFixed(4)}</span>
              </div>
            </li>
          ))}
        </ol>
      )}
      {data?.modos.hibrida && (
        <>
          <h2>Detalle por consulta (híbrida)</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>id</th>
                  <th>consulta</th>
                  <th>recall</th>
                  <th>nDCG</th>
                </tr>
              </thead>
              <tbody>
                {data.modos.hibrida.detalle.map((d) => (
                  <tr key={d.id} className={d.recall === 0 ? "row-bad" : ""}>
                    <td className="mono small">{d.id}</td>
                    <td>{d.consulta}</td>
                    <td className="num">{d.recall.toFixed(2)}</td>
                    <td className="num">{d.ndcg.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

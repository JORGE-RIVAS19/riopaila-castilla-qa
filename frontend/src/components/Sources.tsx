import { useState } from "react";
import type { ShieldFinding, SourceHit } from "../types";

export function ShieldAlert({ findings }: { findings: ShieldFinding[] }) {
  if (!findings.length) return null;
  return (
    <div className="shield" role="alert">
      <b>🛡️ Blindaje del RAG:</b> {findings.length} instrucción(es) oculta(s) en documentos recuperados. Se trataron
      como datos pasivos y no se obedecieron.
      <ul>
        {findings.map((f, i) => (
          <li key={i}>
            <span className="chip warn">{f.motivo}</span> <i>“{f.fragmento}”</i> — {f.titulo}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SourceList({ sources }: { sources: SourceHit[] }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!sources.length) return <p className="muted small">Sin documentos recuperados en este turno.</p>;
  return (
    <ol className="sources">
      {sources.map((s) => (
        <li key={s.chunk_id + s.n} className={s.origen === "sintetico" ? "source synthetic" : "source"}>
          <div className="source-head">
            <span className="cite">[{s.n}]</span>
            <a href={s.url.startsWith("http") ? s.url : undefined} target="_blank" rel="noreferrer">
              {s.titulo}
            </a>
          </div>
          <div className="chips">
            <span className="chip">{s.seccion}</span>
            {s.dense_rank && <span className="chip">densa #{s.dense_rank}</span>}
            {s.lexical_rank && <span className="chip">BM25 #{s.lexical_rank}</span>}
            <span className="chip">RRF {s.score.toFixed(4)}</span>
            {s.origen === "sintetico" && <span className="chip warn">documento de prueba</span>}
          </div>
          <button className="link" onClick={() => setOpen(open === s.chunk_id ? null : s.chunk_id)}>
            {open === s.chunk_id ? "Ocultar fragmento" : `Ver fragmento ${s.chunk_id}`}
          </button>
          {open === s.chunk_id && <pre className="fragment">{s.fragmento}</pre>}
        </li>
      ))}
    </ol>
  );
}

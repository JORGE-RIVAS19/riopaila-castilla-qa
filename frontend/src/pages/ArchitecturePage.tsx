import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useSession } from "../hooks/session";

const ARQ = `flowchart LR
  U[Usuario] --> FE[Frontend React<br/>Vite + TS]
  FE -- HTTP + SSE --> API[FastAPI<br/>api/main.py]
  API --> G{{LangGraph<br/>router → directo / agente}}
  G --> R[Router<br/>reglas + LLM]
  G --> A[create_agent<br/>@tool + middleware]
  A --> T1[buscar_documentos] --> Q[(Qdrant<br/>+ BM25)]
  A --> T2[consultar_indicadores] --> CSV[(CSV indicadores)]
  A --> T3[comparar_cifras]
  A --> T4[recordar_dato_usuario] --> ST[(SqliteStore<br/>largo plazo)]
  G --> CP[(SqliteSaver<br/>checkpointer)]
  G -. trazas .-> LS[LangSmith / logs JSONL]`;

function Mermaid({ code, id }: { code: string; id: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" });
        const { svg } = await mermaid.render(`${id}-${Math.random().toString(36).slice(2, 8)}`, code);
        if (alive && ref.current) ref.current.innerHTML = svg;
      })
      .catch((e: Error) => alive && setErr(e.message));
    return () => {
      alive = false;
    };
  }, [code, id]);
  return err ? <pre className="fragment">{code}</pre> : <div ref={ref} className="mermaid-box" />;
}

export function ArchitecturePage() {
  const { health } = useSession();
  const [graph, setGraph] = useState<string | null>(null);
  useEffect(() => {
    api
      .graph()
      .then((g) => setGraph(g.mermaid))
      .catch(() => setGraph(null));
  }, []);
  return (
    <div className="page">
      <h1>🧩 Arquitectura</h1>
      <p className="muted">Frontend propio desacoplado: la interfaz nunca llama al modelo; todo pasa por la API.</p>
      <Mermaid code={ARQ} id="arq" />
      <h2>Grafo compilado del agente (desde el backend)</h2>
      {graph ? <Mermaid code={graph} id="grafo" /> : <p className="muted">Backend no disponible.</p>}
      {health && (
        <>
          <h2>Configuración en vivo</h2>
          <table className="table">
            <tbody>
              <tr>
                <td>LLM</td>
                <td>
                  {health.llm.proveedor} · {health.llm.modelo}
                </td>
              </tr>
              <tr>
                <td>Router</td>
                <td>{health.router}</td>
              </tr>
              <tr>
                <td>Embeddings</td>
                <td>{health.embeddings}</td>
              </tr>
              <tr>
                <td>Índice Qdrant</td>
                <td>
                  {health.indice.coleccion ?? "no disponible"} · {health.indice.puntos ?? 0} vectores · {health.indice.modo}
                </td>
              </tr>
              <tr>
                <td>Limpieza de chunks</td>
                <td className="small">{JSON.stringify(health.limpieza_chunks)}</td>
              </tr>
              <tr>
                <td>Memoria</td>
                <td>
                  {health.memoria.checkpointer} (corto plazo) · {health.memoria.store} (largo plazo)
                </td>
              </tr>
              <tr>
                <td>LangSmith</td>
                <td>{health.langsmith.activo ? `activo · proyecto ${health.langsmith.proyecto}` : "apagado (trazas en logs/trazas.jsonl)"}</td>
              </tr>
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

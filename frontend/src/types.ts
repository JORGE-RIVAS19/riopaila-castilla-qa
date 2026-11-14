// Contratos que devuelve el backend FastAPI (ver api/schemas.py y agent/service.py).

export type Ruta = "directo" | "memoria" | "rag" | "datos" | "mixto";

export interface RouteDecision {
  ruta: Ruta;
  confianza: number;
  razon: string;
  metodo: "reglas" | "llm" | "reglas+llm";
  cautela: boolean;
  senales: Record<string, number>;
  latencia_ms: number;
}

export interface SourceHit {
  n: number;
  chunk_id: string;
  titulo: string;
  url: string;
  seccion: string;
  origen: "corpus" | "sintetico";
  score: number;
  dense_rank: number | null;
  lexical_rank: number | null;
  fragmento: string;
}

export interface ShieldFinding {
  chunk_id: string;
  titulo: string;
  motivo: string;
  fragmento: string;
}

export interface IndicadorRow {
  id: string;
  indicador: string;
  categoria: string;
  anio: number;
  periodo: string;
  valor: number;
  unidad: string;
  calificador: string;
  descripcion: string;
  fuente_url: string;
  valor_legible: string;
}

export interface ToolRun {
  id: string;
  name: string;
  args: Record<string, unknown>;
  status: "running" | "success" | "error";
  latency_ms?: number;
  artifact?: {
    hits?: SourceHit[];
    shield?: ShieldFinding[];
    filas?: IndicadorRow[];
    total?: number;
    texto?: string;
    guardado?: boolean;
    clave?: string;
    valor?: string;
    [k: string]: unknown;
  };
}

export interface ChatMessage {
  id: string;
  /** "summary": resumen que SummarizationMiddleware dejó en lugar de los turnos antiguos. */
  role: "user" | "assistant" | "summary";
  content: string;
  ruta?: RouteDecision | null;
  tools?: ToolRun[];
  sources?: SourceHit[];
  shield?: ShieldFinding[];
  latency_ms?: number;
  error?: string | null;
  pending?: boolean;
  /** El historial se resumió durante este turno. */
  summarized?: boolean;
}

export interface ThreadSummary {
  thread_id: string;
  titulo?: string | null;
  creado?: string | null;
  actualizado?: string | null;
  turnos: number;
}

export interface RawThreadMessage {
  role: "user" | "assistant" | "tool" | "tool_call" | "summary";
  id?: string;
  content?: string;
  name?: string;
  tool_call_id?: string;
  artifact?: ToolRun["artifact"] | null;
  tool_calls?: { id: string; name: string; args: Record<string, unknown> }[];
  ruta?: RouteDecision | null;
}

export interface MemoryFact {
  key: string;
  clave: string;
  valor: string;
  hilo_origen?: string | null;
  actualizado?: string | null;
}

export interface Health {
  estado: string;
  llm: { proveedor: string; modelo: string };
  router: string;
  embeddings: string;
  indice: { disponible: boolean; coleccion?: string; puntos?: number; modo?: string; dimensiones?: number };
  limpieza_chunks: Record<string, number>;
  memoria: { checkpointer: string; store: string };
  langsmith: { activo: boolean; proyecto: string };
  indicadores: number;
}

export interface Checkpoint {
  checkpoint_id: string | null;
  step: number | null;
  source: string | null;
  mensajes: number;
  siguiente: string[];
  creado: string | null;
}

// Eventos SSE de /api/chat/stream
export type StreamEvent =
  | { type: "start"; thread_id: string; user_id: string; turn_id: string }
  | ({ type: "route" } & RouteDecision)
  | { type: "tool_start"; id: string; name: string; args: Record<string, unknown> }
  | { type: "tool_end"; id: string; name: string; latency_ms: number; status: string; artifact: ToolRun["artifact"] }
  | { type: "token"; text: string }
  | { type: "summary" }
  | { type: "error"; message: string }
  | {
      type: "final";
      thread_id: string;
      content: string;
      ruta: RouteDecision | null;
      fuentes: SourceHit[];
      blindaje: ShieldFinding[];
      latency_ms: number;
      error: string | null;
      resumen?: boolean;
    };

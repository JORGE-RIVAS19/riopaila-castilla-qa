import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../types";
import { RouteBadge } from "./RouteBadge";
import { ShieldAlert } from "./Sources";
import { ThinkingSteps } from "./ThinkingSteps";

interface Props {
  message: ChatMessage;
  selected: boolean;
  onSelect: () => void;
  onRetry?: () => void;
}

export function MessageBubble({ message: m, selected, onSelect, onRetry }: Props) {
  if (m.role === "summary") {
    return (
      <details className="msg summary-note">
        <summary>🗜️ Resumen automático de los turnos anteriores (SummarizationMiddleware)</summary>
        <div className="markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
        </div>
      </details>
    );
  }
  if (m.role === "user") {
    return (
      <div className="msg msg-user">
        <div className="bubble">{m.content}</div>
      </div>
    );
  }
  const toolsUsed = (m.tools ?? []).length;
  return (
    <div className={`msg msg-assistant ${selected ? "selected" : ""}`}>
      <div className="avatar" aria-hidden>
        🌱
      </div>
      <div className="bubble" onClick={onSelect} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onSelect()}>
        <div className="bubble-meta">
          {m.ruta && <RouteBadge ruta={m.ruta} compact />}
          {(m.sources ?? []).length > 0 && <span className="muted small">📎 {(m.sources ?? []).length} fuentes</span>}
          {m.summarized && (
            <span className="muted small" title="La conversación superó el umbral de tokens y se resumió">
              🗜️ historial resumido
            </span>
          )}
          {m.verified && (
            <span
              className="muted small"
              title="El borrador traía números que no salieron de una herramienta: el verificador lo descartó y el agente lo rehízo con comparar_cifras"
            >
              🔢 cifras verificadas
            </span>
          )}
          {m.latency_ms !== undefined && toolsUsed === 0 && (
            <span className="muted small">⏱️ {(m.latency_ms / 1000).toFixed(1)} s</span>
          )}
        </div>
        <ThinkingSteps message={m} />
        {m.content && (
          <div className={`markdown ${m.pending ? "streaming" : ""}`}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
          </div>
        )}
        <ShieldAlert findings={m.shield ?? []} />
        {m.error && (
          <div className="inline-error">
            ⚠️ {m.error}
            {onRetry && (
              <button className="btn small" onClick={onRetry}>
                Reintentar
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

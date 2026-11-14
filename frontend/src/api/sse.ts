import type { StreamEvent } from "../types";

/**
 * Parser incremental de Server-Sent Events.
 * El backend responde a un POST con `text/event-stream`; EventSource solo admite GET,
 * así que leemos el cuerpo con fetch + ReadableStream y separamos los bloques "\n\n".
 */
export class SSEParser {
  private buffer = "";

  push(chunk: string): StreamEvent[] {
    this.buffer += chunk.replace(/\r\n/g, "\n");
    const events: StreamEvent[] = [];
    let idx: number;
    while ((idx = this.buffer.indexOf("\n\n")) !== -1) {
      const block = this.buffer.slice(0, idx);
      this.buffer = this.buffer.slice(idx + 2);
      const data = block
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trimStart())
        .join("\n");
      if (!data) continue;
      try {
        events.push(JSON.parse(data) as StreamEvent);
      } catch {
        // bloque incompleto o corrupto: se ignora sin tumbar la conversación
      }
    }
    return events;
  }
}

import { describe, expect, it } from "vitest";
import { fromThread } from "../hooks/useChat";

describe("fromThread", () => {
  it("agrupa herramientas y fuentes en la respuesta del asistente", () => {
    const msgs = fromThread([
      { role: "user", content: "¿Qué es RioCas?", id: "u1" },
      { role: "tool_call", tool_calls: [{ id: "c1", name: "buscar_documentos", args: { consulta: "RioCas" } }] },
      {
        role: "tool",
        tool_call_id: "c1",
        name: "buscar_documentos",
        artifact: { hits: [{ n: 1, chunk_id: "x", titulo: "RioCas", url: "u", seccion: "noticias", origen: "corpus", score: 1, dense_rank: 1, lexical_rank: 2, fragmento: "…" }], shield: [] },
      },
      { role: "assistant", content: "RioCas es… [1]", id: "a1", ruta: null },
    ]);
    expect(msgs).toHaveLength(2);
    expect(msgs[1].tools?.[0].name).toBe("buscar_documentos");
    expect(msgs[1].sources).toHaveLength(1);
  });

  it("muestra el resumen de SummarizationMiddleware como nota y no como mensaje del usuario", () => {
    const msgs = fromThread([
      { role: "summary", content: "Jorge preguntó por la historia de Riopaila.", id: "s1" },
      { role: "user", content: "¿Y las ventas de energía?", id: "u2" },
      { role: "assistant", content: "21.342 millones COP", id: "a2", ruta: null },
    ]);
    expect(msgs.map((m) => m.role)).toEqual(["summary", "user", "assistant"]);
    expect(msgs[0].content).toContain("Riopaila");
  });
});

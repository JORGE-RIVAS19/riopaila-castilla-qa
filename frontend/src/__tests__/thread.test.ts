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
});

import { describe, expect, it } from "vitest";
import { pasosDelTurno } from "../components/ThinkingSteps";
import type { ChatMessage } from "../types";

const ruta = { ruta: "datos" as const, confianza: 0.85, razon: "x", metodo: "reglas+llm" as const, cautela: false, senales: {}, latencia_ms: 812 };

describe("pasosDelTurno", () => {
  it("antes del router solo muestra «Decidiendo la ruta» en curso", () => {
    const m: ChatMessage = { id: "a", role: "assistant", content: "", pending: true };
    expect(pasosDelTurno(m).map((p) => [p.key, p.estado])).toEqual([["router", "running"]]);
  });

  it("encadena router, herramientas y redacción con sus resultados", () => {
    const m: ChatMessage = {
      id: "a",
      role: "assistant",
      content: "En 2022…",
      pending: true,
      ruta,
      tools: [
        { id: "k1", name: "consultar_indicadores", args: { indicador: "utilidad_neta", anio: 2022 }, status: "success", latency_ms: 14, artifact: { filas: [{ valor_legible: "93.241 millones cop" } as never] } },
        { id: "k3", name: "comparar_cifras", args: { etiqueta_a: "2022", etiqueta_b: "2023" }, status: "running" },
      ],
    };
    const pasos = pasosDelTurno(m);
    expect(pasos.map((p) => p.key)).toEqual(["router", "k1", "k3"]);
    expect(pasos[1].resultado).toBe("93.241 millones cop");
    expect(pasos[2].estado).toBe("running");
    const listo = pasosDelTurno({ ...m, tools: [m.tools![0]] });
    expect(listo.at(-1)?.titulo).toBe("Redactando la respuesta");
  });
});

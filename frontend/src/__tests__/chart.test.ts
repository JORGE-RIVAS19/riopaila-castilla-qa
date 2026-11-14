import { describe, expect, it } from "vitest";
import { filasDelTurno } from "../components/DataChart";
import type { ChatMessage, IndicadorRow } from "../types";

const fila = (id: string, anio: number): IndicadorRow => ({
  id, indicador: "utilidad_neta", categoria: "financiero", anio, periodo: "anual", valor: 1, unidad: "millones_cop",
  calificador: "exacto", descripcion: "", fuente_url: "u", valor_legible: "1",
});

describe("filasDelTurno", () => {
  it("toma solo filas de consultar_indicadores exitosas y sin duplicados", () => {
    const m: ChatMessage = {
      id: "a", role: "assistant", content: "",
      tools: [
        { id: "1", name: "consultar_indicadores", args: {}, status: "success", artifact: { filas: [fila("IND-003", 2022)] } },
        { id: "2", name: "consultar_indicadores", args: {}, status: "success", artifact: { filas: [fila("IND-003", 2022), fila("IND-019", 2023)] } },
        { id: "3", name: "consultar_indicadores", args: {}, status: "error", artifact: { filas: [fila("IND-999", 2024)] } },
        { id: "4", name: "buscar_documentos", args: {}, status: "success", artifact: { hits: [] } },
      ],
    };
    expect(filasDelTurno(m).map((f) => f.id)).toEqual(["IND-003", "IND-019"]);
  });
});

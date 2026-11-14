import { describe, expect, it } from "vitest";
import { agruparHilos, haceCuanto } from "../components/Layout";
import { agruparTurnos } from "../components/TimeTravel";
import type { Checkpoint } from "../types";

const cp = (step: number, source: string, mensajes: number, siguiente: string[]): Checkpoint => ({
  checkpoint_id: `cp${step}`, step, source, mensajes, siguiente, creado: null,
});

describe("time travel", () => {
  it("agrupa los checkpoints en turnos y marca el final de cada uno", () => {
    // del más nuevo al más viejo, como los devuelve get_state_history
    const cps = [cp(5, "loop", 4, []), cp(4, "loop", 3, ["agente"]), cp(3, "input", 2, ["__start__"]), cp(2, "loop", 2, []), cp(1, "loop", 1, ["router"]), cp(-1, "input", 0, ["__start__"])];
    const turnos = agruparTurnos(cps);
    expect(turnos.map((t) => t.completo?.checkpoint_id)).toEqual(["cp2", "cp5"]);
  });
});

describe("barra de hilos", () => {
  it("dice hace cuánto se usó cada hilo", () => {
    const ahora = Date.parse("2026-11-13T21:00:00");
    expect(haceCuanto("2026-11-13T20:55:00", ahora)).toBe("hace 5 min");
    expect(haceCuanto("2026-11-13T18:00:00", ahora)).toBe("hace 3 h");
    expect(haceCuanto("2026-11-12T20:00:00", ahora)).toBe("ayer");
  });

  it("agrupa en Hoy / Ayer / Antes", () => {
    const ahora = new Date("2026-11-13T21:00:00");
    const t = (id: string, iso: string) => ({ thread_id: id, turnos: 1, actualizado: iso });
    const g = agruparHilos([t("a", "2026-11-13T10:00:00"), t("b", "2026-11-12T10:00:00"), t("c", "2026-11-01T10:00:00")], ahora);
    expect(g.map(([k, v]) => [k, v.map((x) => x.thread_id)])).toEqual([["Hoy", ["a"]], ["Ayer", ["b"]], ["Antes", ["c"]]]);
  });
});

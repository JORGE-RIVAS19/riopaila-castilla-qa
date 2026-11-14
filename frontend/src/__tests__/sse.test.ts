import { describe, expect, it } from "vitest";
import { SSEParser } from "../api/sse";

describe("SSEParser", () => {
  it("arma eventos aunque lleguen partidos en varios chunks", () => {
    const p = new SSEParser();
    expect(p.push('event: token\ndata: {"type":"token","te')).toEqual([]);
    const evs = p.push('xt":"Hola"}\n\nevent: final\ndata: {"type":"final","thread_id":"t1"}\n\n');
    expect(evs.map((e) => e.type)).toEqual(["token", "final"]);
  });

  it("ignora bloques corruptos sin romper el stream", () => {
    const p = new SSEParser();
    expect(p.push("data: {roto\n\ndata: {\"type\":\"token\",\"text\":\"ok\"}\n\n")).toHaveLength(1);
  });
});

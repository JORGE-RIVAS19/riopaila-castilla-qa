import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import { useSession } from "../hooks/session";
import type { MemoryFact } from "../types";

export function MemoryPage() {
  const { userId } = useSession();
  const [facts, setFacts] = useState<MemoryFact[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [clave, setClave] = useState("");
  const [valor, setValor] = useState("");

  const load = useCallback(async () => {
    try {
      setFacts(await api.memory(userId));
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!clave.trim() || !valor.trim()) return;
    await api.putMemory(userId, clave, valor).catch((x: Error) => setErr(x.message));
    setClave("");
    setValor("");
    void load();
  };

  return (
    <div className="page">
      <h1>🧠 Memoria de largo plazo</h1>
      <p className="muted">
        Namespace <code>("usuarios", "{userId}", "perfil")</code> del <b>Store</b> (SqliteStore). Lo que el agente guarda
        con <code>recordar_dato_usuario</code> se recupera con <code>store.search()</code> en cualquier hilo nuevo del mismo
        usuario. La memoria de corto plazo (el hilo) vive aparte, en el checkpointer.
      </p>
      {err && <div className="banner-error">{err}</div>}
      <table className="table">
        <thead>
          <tr>
            <th>clave</th>
            <th>valor</th>
            <th>hilo de origen</th>
            <th>actualizado</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {facts.length === 0 && (
            <tr>
              <td colSpan={5} className="muted">
                Sin datos. Prueba en el chat: «Me llamo Ana y trabajo en Carvajal».
              </td>
            </tr>
          )}
          {facts.map((f) => (
            <tr key={f.key}>
              <td>
                <b>{f.clave}</b>
              </td>
              <td>{f.valor}</td>
              <td className="mono small">{f.hilo_origen?.slice(0, 8) ?? "manual"}</td>
              <td className="small">{f.actualizado?.replace("T", " ").slice(0, 16)}</td>
              <td>
                <button className="btn icon ghost" title="Olvidar" onClick={() => void api.deleteMemory(userId, f.key).then(load)}>
                  ✕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form className="row gap" onSubmit={add}>
        <input placeholder="clave (p. ej. cargo)" value={clave} onChange={(e) => setClave(e.target.value)} />
        <input placeholder="valor" value={valor} onChange={(e) => setValor(e.target.value)} />
        <button className="btn" type="submit">
          Guardar
        </button>
      </form>
    </div>
  );
}

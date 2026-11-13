import { useState, type FormEvent } from "react";
import { NavLink, Outlet, useMatch, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useSession } from "../hooks/session";

function StatusPill() {
  const { health, healthError } = useSession();
  if (healthError) return <span className="pill pill-bad" title={healthError}>● backend sin conexión</span>;
  if (!health) return <span className="pill">● conectando…</span>;
  return (
    <span
      className={`pill ${health.indice.disponible ? "pill-ok" : "pill-warn"}`}
      title={`Índice: ${health.indice.coleccion ?? "no disponible"}\nEmbeddings: ${health.embeddings}\nLangSmith: ${health.langsmith.activo ? health.langsmith.proyecto : "apagado"}`}
    >
      ● {health.llm.modelo} {health.indice.disponible ? `· ${health.indice.puntos} vectores` : "· sin índice"}
      {health.langsmith.activo && " · LangSmith"}
    </span>
  );
}

function UserSwitcher() {
  const { userId, setUserId } = useSession();
  const [draft, setDraft] = useState(userId);
  const navigate = useNavigate();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setUserId(draft);
    navigate("/chat");
  };
  return (
    <form className="user-switch" onSubmit={submit}>
      <label htmlFor="user">Usuario (memoria de largo plazo)</label>
      <div className="row">
        <input id="user" value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={40} />
        <button className="btn small" type="submit" disabled={draft.trim().toLowerCase() === userId}>
          Usar
        </button>
      </div>
    </form>
  );
}

export function Layout() {
  const { threads, userId, refreshThreads } = useSession();
  const threadId = useMatch("/chat/:threadId")?.params.threadId;
  const navigate = useNavigate();
  const [menu, setMenu] = useState(false);

  const remove = async (id: string) => {
    if (!window.confirm("¿Borrar este hilo y su checkpoint?")) return;
    await api.deleteThread(id, userId).catch(() => undefined);
    await refreshThreads();
    if (id === threadId) navigate("/chat");
  };

  return (
    <div className={`app ${menu ? "menu-open" : ""}`}>
      <header className="topbar">
        <button className="btn icon only-mobile" onClick={() => setMenu(!menu)} aria-label="Abrir menú">
          ☰
        </button>
        <div className="brand">
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <div>
            <b>Riopaila Castilla</b>
            <span className="muted small"> · Agente conversacional · M2 Grupo 3</span>
          </div>
        </div>
        <StatusPill />
      </header>
      <aside className="sidebar" onClick={(e) => (e.target as HTMLElement).closest("a") && setMenu(false)}>
        <button className="btn primary wide" onClick={() => navigate("/chat")}>
          ＋ Nueva conversación
        </button>
        <UserSwitcher />
        <nav className="threads" aria-label="Hilos">
          <div className="section-title">Hilos de {userId}</div>
          {threads.length === 0 && <p className="muted small">Aún no hay conversaciones.</p>}
          {threads.map((t) => (
            <div key={t.thread_id} className={`thread ${t.thread_id === threadId ? "active" : ""}`}>
              <NavLink to={`/chat/${t.thread_id}`}>
                <span className="thread-title">{t.titulo || "Conversación"}</span>
                <span className="muted small">
                  {t.turnos} turno(s) · {t.thread_id.slice(0, 8)}
                </span>
              </NavLink>
              <button className="btn icon ghost" title="Borrar hilo" onClick={() => void remove(t.thread_id)}>
                ✕
              </button>
            </div>
          ))}
        </nav>
        <nav className="pages" aria-label="Secciones">
          <NavLink to="/chat">💬 Chat</NavLink>
          <NavLink to="/memoria">🧠 Memoria</NavLink>
          <NavLink to="/datos">📊 Datos (CSV)</NavLink>
          <NavLink to="/evaluacion">🎯 Evaluación RAG</NavLink>
          <NavLink to="/arquitectura">🧩 Arquitectura</NavLink>
        </nav>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

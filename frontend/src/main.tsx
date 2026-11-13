import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

// Esqueleto del frontend propio: las vistas del agente llegan en los siguientes PRs.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <main className="page">
      <h1>🌾 Riopaila Castilla · Agente conversacional</h1>
      <p className="muted">Frontend React + Vite desacoplado del backend FastAPI (Módulo 2 · Grupo 3).</p>
    </main>
  </StrictMode>,
);

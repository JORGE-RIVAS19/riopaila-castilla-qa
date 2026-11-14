# ADR-005 · Frontend React + backend FastAPI con streaming SSE

- **Estado:** aceptada · 2026-11-13
- **Contexto:** desde el M2 Streamlit y Gradio están prohibidos; la interfaz no puede llamar al modelo.
- **Decisión:** React 19 + Vite + TypeScript (`frontend/`) y FastAPI (`api/`). El turno se transmite con
  Server-Sent Events sobre `POST /api/chat/stream` (fetch + ReadableStream) con eventos tipados: decisión del
  router, inicio/fin de cada herramienta (con artefactos: fragmentos, filas, hallazgos del blindaje), tokens y final.
  Rutas de la app: `/chat/:threadId`, `/memoria`, `/datos`, `/evaluacion`, `/arquitectura`.
- **Alternativas:** WebSocket (bidireccional, innecesario aquí), Next.js (SSR innecesario para una app interna).
- **Consecuencias:** el dashboard del M1 (`app.py`) se retira; errores de red, 429/503 y cortes se muestran con
  reintento. La app es responsive (escritorio, tablet, móvil).

# ADR-006 · RAG Agent con router en vez de RAG Chain

- **Estado:** aceptada · 2026-11-13
- **Contexto:** Clase 9 — un RAG Chain recupera siempre y responde en una llamada; un RAG Agent decide cuándo y
  cuántas veces buscar, pero paga una llamada extra.
- **Decisión:** RAG Agent (`create_agent` con `buscar_documentos` como `@tool`) detrás del router: el router evita la
  llamada extra en saludos y preguntas sobre el usuario (ruta directa, una sola llamada), y el agente puede combinar
  búsqueda + CSV + comparación en las preguntas mixtas.
- **Orquestadores considerados:** LangChain/LangGraph (elegido: checkpointer, Store, middleware y LangSmith
  nativos), LlamaIndex (fuerte en ingesta, más débil en memoria por hilo), Agno (rápido, menos control del grafo),
  DSPy (optimiza prompts, no orquesta estado). Deep Agents no se usa: no hay tareas largas multi-paso.
- **LLM Wiki / OKF:** nuestro corpus Gold ya es markdown con frontmatter (a un paso de OKF); compilar un wiki en la
  ingesta queda como trabajo futuro para preguntas de síntesis entre muchos documentos.

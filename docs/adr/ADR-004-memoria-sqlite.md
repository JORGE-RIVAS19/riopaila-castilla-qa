# ADR-004 · Memoria persistente con SqliteSaver y SqliteStore

- **Estado:** aceptada · 2026-11-13
- **Contexto:** la memoria en RAM no se acepta como persistencia; el hilo debe sobrevivir al reinicio y el perfil
  debe recuperarse en un hilo nuevo.
- **Decisión:** `SqliteSaver` (`data/memory/checkpoints.sqlite`) para el corto plazo por `thread_id`;
  `SqliteStore` (`data/memory/store.sqlite`) para el largo plazo con namespaces
  `("usuarios", id, "perfil")` y `("usuarios", id, "hilos")`. El perfil entra al prompt con `@dynamic_prompt`
  usando `store.search()`. `SummarizationMiddleware` (6 000 tokens → resumen + 8 mensajes) evita desbordar la
  ventana en el agente; la ruta directa usa `trim_messages` (2 000 tokens).
- **Alternativas:** PostgresSaver/PostgresStore (producción multiusuario; requiere servidor), InMemory (prohibido).
- **Consecuencias:** cero servidores; el *time travel* (`get_state_history`, bifurcar desde un checkpoint) queda
  disponible en la API y en la app.

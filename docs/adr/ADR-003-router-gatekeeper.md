# ADR-003 · Router híbrido tipo gatekeeper (reglas → LLM)

- **Estado:** aceptada · 2026-11-13
- **Contexto:** el criterio 2.3 penaliza al agente que busca siempre. Un LLM decidiendo cada turno suma 2–5 s y
  costo; un RAG Chain busca incluso ante «hola».
- **Decisión:** nodo `router` antes del agente, inspirado en System One/Jev (Clase 9):
  1. **Noul por reglas** (≈0,1 ms): saludo/trivial, dato propio, pregunta sobre el usuario.
  2. **Choice por reglas**: puntúa señales numéricas (CSV) y documentales (RAG) y comparativas (mixto).
  3. **Choice con LLM** solo si la confianza < 0,7 (`ROUTER_MODE=hibrido`), con salida estructurada Pydantic.
  4. Confianza < 0,5 → `rag` en **modo cautela** (solo evidencia o abstención).
  La ruta decide qué herramientas existen en el turno (`wrap_model_call` filtra `request.tools`).
- **Alternativas:** Jev real (no disponible en la cuenta del grupo), router 100 % LLM (más lento y caro),
  `LLMToolSelectorMiddleware` (decide tarde, después de pagar la llamada).
- **Consecuencias:** los saludos y las preguntas sobre el perfil no tocan Qdrant; la decisión es visible en la app
  (badge, confianza, señales) y en la traza. Las reglas se prueban en `tests/test_agent.py`.

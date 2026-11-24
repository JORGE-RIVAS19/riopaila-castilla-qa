# ADR-007 · OpenClaw como puerta, LangGraph como cerebro, MCP propio como puente

- **Estado:** aceptada · 2026-11-23
- **Contexto:** el Módulo 3 exige OpenClaw (gateway, canales, workspace, skills/MCP, sandbox) con WhatsApp en
  producción y, a la vez, 20 herramientas `@tool` + Pydantic trazables en el arnés. Todo el conocimiento (router,
  memoria por hilo, RAG, verificador de cifras, HITL) ya vive en el agente LangGraph del M2.
- **Decisión:** OpenClaw atiende el canal (sesión vinculada, allowlist E.164, notas de voz, fotos, cron, workspace) con
  DeepSeek como modelo del gateway, contesta lo trivial y delega lo del taller a nuestro **servidor MCP propio**
  `taller-riopaila` (stdio), que llama a `POST /api/chat` del FastAPI. Cada número tiene su hilo `wa-<número>` en el
  checkpointer. Los adjuntos vuelven como rutas del workspace y OpenClaw los envía con líneas `MEDIA:`.
- **Alternativas:** (a) exponer las 21 herramientas sueltas por MCP y que OpenClaw haga el ReAct: se perdían router,
  memoria por hilo, verificador e HITL de LangGraph; (b) plugin TypeScript con *agent harness*: más acoplado a la
  versión de OpenClaw y más difícil de probar con pytest; (c) puente directo por la API de WhatsApp Cloud: el número de
  prueba de Meta no cumple los lineamientos.
- **Consecuencias:** dos niveles de decisión (puerta y router interno) visibles en logs y trazas; el MCP es pequeño,
  tipado y probado (`tests/test_mcp_taller.py`); la herramienta de escritura se autoriza por remitente en
  `tools.toolsBySender` y el API vuelve a validar el rol (defensa en profundidad).

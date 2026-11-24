# ADR-010 · Seguridad: roles del servidor, HITL con interrupt y OpenClaw endurecido

- **Estado:** aceptada · 2026-11-23
- **Contexto:** el bot lo prueban invitados desde sus teléfonos; los datos de SAP son internos; la única acción que
  escribe es registrar una novedad.
- **Decisión:** (1) WhatsApp con `dmPolicy: allowlist`; (2) gateway `bind: loopback` + token; `tools.profile:
  messaging`, `deny` de runtime/fs/automation/browser, `fs.workspaceOnly`, `exec` denegado, sandbox Docker `mode: all`;
  (3) `toolsBySender` deja la herramienta MCP de escritura solo a los números del taller; (4) en el API el **rol lo
  decide el servidor** (`TALLER_ROLES`) y el canal de solo lectura fuerza `invitado`; (5) `registrar_novedad` hace
  `interrupt()` con la pregunta de confirmación y solo escribe ante un SÍ; cualquier otra respuesta cancela.
- **Alternativas:** `HumanInTheLoopMiddleware` (aprueba llamadas de herramienta, pero la confirmación debía mostrar el
  equipo resuelto en SAP); confiar en el número que escribe el modelo (inyectable).
- **Consecuencias:** un invitado no puede escribir aunque engañe al modelo; el HITL sobrevive a reinicios porque la
  pausa queda en el checkpointer; `openclaw security audit` forma parte de la verificación diaria.

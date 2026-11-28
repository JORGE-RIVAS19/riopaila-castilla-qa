# ADR-012 · WhatsApp abierto a cualquier invitado y remitentes con número oculto (LID)

- **Estado:** aceptada · 2026-11-27 · ajusta [ADR-010](ADR-010-seguridad-hitl-roles.md) y complementa
  [ADR-011](ADR-011-perfiles-por-numero.md)
- **Contexto:** en la clase del 27-nov el docente pidió que el bot **le funcione a cualquier persona** que le escriba
  el día de la sustentación (invitados de las empresas que no conocemos de antemano). Con `dmPolicy: pairing` un número
  nuevo debía esperar la aprobación de un código. Además, en la prueba en vivo apareció un segundo problema: cuando
  WhatsApp no le entrega al bot el número del remitente (usuarios con nombre de usuario o primer contacto sin chat
  previo), el plugin `@openclaw/whatsapp` lanza `WhatsApp inbound LID identity unavailable` y **descarta el mensaje
  antes de evaluar la política**; con `open` pasaba lo mismo. Revisamos el código de las versiones 2026.11.2,
  2026.11.10 y 2026.12.1-beta.1 del plugin: ninguna trae una opción para estos remitentes.
- **Decisión:** (1) `dmPolicy: "open"` con `allowFrom: ["*", …]`: cualquiera recibe respuesta sin código. (2) La lista
  E.164 sigue gobernando lo sensible: `toolsBySender` (solo los números del taller ven la herramienta MCP de escritura;
  `"*"` la niega) y `TALLER_ROLES` en el API (solo el personal ve SAP real). (3) Ajuste de una línea en el plugin
  (`deploy/scripts/05_parche_lid.sh`): si no hay número, se usa el identificador LID como identidad; el bot responde a
  ese mismo chat y el remitente entra como **visitante** (vitrina pública + muestra anonimizada, sin escritura). El
  script es idempotente, guarda el original (`.orig`), valida la sintaxis con `node --check`, se revierte con
  `--revertir` y lo aplica `03_configurar_openclaw.sh` en una instalación nueva.
- **Alternativas:** WhatsApp Cloud API de Meta (entrega siempre un identificador del usuario, pero exige verificación
  del negocio, token permanente, número registrado y URL pública HTTPS: no cabía antes del sábado; el webhook
  `/api/webhook/whatsapp` queda listo como contingencia); mantener `pairing` (no cumple la instrucción del docente);
  saludar primero desde el bot a cada número (no sirve para invitados desconocidos ni para números ocultos).
- **Consecuencias:** el bot responde a cualquiera y un desconocido nunca ve datos reales ni escribe. El personal del
  taller debe haber recibido al menos un mensaje del bot (`openclaw message send …`) para que WhatsApp le entregue su
  número y el servidor lo reconozca; si no, entra como visitante. El ajuste toca código de terceros: hay que volver a
  aplicarlo tras actualizar el plugin (el script avisa si la línea cambió). `openclaw security audit` reporta la
  política abierta; es un riesgo aceptado y mitigado por perfiles, `toolsBySender`, HITL y sandbox.
- **Evidencia:** log del 27-nov, 21:01 (hora Colombia): `Inbound message 37976268636274@lid -> +573136538437` seguido
  de `Sent message … (313ms)`.

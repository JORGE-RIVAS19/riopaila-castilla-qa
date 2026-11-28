---
name: taller-castilla
description: Consultas del Taller Castilla (SAP, repuestos, manuales con foto, fusibles, alertas) y registro de fallas por el MCP taller-riopaila.
---
# Taller Castilla

Usa este skill para cualquier pregunta de mantenimiento de la flota de Riopaila Castilla.

1. Consulta → `taller-riopaila__consultar_asistente_taller(mensaje, telefono, adjuntos?)`.
2. Falla de un equipo → `taller-riopaila__gestionar_novedad_taller(mensaje, telefono)` y, tras la pregunta de
   confirmación, la respuesta SÍ/NO del usuario con la misma herramienta.
3. Parte del día → `taller-riopaila__parte_diario_taller(dias=7)`.

Entrega: copia `respuesta` y agrega una línea `MEDIA:<ruta>` por cada ruta de `adjuntos`.

Ejemplos que lucen bien en la demo:
- "¿Qué fusible es el del radio en la mula?" → foto de la caja de fusibles con el fusible resaltado.
- "¿Cómo cambio el filtro hidráulico del Puma 165?" → pasos + foto de la página del manual.
- "¿Qué le toca cambiar pronto al 25375?" → kit sugerido con fechas y costo estimado.
- "¿Hay consumos raros esta semana?" → alertas explicadas (cuántas veces por encima de lo normal).
- "Mándame el informe PDF de las cosechadoras" → PDF adjunto.

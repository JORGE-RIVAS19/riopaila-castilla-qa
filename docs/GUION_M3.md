# Guion de la sustentación final · Grupo 3 · sábado 28-nov · 8:45 a. m.

**Formato:** 7 min de pitch con demo en vivo por WhatsApp (sin diapositivas) + 8 min de discusión técnica y preguntas.
**Antes de entrar (8:30):** `bash deploy/scripts/verificar.sh` en verde, celular del bot cargado, dos teléfonos de
invitados con el número guardado, el repo en una pestaña y `openclaw logs --follow` en otra.

## Pitch (7 min)

| Min | Quién | Qué se dice / se hace |
|---|---|---|
| 0:00–1:00 | Jorge | **El problema.** “Soy supervisor de mantenimiento en Planta Castilla. Tenemos 42 tractores de cosecha, cosechadoras, alzadoras y 12 mulas. Para cambiar un filtro o encontrar un fusible, el técnico busca en 22 manuales de cientos de páginas, en inglés o portugués, y para pedir un repuesto hay que encontrar su código entre 26.000 materiales de SAP.” |
| 1:00–1:30 | Jorge | **La propuesta.** “Un compañero de taller en WhatsApp que contesta con la página del manual, el dato de SAP y la gráfica; y que avisa solo cuando algo se sale de lo normal.” |
| 1:30–5:30 | Melissa (narra) · invitado (escribe) | **Demo en el teléfono del invitado** (ver lista abajo). |
| 5:30–6:30 | Waldor | **Impacto.** Minutos por consulta en lugar de horas; alertas tempranas de consumo; menos códigos duplicados; trazabilidad de las novedades; corre con un costo de API de centavos por día. |
| 6:30–7:00 | Jorge | **Cierre.** “Lo construimos sobre todo lo del curso: el corpus del M1, el agente con memoria y RAG del M2 y OpenClaw con 21 herramientas en el M3. Mañana mismo lo puede usar el taller.” |

**Demo (en este orden; si algo tarda, se narra mientras llega):**
1. Invitado: “Hola, ¿qué puedes hacer?” → responde la puerta sin herramientas (router).
2. Invitado: “¿Qué fusible es el del radio en la mula?” → foto de la caja con el fusible resaltado.
3. Jorge, nota de voz: “¿Cómo cambio el filtro hidráulico del Puma 165?” → pasos + página del manual.
4. Invitado: “¿Hay consumos raros este mes?” → alertas explicadas (“12× lo normal”).
5. Invitado: “Hazme la gráfica de gasto de las cosechadoras” → gráfica.
6. Jorge: “El 25375 está botando aceite por la bomba, regístralo” → SÍ/NO → “Sí” → novedad #N.
7. Invitado intenta lo mismo → “solo el personal del taller puede registrar novedades”.

## Discusión técnica (8 min) · quién defiende qué

| Tema | Responsable | Qué mostrar |
|---|---|---|
| Arquitectura y OpenClaw (gateway, `openclaw.json`, workspace, MCP propio, sandbox) | Jorge | `deploy/openclaw/openclaw.json5`, `openclaw security audit`, `docs/arquitectura` (Archify) |
| 21 herramientas, router y HITL | Waldor | `src/riopaila_qa/taller/tools.py`, `TOOLS_BY_ROUTE`, traza en LangSmith, `interrupt` |
| Datos, RAG, memoria y evaluación | Melissa | DuckDB + muestra anonimizada, manuales por página, nDCG@10 y UMAP, checkpointer por número |

## Preguntas probables (respuesta corta)

- **¿Por qué no Ollama?** El motor es DeepSeek por API (Gemini de respaldo); Ollama solo vectoriza (embeddings), que el anuncio permite.
- **¿Por qué dos LLM (puerta y agente)?** La puerta decide si hace falta el taller (saludos sin gasto) y maneja voz/fotos; el agente tiene router, memoria por hilo, verificador de cifras y HITL. Dos niveles de decisión, ambos trazables (ADR-007).
- **¿Cómo evitan que un invitado registre fallas?** Tres capas: `toolsBySender` en OpenClaw, el rol lo decide el servidor (`TALLER_ROLES`) y la confirmación SÍ/NO con `interrupt` (ADR-010).
- **¿Y si el LLM inventa una cifra?** No calcula: las cifras salen de SQL; el verificador de cifras descarta respuestas con números sin respaldo.
- **¿Qué pasa si un manual trae una instrucción maliciosa?** Datos pasivos en XML + detector de inyección + red lines en AGENTS.md.
- **¿Datos reales en GitHub?** No: SAP y manuales solo en el servidor; el repo tiene una muestra anonimizada.
- **¿Cómo saben que la búsqueda funciona?** 25 consultas etiquetadas: nDCG@10 0,58 / MRR 0,72 léxico; UMAP muestra que el espacio léxico agrupa por idioma, por eso el glosario y los embeddings multilingües.
- **¿Si se cae?** systemd reinicia API y gateway; la memoria está en disco; Gemini de respaldo; segundo celular vinculado.

---

## English version of the pitch (optional bonus)

**0:00 Problem.** “I’m the maintenance supervisor at Riopaila Castilla’s Castilla plant. We run 42 harvest tractors, cane
harvesters, loaders and 12 trucks. To change a filter or find a fuse, a technician digs through 22 manuals — thousands of
pages in English and Portuguese — and to order a part he must find its code among 26,000 SAP materials.”
**1:00 Proposal.** “A workshop buddy on WhatsApp that answers with the manual page, the SAP figure and the chart, and
warns us when consumption looks abnormal.”
**1:30 Live demo** (same seven steps). **5:30 Impact.** “Minutes instead of hours per question, early warnings, fewer
duplicated part codes, traceable field reports, at a few cents of API cost per day.” **6:30 Close.** “It is built on
everything in the course: the M1 corpus, the M2 agent with memory and RAG, and OpenClaw with 21 tools in M3. The
workshop can start using it on Monday.”

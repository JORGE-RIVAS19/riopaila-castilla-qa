# Guion de la sustentación final · Grupo 3 · sábado 28-nov · 8:45 a. m.

**Formato:** 7 min de pitch con demo en vivo por WhatsApp (sin diapositivas) + 8 min de discusión técnica y preguntas.
**Antes del sábado:** el bot le escribe una vez a cada número del taller (`openclaw message send …`) para que el servidor
lo reconozca; los invitados no necesitan nada: cualquiera que escriba recibe respuesta (ADR-012). **Antes de entrar (8:30):** `bash deploy/scripts/verificar.sh` en verde, celular del bot cargado, dos teléfonos de
invitados ya saludados **desde el celular del bot** (WhatsApp oculta el número de quien escribe por primera vez; si el bot escribe primero, el servidor lo reconoce), el repo en una pestaña y `openclaw logs --follow` en otra.

## Pitch (7 min)

| Min | Quién | Qué se dice / se hace |
|---|---|---|
| 0:00–1:00 | Jorge | **El problema.** “Soy supervisor de mantenimiento en Planta Castilla. Tenemos 42 tractores de cosecha, cosechadoras, alzadoras y 12 mulas. Para cambiar un filtro o encontrar un fusible, el técnico busca en 22 manuales de cientos de páginas, en inglés o portugués, y para pedir un repuesto hay que encontrar su código entre 26.000 materiales de SAP.” |
| 1:00–1:30 | Jorge | **La propuesta.** “Un compañero en WhatsApp con dos caras: para el visitante es la **vitrina de Riopaila Castilla** (cifras y documentos públicos del M1/M2, siempre con su fuente); para el taller, el que contesta con la página del manual, el dato de SAP y la gráfica, y avisa cuando algo se sale de lo normal.” |
| 1:30–5:30 | Melissa (narra) · invitado (escribe) · Jorge | **Demo en el teléfono del invitado** (ver lista abajo). |
| 5:30–6:30 | Waldor | **Impacto.** Minutos por consulta en lugar de horas; alertas tempranas de consumo; menos códigos duplicados (ya detectó una etiqueta que no coincide con el maestro); trazabilidad de las novedades; y los datos internos nunca salen de la empresa: el visitante ve una muestra anonimizada. Costo de API: centavos por día. |
| 6:30–7:00 | Jorge | **Cierre.** “Lo construimos sobre todo lo del curso: el corpus del M1, el agente con memoria y RAG del M2 y OpenClaw con 23 herramientas en el M3. Mañana mismo lo puede usar el taller.” |

**Demo (en este orden; si algo tarda, se narra mientras llega):**
1. Invitado: “Hola” → **menú de visitante** de la puerta, sin herramientas (router: no gasta búsquedas en saludos).
2. Invitado: “1” (*Riopaila en cifras*) → **infografía** con ingresos, utilidades, mercado, países, empleo e inversión
   social, cada cifra con su año y su fuente (M1/M2 vivos).
3. Invitado: “¿Hay consumos raros este mes?” → alertas explicadas (“12× lo normal”) **sobre datos de muestra**: el bot
   lo dice. *Melissa:* “el visitante prueba todo, pero nunca ve un dato real de SAP”.
4. Jorge, 📷 foto de las etiquetas de repuestos → códigos SAP **reales**, precio, último uso y la alerta de que
   “dispositivo de arado” no coincide con el maestro.
5. Jorge, 🎙️ nota de voz: “¿Cómo cambio el filtro hidráulico del Puma 165?” → pasos + página del manual resaltada.
6. Jorge: “El 25375 está botando aceite por la bomba, regístralo” → SÍ/NO → “Sí” → novedad #N.
7. Invitado intenta lo mismo → “solo el personal del taller puede registrar novedades”.

## Discusión técnica (8 min) · quién defiende qué

| Tema | Responsable | Qué mostrar |
|---|---|---|
| Arquitectura y OpenClaw (gateway, `openclaw.json`, workspace, MCP propio, sandbox) | Jorge | `deploy/openclaw/openclaw.json5`, `openclaw security audit`, `docs/arquitectura` (Archify) |
| 23 herramientas, perfiles, router y HITL | Waldor | `src/riopaila_qa/taller/tools.py`, `TOOLS_BY_ROUTE`, traza en LangSmith, `interrupt` |
| Datos, RAG, memoria, perfiles y evaluación | Melissa | vitrina M1/M2 (infografía desde el CSV con fuente), DuckDB real vs. muestra por perfil (ADR-011), manuales por página, nDCG@10 y UMAP, checkpointer por número |
| QA y despliegue | Jorge | `tests/e2e` con Playwright (capturas en teléfono y escritorio), `deploy/scripts/04_actualizar.sh`, `openclaw logs` |

## Preguntas probables (respuesta corta)

- **¿Por qué no Ollama?** El motor es DeepSeek por API (Gemini de respaldo); Ollama solo vectoriza (embeddings), que el anuncio permite.
- **¿Por qué dos LLM (puerta y agente)?** La puerta decide si hace falta el taller (saludos sin gasto) y maneja voz/fotos; el agente tiene router, memoria por hilo, verificador de cifras y HITL. Dos niveles de decisión, ambos trazables (ADR-007).
- **¿Cómo evitan que un invitado registre fallas?** Tres capas: `toolsBySender` en OpenClaw, el rol lo decide el servidor (`TALLER_ROLES`) y la confirmación SÍ/NO con `interrupt` (ADR-010).
- **¿Y si el LLM inventa una cifra?** No calcula: las cifras salen de SQL; el verificador de cifras descarta respuestas con números sin respaldo.
- **¿Qué pasa si un manual trae una instrucción maliciosa?** Datos pasivos en XML + detector de inyección + red lines en AGENTS.md.
- **¿Datos reales en GitHub?** No: SAP y manuales solo en el servidor; el repo tiene una muestra anonimizada.
- **¿Cómo saben que la búsqueda funciona?** 25 consultas etiquetadas: nDCG@10 0,58 / MRR 0,72 léxico; UMAP muestra que el espacio léxico agrupa por idioma, por eso el glosario y los embeddings multilingües.
- **¿Le funciona a cualquiera?** Sí: la consulta está abierta (`dmPolicy: open`). La lista E.164 decide lo sensible
  (escribir, ver SAP real). Encontramos que el plugin descartaba en silencio a quien llega con el número oculto (LID) y lo
  ajustamos con un script versionado y reversible: entra como visitante (ADR-012).
- **¿Qué ve un invitado de otra empresa?** La vitrina pública de Riopaila y el taller sobre una **muestra
  anonimizada**; el perfil lo decide el servidor por el número, no el modelo (ADR-011). Un rol desconocido cae en la
  muestra: se falla hacia lo seguro.
- **¿Por qué WhatsApp Web de OpenClaw y no la Cloud API de Meta?** El anuncio 008 acepta ambos; con OpenClaw no hay
  lista de 5 ni token que caduque. El webhook de Cloud API (`/api/webhook/whatsapp`) quedó listo como contingencia y
  probado con un POST simulado.
- **¿Por qué Google Cloud y un script, si en clase se hizo a mano?** Son los mismos comandos de OpenClaw
  (`gateway install`, `channels login`, `openclaw.json`), versionados en `deploy/scripts`: así el despliegue se
  reproduce y la configuración queda en el repositorio (3.1).
- **¿Cómo hicieron QA?** Playwright en `tests/e2e`: API, webhook, flujo del pitch y la web en teléfono y escritorio,
  contra la app desplegada. Encontró un 404 real (la evaluación del M2 no se había generado) y se corrigió.
- **¿Si se cae?** systemd reinicia API y gateway; la memoria está en disco; Gemini de respaldo; segundo celular vinculado.

---

## English version of the pitch (optional bonus)

**0:00 Problem.** “I’m the maintenance supervisor at Riopaila Castilla’s Castilla plant. We run 42 harvest tractors, cane
harvesters, loaders and 12 trucks. To change a filter or find a fuse, a technician digs through 22 manuals — thousands of
pages in English and Portuguese — and to order a part he must find its code among 26,000 SAP materials.”
**1:00 Proposal.** “A WhatsApp buddy with two faces: for visitors, a showcase of Riopaila Castilla’s public figures,
always with their source; for the workshop, the manual page, the SAP figure and the chart, plus early warnings.
Visitors try everything on anonymized sample data; real SAP data never leaves the company.”
**1:30 Live demo** (same seven steps). **5:30 Impact.** “Minutes instead of hours per question, early warnings, fewer
duplicated part codes, traceable field reports, at a few cents of API cost per day.” **6:30 Close.** “It is built on
everything in the course: the M1 corpus, the M2 agent with memory and RAG, and OpenClaw with 23 tools in M3. The
workshop can start using it on Monday.”

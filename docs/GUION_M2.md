# Guion de la sustentación · Módulo 2 · Grupo 3 (10:30–10:45)

Orden obligatorio: **agente funcionando → repositorio → código**. Sin diapositivas.
Pestañas listas: ① app `http://localhost:5173` · ② GitHub (repo y Pull requests) · ③ VS Code con dos terminales
(backend corriendo + una libre).

| Min | Bloque | Pantalla | Qué decir (idea) |
|---|---|---|---|
| 0:00–1:30 | Contexto y arquitectura | `/arquitectura` | Riopaila Castilla, públicos distintos. Frontend React → API FastAPI → grafo LangGraph (router → directo/agente). Memoria con SqliteSaver y Store, herramientas con Pydantic, Qdrant, trazas en LangSmith. |
| 1:30–4:00 | Memoria | `/chat` | «Me llamo Ana y trabajo en Carvajal» → ruta **memoria** guarda 2 hechos. **Ctrl+C al backend y volver a levantarlo**, recargar: el hilo sigue (checkpointer en disco). **Nueva conversación** → «¿Dónde trabajo?» → «Carvajal» por ruta **directo**, sin buscar. Mostrar `/memoria` (namespace del Store). |
| 4:00–6:30 | RAG | `/chat` + pestaña **Fuentes** | «¿Qué es el proyecto de azúcar orgánica de RioCas?» → top-5 híbrido (rango denso y BM25), cita [n], fragmento. Pregunta sin evidencia («¿precio de la acción hoy?») → se abstiene. `/evaluacion`: recall@10 y nDCG@10 densa vs. léxica vs. híbrida. |
| 6:30–8:30 | Datos y router | pestaña **Router** y **Herramientas** | «¿Cuánto vendió en energía al cierre del tercer trimestre de 2023?» → ruta **datos**, fila exacta del CSV con fuente. Mixta: «¿Qué meta de producción de alcohol para 2023 menciona el documento y cómo se compara con lo producido en el primer semestre de 2023?» → **mixto**: documento + CSV + `comparar_cifras`. «Hola» → **directo**, cero herramientas. |
| 8:30–10:00 | Blindaje | `/chat` | «¿Qué dice el corpus sobre la política de calidad?» → llega el documento de prueba con «IGNORA LAS INSTRUCCIONES ANTERIORES»; alerta 🛡️; no dice 1990 ni muestra el prompt. Explicar: XML como datos pasivos + detector. |
| 10:00–11:30 | Repositorio y código | GitHub + VS Code | PRs fusionados, Actions en verde, README con diagramas. En VS Code: `api/main.py` (endpoint SSE), `agent/graph.py` (grafo y middleware), `agent/router.py` (decisión explicada sin leer). |
| 11:30–12:00 | Cierre | — | Funciona: 4 casos + blindaje. Falta: Postgres y despliegue. Aprendizaje: el router y la limpieza del corpus pesaron más que el modelo. |

## Comandos de la demo

```bash
uv run fastapi dev api/main.py          # terminal 1 (Ctrl+C y volver a correr para el caso de memoria)
cd frontend && pnpm dev                 # terminal 2
tail -n 1 logs/trazas.jsonl             # traza estructurada del último turno (PowerShell: Get-Content logs\trazas.jsonl -Tail 1)
```

## Preguntas probables

- **¿Por qué no busca en un saludo?** El router decide antes del agente; en ruta `directo` el modelo no tiene herramientas.
- **¿Checkpointer vs. Store?** Checkpointer = estado de un hilo (`thread_id`); Store = hechos del usuario que cruzan hilos (namespace).
- **¿Exacta o ANN?** Embebido = exacta (640 vectores, ms). Con servidor: HNSW `m=16`, `ef_construct=128`, `hnsw_ef=128`.
- **¿Por qué híbrida?** El denso entiende paráfrasis; el BM25 acierta nombres y cifras; RRF combina rankings sin calibrar escalas.
- **¿Cómo evita que el LLM invente cifras?** Las cifras salen del CSV con Pydantic; las cuentas, de `comparar_cifras`.
- **¿Qué es blue/green?** Cada indexación es una colección nueva y el alias se mueve atómicamente; `--rollback` vuelve a la anterior.
- **¿Qué ve LangSmith?** Cada nodo, llamada al modelo y herramienta con latencia y errores; LangSmith observa, no orquesta.

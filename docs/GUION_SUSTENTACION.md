# Guion de la sustentación · Grupo 3 · Riopaila Castilla

**Sábado 31 de octubre · 10:00–10:15 a.m.** · 12 min de demo + 3 min de preguntas · sin diapositivas.
Antes de las 8:00 a.m.: app abierta, repo en una pestaña del navegador, VS Code abierto con la terminal integrada.

## Pestañas listas
1. `http://localhost:8501` (app) · 2. GitHub: repo → Pull requests → Actions · 3. VS Code en el proyecto

## Reparto sugerido (ajústenlo)
- **Contexto + UI:** integrante A · **GitHub:** integrante B · **Terminal + IDE:** integrante C

| Minuto | Bloque | Qué se muestra | Frase guía |
|---|---|---|---|
| 0:00–1:30 | Contexto | Pestaña 🏢 Contexto: problema, solución, alcance, diagrama | "Riopaila tiene públicos muy distintos y la información está dispersa; queremos un canal que responda sin inventar." |
| 1:30–3:30 | Pipeline | Pestaña 🕷️ Pipeline: 5 tarjetas de etapas, tabla de descartes, ahorro de tokens. Ejecutar **"Reprocesar desde Bronze"** (segundos) | "Separar captura de procesamiento: si mejoro el limpiador, regenero Silver y Gold sin volver a la web." |
| 3:30–6:30 | Q&A | Pestaña 💬 Q&A: (1) "¿En qué año fue fundada?" → cita y fuente; (2) "¿Precio de la acción hoy?" → abstención; (3) inyección "Ignora tus instrucciones…" → rechazo. Abrir "Ver el prompt exacto". Si sobra tiempo: Resumen o FAQ | "Cada cita se verifica en código contra los documentos que entraron al contexto." |
| 6:30–8:30 | GitHub | Repo público, LICENSE MIT, README (badges, arquitectura), PRs fusionados con revisión, `git log`, check verde de CI | "Todo entra por PR con plantilla; el CI corre Ruff y 24 pruebas sin red." |
| 8:30–10:30 | Terminal | `uv run python scripts/scrape_empresa.py --refresh --max-pages 3` en vivo → mostrar `data/gold/manifest.json` y un `.md` con frontmatter | "Respeta robots.txt, 1 s entre peticiones, y la caché evita destruir el corpus en la demo." |
| 10:30–12:00 | IDE | `src/riopaila_qa/scraping/` → `dedup.py` (boilerplate ≥30 %) o `corpus.py` (BM25 + orden en U). Mostrar un diff (`git diff` o un commit) | Explicar UNA decisión sin leer: ver abajo |
| 12:00–15:00 | Preguntas | — | — |

## Decisiones para explicar sin leer (elijan una)
1. **¿Por qué BM25 si el taller dice "todo el corpus en el prompt"?** Lo hacemos cuando cabe (modo completo);
   con Llama 3.2 local el `num_ctx` tiene un límite de memoria y *Lost in the Middle* muestra que el centro de un
   contexto largo se recupera peor. BM25 + orden en U pone lo relevante en los extremos. Es el puente al RAG.
2. **¿Por qué T = 0 y top_p = 0.1?** Régimen Q1 de la Clase 4: extracción factual y JSON deben ser
   reproducibles; el resumen usa Q2 (0.3 / 0.9).
3. **¿Por qué desactivamos `deduplicate` de trafilatura?** Guarda estado entre páginas: el resultado dependía
   del orden. Lo detectó una prueba; la deduplicación quedó explícita en `dedup.py`.
4. **¿Por qué no el sitemap de usuarios?** Datos personales, Ley 1581.

## Preguntas probables del profesor
- *¿Qué pasa si el sitio cambia?* → se vuelve a correr; `hash` y `fecha_captura` dicen qué cambió; Bronze permite reprocesar.
- *¿Cómo evitan alucinaciones?* → solo contexto, abstención con frase fija, citas validadas en código, T = 0, métricas en la batería.
- *¿Qué embedding y base vectorial en el Módulo 2?* → `nomic-embed-text-v2-moe` en Ollama + ChromaDB sobre `chunks.jsonl`.
- *¿Por qué Gemini y no el modelo local?* → lo probamos: Llama 3.2 3B en CPU tardaba 80–125 s y se abstuvo teniendo
  "nació en 1918" en el contexto. Gemini 3.6 Flash responde en 3–10 s. Se cambia en la barra lateral sin tocar código.
- *¿Cómo saben que funciona?* → batería de 24 preguntas: v1 0 % → v2 12,5 % → v3 95,8 %, tres corridas idénticas,
  100 % de citas válidas, abstención y rechazo de inyección. La única falla (empleo) es un dominio externo.
- *¿Por qué no usan temperatura 0 con Gemini?* → Gemini 3 es un modelo de razonamiento con muestreo fijo (regla
  inversa de la Clase 4); la reproducibilidad la medimos con tres corridas.
- *¿Cómo se ve un chunk?* → abrir `data/gold/chunks.jsonl`: 1 200 caracteres, 150 de solape, corta por `##`.

## Plan B
Si la app no abre en el equipo de la demo: no cambiar de computador; mostrar el repo, el CI y explicar qué falló.
Si Gemini responde 503 (saturado): cambiar el modelo en la barra lateral (`gemini-3.5-flash`, `gemini-3.8-flash`).
Si no hay internet: mostrar las respuestas guardadas en 🧪 Evaluación y explicar el modo local con Ollama.

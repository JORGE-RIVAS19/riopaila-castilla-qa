# ADR-001 · Modelo local por defecto y contexto con presupuesto

- **Estado:** aceptada · 2026-10-30
- **Contexto:** el taller permite Ollama (Llama 3.2, Mistral) o API privada. El corpus es información
  pública, pero el asistente del semestre manejará datos de una empresa real; el equipo no tiene GPU dedicada.
- **Decisión:** Llama 3.2 3B en Ollama por defecto (`num_ctx` 16k, presupuesto de contexto 12k tokens),
  con Gemini u OpenAI intercambiables por `.env`. Muestreo Q1 (T=0, top_p=0.1) para Q&A y FAQ.
  Si el corpus no cabe, preselección BM25 (ver `openspec/changes/archive/2026-10-30-contexto-bm25`).
- **Consecuencias:** costo cero y datos locales; el modelo pequeño es más lento con prompts largos y
  sigue peor el formato que un modelo de frontera, por eso validamos citas y esquema en código.
  En el Módulo 2 el BM25 se reemplaza (o se combina) con embeddings `nomic-embed-text-v2-moe` + ChromaDB.
- **Registro en Engram:** `mem_save` con título "ADR-001 modelo y contexto" (ver docs/USO_DE_IA.md).

## Actualización · 2026-10-30 (tras la prueba con el corpus real)
- Llama 3.2 3B en CPU tardó 80–125 s por respuesta y no siguió las reglas del prompt (se abstuvo teniendo la
  respuesta en el contexto). La demo y la evaluación pasan a **Gemini 3.6 Flash** por API (3–10 s).
- `num_ctx` de Ollama se ajusta al prompt real y no al presupuesto máximo (antes reservaba 134k tokens).
- Las páginas *Somos Riopaila Castilla* y *Contáctenos* siempre entran al contexto; BM25 usa stemming por
  truncamiento y pondera menos las noticias.
- El plan gratuito de Gemini permite 20 solicitudes por día por modelo: se usa un proyecto con facturación y la
  evaluación reintenta ante 503.

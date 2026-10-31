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

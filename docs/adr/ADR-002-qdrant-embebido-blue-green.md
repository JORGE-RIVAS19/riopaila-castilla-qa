# ADR-002 · Qdrant embebido, payload y alias blue/green

- **Estado:** aceptada · 2026-11-13
- **Contexto:** el M2 exige Qdrant con colecciones, payload y filtros, y saber explicar búsqueda exacta vs. ANN.
  El corpus son ~640 chunks; la demo corre en el portátil de un integrante, sin garantía de Docker.
- **Decisión:** `QdrantClient(path="data/qdrant")` (modo embebido, persistente en disco) por defecto, y
  `QDRANT_URL` para el servidor Docker. Cada indexación crea `riopaila_chunks_<modelo>_<fecha>` y mueve el alias
  `riopaila_chunks` de forma atómica (blue/green); se conservan dos colecciones para `--rollback`.
  Payload: `chunk_id, doc_id, url, titulo, seccion, tipo, anio, origen, texto`. Filtros por sección, tipo, año y
  origen (para excluir el documento sintético en la evaluación).
- **Exacto vs. ANN:** en modo embebido la búsqueda es exacta (fuerza bruta): con 640 vectores tarda pocos ms y da
  recall 100 % frente a sí misma. En servidor la colección se crea con HNSW (`m=16`, `ef_construct=128`) y se
  consulta con `hnsw_ef=128`; `exact=True` permite medir cuánto recall pierde el ANN. IVF y PQ tendrían sentido con
  millones de vectores, no aquí.
- **Consecuencias:** cero infraestructura para la demo y el CI; el modo embebido bloquea la carpeta (un proceso a la
  vez): se indexa con el backend detenido.

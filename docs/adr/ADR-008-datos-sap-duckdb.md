# ADR-008 · Datos de SAP en DuckDB de solo lectura y muestra anonimizada en el repo

- **Estado:** aceptada · 2026-11-23
- **Contexto:** 3 exportes de SAP (equipos, materiales y 235.498 movimientos 261/262/101/102 desde 2023). Las preguntas
  del taller son agregaciones (gasto por equipo, ranking, series, intervalos): un RAG sobre filas sería impreciso y el
  LLM no debe sumar.
- **Decisión:** construir una base **DuckDB** (`scripts/build_taller.py`, ≈20 s) con la vista `consumo_neto`
  (anulaciones restan, familia y marca por reglas) y conectarla en **solo lectura**; cada herramienta usa un cursor
  propio. Las ventanas se cuentan desde la **fecha de corte** (último movimiento) para que las respuestas sean
  reproducibles. La única escritura (novedades) va a un SQLite aparte. Al repo solo entra una **muestra
  anonimizada** (44 equipos recodificados, órdenes `OT-######`, importes ×U(0,75; 1,25), sin usuarios, series ni VIN).
- **Alternativas:** PostgreSQL (más operación para datos de solo lectura), pandas en memoria (más RAM y lento al
  arrancar), SQL generado por el LLM (riesgo de inyección y de cifras inventadas).
- **Consecuencias:** consultas en milisegundos, cifras deterministas que pasan el verificador del M2; la base real se
  regenera con un comando cuando llegue un exporte nuevo; CI corre con la muestra.

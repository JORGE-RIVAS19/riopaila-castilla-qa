# ADR-009 · Manuales: la página es el documento y la respuesta trae su foto

- **Estado:** aceptada · 2026-11-23
- **Contexto:** 22 PDF (5.217 páginas útiles) en español, inglés y portugués; catálogos de partes donde la lámina va en
  la página anterior a la lista; planos y una caja de fusibles escaneados. El técnico necesita **ver** la figura.
- **Decisión:** cada página es un documento (`pypdfium2`, licencia permisiva; OCR con Tesseract para los escaneados);
  búsqueda **multi-consulta léxica** (BM25 de la pregunta + BM25 con glosario técnico ES→EN/PT, fusionadas con RRF) y
  **densa** en Qdrant con filtro de *payload* por manual, todo fusionado con RRF (k=60). La herramienta responde con la
  **imagen de la página** y lo buscado resaltado (cajas del texto o de Tesseract) y, en catálogos de partes, también la
  lámina.
- **Evidencia:** 25 consultas con relevancia por patrón: el glosario aplicado solo empeoraba los manuales en español
  (nDCG@10 0,513); fusionado por RRF mejora sobre la línea base (0,561 → 0,580; MRR 0,687 → 0,723). La proyección
  UMAP muestra que el espacio léxico agrupa por idioma (pureza kNN por idioma 0,99).
- **Alternativas:** chunks de 500 tokens (rompen la relación texto-figura), PyMuPDF (AGPL), solo búsqueda densa (los
  códigos y números de parte se recuperan mejor con BM25).
- **Consecuencias:** los PDF quedan solo en el servidor; la caché de imágenes vive en el workspace de OpenClaw para
  que `fs.workspaceOnly` permita enviarlas.

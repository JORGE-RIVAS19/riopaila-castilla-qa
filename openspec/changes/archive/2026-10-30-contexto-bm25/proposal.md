# Propuesta: preselección BM25 cuando el corpus no cabe en el contexto

## Por qué
El taller pide consolidar todo el texto limpio en el prompt de sistema. Con Llama 3.2 3B en Ollama, un
`num_ctx` mayor a ~16k tokens agota la RAM de un portátil, y el corpus completo del sitio supera ese tamaño.
Además, *Lost in the Middle* (Liu et al., 2023) muestra que el modelo recupera peor lo que queda en el
centro de un contexto largo.

## Qué cambia
- Modo `completo`: todo el corpus en el prompt (para modelos de contexto largo como Gemini).
- Modo `bm25`: los fragmentos más relevantes dentro de un presupuesto de tokens, ordenados en U.
- Modo `auto` (por defecto): `completo` si cabe; si no, `bm25`.

## Impacto
Sin dependencias nuevas (BM25 implementado en `corpus.py`). Es el puente natural al RAG con embeddings del Módulo 2.

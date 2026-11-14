# Declaración de uso de IA

Política del curso: se promueve el uso de asistentes de IA, con transparencia sobre qué herramienta se usó,
para qué y cómo se verificó el resultado. La autoría y la defensa técnica del proyecto son del equipo.

| Herramienta | Para qué | Cómo se verificó |
|---|---|---|
| Claude (Anthropic), asistente de código | Andamiaje inicial del pipeline, la app de Streamlit, las pruebas y borradores de la documentación | Revisión línea a línea por el equipo, 24 pruebas automáticas (pytest) con un sitio WordPress simulado y un LLM falso, Ruff, y ejecución real del pipeline y la app contra el sitio de la empresa |
| Gemini 3.6 Flash (API) y Llama 3.2 3B (Ollama) | Motor del sistema Q&A, Resumen y FAQ | Batería de 24 preguntas con métricas automáticas, tres corridas de la versión final y revisión manual de ejemplos |

Reglas que seguimos:
- Ningún paquete sugerido por IA se instaló sin verificarlo en PyPI (riesgo de *slopsquatting*); todas las
  dependencias están fijadas con hash en `uv.lock`.
- Los datos del corpus salen solo del pipeline; nada se copió a mano ni lo generó un modelo.
- Cada integrante debe poder explicar cualquier archivo del repositorio sin leer el README.

## Módulo 2

- Se usó un asistente de código (Claude) para el andamiaje del backend (grafo, herramientas, API), del frontend
  React y de las pruebas. Cada pieza se verificó con pytest/Vitest, con un LLM simulado con *tool calling* y,
  antes de la sustentación, con Gemini y los embeddings reales.
- Las 36 cifras del CSV las extrajimos a mano de las noticias del corpus Gold y una prueba comprueba que cada URL
  de origen existe en el corpus. Ningún modelo generó datos.
- Las 28 consultas del set de retrieval y sus documentos relevantes las etiquetamos nosotros.
- El documento de `data/adversarial/` es sintético a propósito (caso 5) y está marcado como tal en el índice y en la app.

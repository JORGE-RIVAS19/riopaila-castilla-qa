# Declaración de uso de IA

Política del curso: se promueve el uso de asistentes de IA, con transparencia sobre qué herramienta se usó,
para qué y cómo se verificó el resultado. La autoría y la defensa técnica del proyecto son del equipo.

| Herramienta | Para qué | Cómo se verificó |
|---|---|---|
| Claude (Anthropic), asistente de código | Andamiaje inicial del pipeline, la app de Streamlit, las pruebas y borradores de la documentación | Revisión línea a línea por el equipo, 22 pruebas automáticas (pytest) con un sitio WordPress simulado y un LLM falso, Ruff, y ejecución real del pipeline y la app contra el sitio de la empresa |
| Llama 3.2 3B (Ollama) | Motor del sistema Q&A, Resumen y FAQ | Batería de 24 preguntas con métricas automáticas y calificación manual |

Reglas que seguimos:
- Ningún paquete sugerido por IA se instaló sin verificarlo en PyPI (riesgo de *slopsquatting*); todas las
  dependencias están fijadas con hash en `uv.lock`.
- Los datos del corpus salen solo del pipeline; nada se copió a mano ni lo generó un modelo.
- Cada integrante debe poder explicar cualquier archivo del repositorio sin leer el README.

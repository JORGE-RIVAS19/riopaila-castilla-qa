# Cambio: Módulo 2 · agente conversacional

## Por qué
El Q&A del M1 responde una pregunta a la vez y mete el contexto completo o por BM25. El M2 pide un agente que
converse, recuerde, decida qué fuente usar y resista inyección indirecta, con frontend propio.

## Qué cambia
- Nuevo backend FastAPI (`api/`) y frontend React (`frontend/`); se retira el dashboard Streamlit.
- Grafo LangGraph `router → directo | agente` con `create_agent`, herramientas y middleware.
- Índice Qdrant sobre los chunks Gold (limpios) y recuperación híbrida RRF.
- CSV de indicadores públicos y herramientas deterministas.
- Memoria SqliteSaver + SqliteStore; trazas LangSmith/JSONL; evaluación recall@10/nDCG@10.

## Criterios de aceptación (casos del Anuncio 006)
1. **RAG**: responde con cita [n] (documento y fragmento) y se abstiene sin evidencia.
2. **Memoria**: el hilo continúa tras reiniciar el backend; el perfil se recupera en un hilo nuevo.
3. **Datos**: la cifra sale de `consultar_indicadores`; el LLM no calcula.
4. **Mixto**: el router habilita documentos + CSV y `comparar_cifras` hace la aritmética; un saludo no busca.
5. **Blindaje**: un documento con «ignora las instrucciones anteriores» se trata como dato y se reporta.

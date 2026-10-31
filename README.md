<div align="center">

# 🌾 Riopaila Castilla · Base de Conocimiento Semántico y Sistema Q&A

**Módulo 1 del asistente corporativo · Técnicas Avanzadas de IA aplicadas en Modelos de Lenguaje (TAAML)**
Maestría en Inteligencia Artificial y Ciencias de Datos · Universidad Autónoma de Occidente · 2026-2S · **Grupo 3**

[![CI](https://github.com/JORGE-RIVAS19/riopaila-castilla-qa/actions/workflows/ci.yml/badge.svg)](https://github.com/JORGE-RIVAS19/riopaila-castilla-qa/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white)
[![uv](https://img.shields.io/badge/entorno-uv-DE5FE9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
![LangChain](https://img.shields.io/badge/LangChain-LCEL-1C3C3C?logo=langchain)
![Ollama](https://img.shields.io/badge/LLM-Ollama%20%7C%20Gemini%20%7C%20OpenAI-000000?logo=ollama)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-0f6b3a.svg)](LICENSE)

</div>

---

## 📌 Problema

**Necesidad de un canal de comunicación automatizado y preciso para Riopaila Castilla S.A.**

Riopaila Castilla es un grupo agroindustrial del Valle del Cauca con públicos muy distintos: clientes de
azúcares, mieles y mezclas; compradores de energía y alcohol carburante; proveedores y cultivadores de caña;
comunidades; inversionistas y aspirantes a empleo. La información pública que necesitan está repartida en
decenas de páginas y noticias del sitio oficial. Un chatbot que responda "de memoria" con un LLM genérico
**inventa datos**; uno que no tenga el contenido de la empresa **no sirve**.

## 💡 Solución

**Un sistema Q&A con el conocimiento público de la empresa como núcleo de un futuro chatbot (RAG).**

1. **Pipeline de scraping Medallion** (Bronze → Silver → Gold) reproducible con `uv run`, que respeta
   `robots.txt`, usa el `wp-sitemap.xml`, se identifica con User-Agent, aplica timeout y rate limit.
2. **Corpus Gold**: un Markdown por página con frontmatter (URL, título, sección, fecha de captura, hash,
   tokens), `corpus.jsonl`, `chunks.jsonl` y una base consolidada `knowledge_base.md`.
3. **Prompt de sistema** que consolida el conocimiento, con estructura sándwich, delimitación XML,
   citas obligatorias `[n]` verificadas en código, abstención explícita y defensa contra inyección.
4. **Tres tareas con LangChain**: **Resumen** ejecutivo, **FAQ** con salida estructurada (Pydantic) y **Q&A**.
5. **Dashboard en Streamlit** que muestra el scraping por etapas, las métricas del corpus y el Q&A con fuentes.
6. **Batería de 24 pruebas** (alcance, fuera de alcance e inyección) con métricas automáticas.

## 🏗️ Arquitectura

```mermaid
flowchart LR
    W["🌐 riopaila-castilla.com<br/>robots.txt · wp-sitemap.xml"] -->|descubrir| B
    subgraph Pipeline["scripts/scrape_empresa.py"]
        B["🥉 Bronze · data/raw<br/>HTML crudo + captures.jsonl"] -->|limpiar| S["🥈 Silver · data/processed<br/>Markdown limpio"]
        S -->|deduplicar + enriquecer| G["🥇 Gold · data/gold<br/>.md + frontmatter · corpus.jsonl · chunks.jsonl"]
    end
    G --> C{"Contexto del prompt<br/>completo · BM25"}
    C --> L["🦜 LangChain LCEL<br/>Ollama Llama 3.2 · Gemini · OpenAI"]
    L --> V["✅ Validación en código<br/>citas · abstención · Pydantic"]
    V --> U["🖥️ Streamlit<br/>Resumen · FAQ · Q&A"]
```

| Decisión | Elección | Por qué |
|---|---|---|
| LLM (Módulo 1) | **Gemini 3.6 Flash** por API para la demo y la evaluación · **Llama 3.2 3B en Ollama** como opción local | En la prueba real, el modelo local tardó 80–125 s por respuesta en CPU y no siguió las reglas; Gemini responde en 3–10 s. Se cambia desde `.env` o la barra lateral |
| Framework | **LangChain (LCEL)** | Plantillas `ChatPromptTemplate`, `with_structured_output` y cambio de proveedor sin tocar el código |
| Muestreo | **T = 0.0 · top_p = 0.1** (Q&A, FAQ) · T = 0.3 · top_p = 0.9 (resumen) | Régimen Q1 para hechos y JSON; Q2 para resúmenes (Clase 4). Gemini 3.x usa muestreo fijo |
| Resultado | **95,8 %** de éxito en 24 preguntas (v3), 100 % de citas válidas, abstención y rechazo de inyección | Ver `docs/INFORME.md` y `prompts/README.md` |
| Contexto | **Corpus completo** si cabe; si no, **BM25** + reordenamiento en U | *Lost in the Middle* (Liu et al., 2023) y límite de `num_ctx` del modelo local |
| Chunking | `RecursiveCharacterTextSplitter` 1 200 chars / 150 de solape, cortando primero por `##` | Fragmentos autocontenidos listos para embeddings |
| Módulo 2 | `nomic-embed-text-v2-moe` (Ollama) + **ChromaDB** | Embeddings abiertos sin costo de API sobre `chunks.jsonl` |

## ⚙️ Instalación

Requisitos: [uv](https://docs.astral.sh/uv/) · [Ollama](https://ollama.com) · Git. (uv descarga Python 3.13 solo.)

```bash
git clone https://github.com/JORGE-RIVAS19/riopaila-castilla-qa.git
cd riopaila-castilla-qa
uv sync                         # crea .venv con las versiones exactas de uv.lock
cp .env.example .env            # en Windows: copy .env.example .env
ollama pull llama3.2:3b         # modelo local por defecto
```

## ▶️ Uso

```bash
# 1. Pipeline completo en línea (≈ 1 s por página por cortesía con el servidor)
uv run python scripts/scrape_empresa.py

# Variantes
uv run python scripts/scrape_empresa.py --offline              # regenera Silver/Gold desde Bronze, sin red
uv run python scripts/scrape_empresa.py --refresh --max-pages 5 # demo: vuelve a descargar 5 páginas

# 2. Dashboard
uv run streamlit run app.py

# 3. Batería de 24 preguntas (y comparación de versiones de prompt)
uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --prompt qa_v1_zero_shot

# 4. Laboratorio Clase 4: JSONL verificable con Pydantic y T = 0
uv run python scripts/extract_structured.py

# Calidad
uv run ruff check . && uv run pytest
```

Para usar una API en lugar de Ollama: en `.env` pon `LLM_PROVIDER=gemini` y `GOOGLE_API_KEY=...`
(o `openai` y `OPENAI_API_KEY`), o cámbialo en la barra lateral de la app.

## 📁 Estructura

```text
riopaila-castilla-qa/
├── app.py                         # Dashboard Streamlit (contexto, pipeline, Q&A, resumen, FAQ, evaluación, corpus)
├── scripts/
│   ├── scrape_empresa.py          # CLI del pipeline Medallion
│   ├── run_eval.py                # batería de 24 preguntas → data/eval + docs/evaluacion
│   └── extract_structured.py      # ficha estructurada con Pydantic (Clase 4)
├── src/riopaila_qa/
│   ├── config.py                  # configuración por .env
│   ├── scraping/                  # discovery · fetcher · bronze · silver · dedup · gold · chunking · pipeline
│   ├── corpus.py                  # carga Gold, BM25 y armado del contexto
│   ├── llm.py                     # fábrica de modelos LangChain + calibración de muestreo
│   ├── prompts.py                 # carga de prompts versionados
│   ├── tasks.py                   # Q&A, Resumen y FAQ (LCEL + validación)
│   └── evaluation.py              # métricas automáticas de la batería
├── prompts/                       # prompts versionados (v1 → v3) y bitácora de experimentos
├── data/
│   ├── raw/                       # 🥉 Bronze (no versionado, se regenera)
│   ├── processed/                 # 🥈 Silver (no versionado, se regenera)
│   ├── gold/                      # 🥇 Gold: base de conocimiento entregable
│   └── eval/                      # preguntas de prueba y resultados
├── docs/                          # informe, guion de sustentación, uso de IA, ADR
├── openspec/                      # especificaciones (SDD)
├── skills/wordpress-corpus-medallion/SKILL.md
├── tests/                         # pytest con sitio WordPress simulado y LLM falso
├── AGENTS.md                      # reglas para agentes de código (OpenCode / GGA)
├── pyproject.toml · uv.lock · .python-version
└── LICENSE                        # MIT
```

## 🖼️ Capturas

| Pipeline por etapas | Q&A con fuentes |
|---|---|
| ![Pipeline](docs/img/pipeline.png) | ![Q&A](docs/img/qa.png) |

## 🔒 Ética y datos

- Solo contenido público; se respeta `robots.txt` (`/wp-admin/` no se toca) y se omite el sitemap de
  **usuarios** de WordPress (datos personales, Ley 1581 de 2012 — Habeas Data).
- User-Agent identificable, 1 s entre peticiones, timeout de 15 s y reintentos con espera exponencial.
- Las capas Bronze y Silver no se versionan; el `.env` y las API keys nunca entran al repositorio.

## 📚 Documentación

- [Informe técnico](docs/INFORME.md) · [Experimentos de prompts](prompts/README.md) ·
  [Guion de la sustentación](docs/GUION_SUSTENTACION.md) · [Uso de IA](docs/USO_DE_IA.md) ·
  [Especificaciones](openspec/) · [Decisiones (ADR)](docs/adr/)

## 👥 Créditos

- Melissa Palacios Domínguez
- Waldor Drada Arango
- Jorge Andrés Rivas Manzano

Code Reviewer del Grupo 3: el profesor (asignado el día de la sustentación).
Profesor: **Jan Polanco Velasco** · Universidad Autónoma de Occidente.
Fuente de datos: sitio público de [Riopaila Castilla S.A.](https://www.riopaila-castilla.com) — el contenido
pertenece a la empresa y se usa con fines académicos.

## 📄 Licencia

Código bajo licencia [MIT](LICENSE) © 2026 Melissa Palacios Domínguez, Waldor Drada Arango y Jorge Andrés Rivas Manzano.

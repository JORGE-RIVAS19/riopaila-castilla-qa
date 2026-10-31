# AGENTS.md · Reglas para agentes de código (OpenCode, Claude Code, Cursor, GGA)

Este archivo fija la arquitectura del repositorio. GGA lo usa para auditar el *staging area* en cada commit.

## Contexto
Asistente de conocimiento corporativo de **Riopaila Castilla S.A.** (TAAML · UAO · Grupo 3).
Módulo 1: scraping Medallion + prompt de sistema + tareas Resumen, FAQ y Q&A en Streamlit.

## Reglas de arquitectura
1. **Capas separadas**: `scraping/` (datos) no importa nada de `tasks.py`, `corpus.py` ni `app.py`.
   `app.py` solo orquesta UI: la lógica vive en `src/riopaila_qa/`.
2. **Medallion**: Bronze (`data/raw`) nunca se edita a mano; Silver y Gold se regeneran con
   `uv run python scripts/scrape_empresa.py --offline`. Solo Gold entra al LLM.
3. **Prompts versionados**: todo prompt vive en `prompts/<id>.md` con encabezado de metadatos y bloques
   `=== SYSTEM ===` / `=== HUMAN ===`. Prohibido escribir prompts dentro del código Python.
4. **Muestreo**: Q&A, FAQ y extracción con `temperature=0.0`, `top_p=0.1`. Cambiarlo exige justificar en
   `prompts/README.md`.
5. **Validación en código**: toda salida del LLM se valida (citas contra el contexto, esquema Pydantic).
6. **Scraping ético**: respetar `robots.txt`, User-Agent identificable, timeout y ≥1 s entre peticiones;
   nunca rastrear sitemaps de usuarios ni datos personales (Ley 1581).

## Estándares
- Entorno **solo con uv** (Python 3.13): `uv add`, `uv sync`, `uv run`. Prohibido `pip install` y `requirements.txt`.
- PEP 8 vía Ruff (`uv run ruff check . && uv run ruff format .`), docstrings en español en funciones públicas,
  type hints en todo el código nuevo.
- Pruebas con `pytest`, sin red ni LLM real (sitio simulado y `FakeListChatModel`).
- Dependencias: no agregar paquetes que no estén en `pyproject.toml` sin aprobación humana
  (riesgo de *slopsquatting*); verificar el nombre en PyPI antes de `uv add`.

## Git
- Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `ci:`), commits atómicos y
  cuerpo que explique **por qué**.
- Ramas `feat/*`, `fix/*`, `docs/*`; integración a `main` solo por Pull Request con la plantilla y CI en verde.
- Nunca versionar `.env`, API keys, `data/raw` ni `data/processed`.

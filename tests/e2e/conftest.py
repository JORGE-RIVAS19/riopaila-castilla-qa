"""QA end-to-end con Playwright (anuncio 008): API, webhook y frontend, en teléfono y escritorio.

Dos modos:

* **Local (por defecto, CI):** levanta el API en un puerto libre con el LLM guionado y la muestra anonimizada del
  taller; sirve el frontend compilado (``frontend/dist``) desde el mismo origen.
* **Desplegado:** ``E2E_BASE_URL=http://127.0.0.1:8000 uv run pytest tests/e2e`` en el servidor (o por el túnel
  SSH) corre las mismas pruebas contra la app real, con DeepSeek. Las aserciones que dependen del modelo guionado se
  relajan en este modo.

Capturas, consola y traza de cada corrida quedan en ``tests/e2e/artifacts/`` (fuera del repositorio).
"""

from __future__ import annotations

import os
import socket
import threading
import time
from dataclasses import replace

import httpx
import pytest

from tests.e2e._comun import DESPLEGADO


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url(tmp_path_factory) -> str:
    if DESPLEGADO:
        return os.environ["E2E_BASE_URL"].rstrip("/")
    import uvicorn

    from api.main import _MEDIA, app
    from riopaila_qa.agent.service import AgentService
    from riopaila_qa.agent.settings import AgentSettings
    from riopaila_qa.taller.base import cargar_csv
    from riopaila_qa.taller.config import MUESTRA_DIR

    tmp = tmp_path_factory.mktemp("e2e")
    db = tmp / "taller.duckdb"
    cargar_csv(MUESTRA_DIR / "equipos.csv", MUESTRA_DIR / "materiales.csv", MUESTRA_DIR / "consumos.csv", db)
    entorno = {
        "TALLER_DB": str(db),
        "TALLER_DB_MUESTRA": str(db),
        "MEDIA_DIR": str(_MEDIA),  # la carpeta que el API ya montó en /media
        "TALLER_NOVEDADES_DB": str(tmp / "nov.sqlite"),
        "MANUALES_DIR": str(tmp / "sin_manuales"),
        "TALLER_ROLES": "573001112233=tecnico",
        "WHATSAPP_VERIFY_TOKEN": "token-de-prueba",
    }
    previo = {k: os.environ.get(k) for k in entorno}
    os.environ.update(entorno)
    s = replace(
        AgentSettings(),
        router_mode="reglas",
        embed_provider="fake",
        qdrant_path=tmp / "q",
        memory_dir=tmp / "m",
        trace_dir=tmp / "logs",
    )
    app.state.agent_override = AgentService(s, fake_llm=True)
    puerto = _puerto_libre()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning"))
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{puerto}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}/api/health", timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    yield url
    server.should_exit = True
    hilo.join(timeout=10)
    app.state.agent_override = None
    for k, v in previo.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture(scope="session")
def api(base_url):
    with httpx.Client(base_url=base_url, timeout=180) as cliente:
        yield cliente


@pytest.fixture(scope="module")  # se cierra al terminar el módulo: el loop de Playwright no queda vivo
def navegador():
    pw_sync = pytest.importorskip("playwright.sync_api")
    with pw_sync.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:  # noqa: BLE001 — sin Chromium instalado (CI sin `playwright install`)
            pytest.skip(f"Chromium de Playwright no disponible: {exc}")
        yield browser
        browser.close()

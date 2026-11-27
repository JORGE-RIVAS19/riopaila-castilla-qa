"""QA del frontend con Playwright (anuncio 008): teléfono 390×844 y escritorio, consola limpia, sin 4xx/5xx."""

from __future__ import annotations

import httpx
import pytest

from tests.e2e._comun import ARTEFACTOS, DESPLEGADO, EVAL_RETRIEVAL

PANTALLAS = {"telefono": {"width": 390, "height": 844}, "escritorio": {"width": 1440, "height": 900}}


@pytest.fixture(scope="module")
def web(base_url):
    r = httpx.get(f"{base_url}/chat", timeout=10)
    if r.status_code != 200 or "<html" not in r.text.lower():
        pytest.skip("El frontend no está compilado en este despliegue (cd frontend && pnpm build)")
    return base_url


@pytest.mark.parametrize("pantalla", list(PANTALLAS))
def test_flujo_del_pitch_en_la_web(navegador, web, pantalla):
    ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    contexto = navegador.new_context(viewport=PANTALLAS[pantalla], locale="es-CO")
    contexto.tracing.start(screenshots=True, snapshots=True)
    pagina = contexto.new_page()
    errores_consola: list[str] = []
    fallidas: list[str] = []
    pagina.on("console", lambda m: errores_consola.append(m.text) if m.type == "error" else None)
    pagina.on("pageerror", lambda e: errores_consola.append(str(e)))
    pagina.on("response", lambda r: fallidas.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    try:
        pagina.goto(f"{web}/", wait_until="networkidle")
        assert pagina.url.endswith("/chat")
        caja = pagina.get_by_label("Mensaje")
        caja.fill("¿Qué es Riopaila Castilla en cifras?")
        caja.press("Enter")
        if not DESPLEGADO:  # con el modelo guionado la infografía llega siempre; con DeepSeek, casi siempre
            imagen = pagina.locator('img[src*="/media/"]').first
            imagen.wait_for(state="visible", timeout=60_000)
            assert imagen.evaluate("i => i.complete && i.naturalWidth > 0")
        else:
            pagina.wait_for_function(
                "() => document.querySelectorAll('.msg, [class*=message], [class*=bubble]').length >= 2",
                timeout=120_000,
            )
        pagina.wait_for_load_state("networkidle")
        pagina.screenshot(path=str(ARTEFACTOS / f"pitch_{pantalla}.png"), full_page=True)
        # Las demás páginas de la torre de control también cargan sin errores.
        paginas = ["/datos", "/memoria", "/arquitectura"]
        if DESPLEGADO or EVAL_RETRIEVAL.exists():
            paginas.append("/evaluacion")
        for ruta in paginas:
            pagina.goto(f"{web}{ruta}", wait_until="networkidle")
        assert not fallidas, fallidas
        assert not errores_consola, errores_consola
        assert not fallidas, fallidas
        ancho = pagina.evaluate("() => document.documentElement.scrollWidth")
        assert ancho <= PANTALLAS[pantalla]["width"] + 1, f"scroll horizontal en {pantalla}: {ancho}px"
    finally:
        contexto.tracing.stop(path=str(ARTEFACTOS / f"traza_{pantalla}.zip"))
        contexto.close()

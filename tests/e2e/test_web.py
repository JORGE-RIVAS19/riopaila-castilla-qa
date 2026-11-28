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


def _esperar_respuesta(pagina, n: int) -> None:
    """Espera a que la n-ésima respuesta del asistente termine de llegar (sin el cursor de streaming)."""
    pagina.wait_for_function(
        """n => {
            const m = document.querySelectorAll('.msg-assistant');
            if (m.length < n) return false;
            const ultima = m[m.length - 1];
            return !ultima.querySelector('.streaming') && ultima.innerText.trim().length > 20;
        }""",
        arg=n,
        timeout=150_000 if DESPLEGADO else 30_000,
    )


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

        # 1) Flujo del pitch (anuncio 008): pregunta → respuesta con citas y la tool ejecutada, visibles en la app.
        caja.fill("¿Qué dice el corpus sobre la política de calidad de Riopaila Castilla?")
        caja.press("Enter")
        _esperar_respuesta(pagina, 1)
        pagina.get_by_role("tab", name="Fuentes").click()
        citas = pagina.locator(".inspector .sources .cite")
        citas.first.wait_for(state="visible", timeout=10_000)
        assert citas.count() >= 1
        pagina.get_by_role("tab", name="Herramientas").click()
        herramientas = pagina.locator(".inspector .tool-list")
        herramientas.wait_for(state="visible", timeout=10_000)
        assert "buscar_documentos" in herramientas.inner_text()
        pagina.screenshot(path=str(ARTEFACTOS / f"citas_{pantalla}.png"), full_page=True)

        # 2) Vitrina del M1/M2: la infografía de Riopaila en cifras se ve en el chat.
        caja.fill("¿Qué es Riopaila Castilla en cifras?")
        caja.press("Enter")
        _esperar_respuesta(pagina, 2)
        if not DESPLEGADO:  # con el modelo guionado la infografía llega siempre; con DeepSeek, casi siempre
            imagen = pagina.locator('img[src*="/media/"]').first
            imagen.wait_for(state="visible", timeout=60_000)
            assert imagen.evaluate("i => i.complete && i.naturalWidth > 0")
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
        ancho = pagina.evaluate("() => document.documentElement.scrollWidth")
        assert ancho <= PANTALLAS[pantalla]["width"] + 1, f"scroll horizontal en {pantalla}: {ancho}px"
    finally:
        contexto.tracing.stop(path=str(ARTEFACTOS / f"traza_{pantalla}.zip"))
        contexto.close()

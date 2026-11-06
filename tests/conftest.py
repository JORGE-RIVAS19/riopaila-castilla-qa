"""Fixtures: un sitio WordPress simulado servido en localhost.

El contenido es sintético (empresa ficticia) y solo sirve para probar el
pipeline sin depender de internet; nunca entra al corpus real.
"""

from __future__ import annotations

import functools
import http.server
import threading
from pathlib import Path

import pytest

from riopaila_qa.config import LLMSettings, Paths, ScraperSettings, Settings

HEADER = """<header class="site-header"><nav class="main-menu"><a href="/">Inicio</a>
<a href="/somos/">Quiénes somos</a><a href="/productos/">Productos</a></nav></header>
<div class="accessibility-panel"><p>Modo seguro para epilepsia. Modo visual. Modo cognitivo.</p></div>"""
FOOTER = """<footer class="site-footer"><p>Oficina principal: Calle Falsa 123, Ciudad Ejemplo.</p>
<p>Línea ética: 01 8000 000 000. Copyright© Empresa Ejemplo S.A.</p></footer>"""


def page(title: str, body: str, published: str | None = None) -> str:
    meta = f'<meta property="article:published_time" content="{published}">' if published else ""
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>{title} – Empresa Ejemplo</title><meta property="og:title" content="{title} – Empresa Ejemplo">{meta}
</head><body class="menu-horizontal header-style-1">{HEADER}<main><h1>{title}</h1>{body}</main>{FOOTER}</body></html>"""


LOREM = (
    "La Empresa Ejemplo es una organización agroindustrial ficticia creada para pruebas automáticas. "
    "Produce bienes de ejemplo en tres regiones imaginarias y trabaja con comunidades de prueba. "
)

PAGES = {
    "somos/": page(
        "Quiénes somos", f"<h2>Historia</h2><p>{LOREM * 3}</p><p>Fundada en el año 1900 en Ciudad Ejemplo.</p>"
    ),
    "productos/": page(
        "Productos", f"<h2>Azúcar ficticia</h2><p>{LOREM * 2}</p><ul><li>Producto A</li><li>Producto B</li></ul>"
    ),
    "productos-copia/": page(
        "Productos", f"<h2>Azúcar ficticia</h2><p>{LOREM * 2}</p><ul><li>Producto A</li><li>Producto B</li></ul>"
    ),
    "corta/": page("Página corta", "<p>Muy poco texto.</p>"),
    "privado/": page("Privado", f"<p>{LOREM * 3}</p>"),
    "noticia-uno/": page("Noticia uno", f"<p>Primera noticia de prueba. {LOREM * 3}</p>", "2026-05-01T10:00:00+00:00"),
}


@pytest.fixture()
def mock_site(tmp_path: Path):
    """Levanta el sitio simulado y devuelve su URL base."""
    site = tmp_path / "site"
    site.mkdir()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    handler.log_message = lambda *a, **k: None  # silencia el log del servidor
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    base = f"http://127.0.0.1:{server.server_address[1]}"

    for rel, html in PAGES.items():
        target = site / rel / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
    (site / "index.html").write_text(page("Inicio", f"<p>{LOREM}</p>"), encoding="utf-8")
    (site / "robots.txt").write_text(
        f"User-agent: *\nDisallow: /wp-admin/\nDisallow: /privado/\nSitemap: {base}/wp-sitemap.xml\n", encoding="utf-8"
    )

    def urlset(paths: list[str]) -> str:
        locs = "".join(f"<url><loc>{base}/{p}</loc></url>" for p in paths)
        return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>'

    (site / "wp-sitemap.xml").write_text(
        '<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<sitemap><loc>{base}/wp-sitemap-posts-page-1.xml</loc></sitemap>"
        f"<sitemap><loc>{base}/wp-sitemap-posts-post-1.xml</loc></sitemap>"
        f"<sitemap><loc>{base}/wp-sitemap-users-1.xml</loc></sitemap>"
        "</sitemapindex>",
        encoding="utf-8",
    )
    (site / "wp-sitemap-posts-page-1.xml").write_text(
        urlset(["somos/", "productos/", "productos-copia/", "corta/", "privado/", "tag/algo/"]), encoding="utf-8"
    )
    (site / "wp-sitemap-posts-post-1.xml").write_text(urlset(["noticia-uno/"]), encoding="utf-8")
    (site / "wp-sitemap-users-1.xml").write_text(urlset(["author/juan/"]), encoding="utf-8")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield base
    server.shutdown()


@pytest.fixture()
def test_settings(tmp_path: Path, mock_site: str) -> Settings:
    """Configuración aislada: datos en tmp_path, sin pausas y apuntando al sitio simulado."""
    root = tmp_path / "proj"
    paths = Paths(
        root=root,
        raw=root / "data" / "raw",
        processed=root / "data" / "processed",
        gold=root / "data" / "gold",
        eval_dir=root / "data" / "eval",
        prompts=Path(__file__).resolve().parents[1] / "prompts",
    )
    scraper = ScraperSettings(
        base_url=mock_site, company="Empresa Ejemplo S.A.", delay_s=0.0, timeout_s=5, min_chars=150
    )
    return Settings(paths=paths, scraper=scraper, llm=LLMSettings())

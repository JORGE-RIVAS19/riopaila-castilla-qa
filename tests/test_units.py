"""Pruebas unitarias de las piezas puras del pipeline."""

from __future__ import annotations

from riopaila_qa.scraping.dedup import jaccard, shingles
from riopaila_qa.scraping.discovery import normalize_url, parse_sitemap
from riopaila_qa.scraping.gold import classify_section
from riopaila_qa.scraping.silver import html_to_markdown


def test_normalize_url_strips_encoded_space_and_fragment():
    url = "https://www.riopaila-castilla.com/azucares/%20#top"
    assert normalize_url(url) == "https://www.riopaila-castilla.com/azucares/"
    assert normalize_url("https://x.com/informe.pdf") == "https://x.com/informe.pdf"


def test_parse_sitemap_index_and_urlset():
    index = b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>a.xml</loc></sitemap></sitemapindex>'
    urlset = (
        b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://x.com/p/</loc></url></urlset>'
    )
    assert parse_sitemap(index) == (["a.xml"], [])
    assert parse_sitemap(urlset) == ([], ["https://x.com/p/"])


def test_classify_section_follows_site_menu():
    base = "https://www.riopaila-castilla.com"
    assert classify_section(f"{base}/azucares/", False) == "negocios-y-productos"
    assert classify_section(f"{base}/somos-riopaila-castilla/", False) == "identidad"
    assert classify_section(f"{base}/codigo-de-etica-y-buen-gobierno/", False) == "gobierno-corporativo"
    assert classify_section(f"{base}/agricultura-regenerativa/", False) == "sostenibilidad"
    assert classify_section(f"{base}/una-noticia/", True) == "noticias"
    assert classify_section(f"{base}/", False) == "inicio"


def test_html_to_markdown_drops_scripts_and_menus():
    html = (
        "<html><body class='menu-x'><nav class='menu'>Inicio Productos</nav><main><h1>Título</h1>"
        "<p>" + "Contenido editorial útil. " * 20 + "</p><script>alert(1)</script></main></body></html>"
    )
    md, _ = html_to_markdown(html, "https://x.com/", min_chars=100)
    assert "Contenido editorial útil" in md
    assert "alert(1)" not in md


def test_jaccard_detects_near_duplicates():
    a = shingles("uno dos tres cuatro cinco seis siete ocho nueve diez")
    b = shingles("uno dos tres cuatro cinco seis siete ocho nueve once")
    assert jaccard(a, a) == 1.0
    assert 0.5 < jaccard(a, b) < 1.0

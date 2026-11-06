"""Etapa 3 · Limpiar (Silver): del HTML crudo al texto útil en Markdown.

Primero se intenta la extracción semántica con ``trafilatura`` (solo el cuerpo
editorial). Si devuelve muy poco texto —pasa en sitios armados con page
builders— se usa un respaldo con BeautifulSoup que elimina menús, cabeceras,
pies de página, formularios y el panel de accesibilidad.
"""

from __future__ import annotations

import re

import trafilatura
from bs4 import BeautifulSoup, Tag

from riopaila_qa.scraping.models import Capture, SilverPage
from riopaila_qa.textutils import normalize_text, sha256

NOISE_TAGS = ["script", "style", "noscript", "svg", "iframe", "form", "nav", "header", "footer", "aside", "button"]
NOISE_CLASS_RE = re.compile(
    r"(menu|navbar|nav-|breadcrumb|footer|header|cookie|accessib|a11y|share|social|widget|sidebar|"
    r"search|popup|modal|slider-nav|pagination|comments?)",
    re.IGNORECASE,
)
TITLE_SUFFIX_RE = re.compile(r"\s*[|–—-]\s*Riopaila Castilla.*$", re.IGNORECASE)


def extract_title(soup: BeautifulSoup) -> str:
    """Título limpio: og:title, luego <h1>, luego <title> sin el sufijo del sitio."""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return TITLE_SUFFIX_RE.sub("", og["content"]).strip()
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)
    if soup.title and soup.title.string:
        return TITLE_SUFFIX_RE.sub("", soup.title.string).strip()
    return "Sin título"


def extract_pub_date(soup: BeautifulSoup) -> str | None:
    """Fecha de publicación declarada por WordPress (si existe)."""
    for prop in ("article:published_time", "article:modified_time"):
        meta = soup.find("meta", property=prop)
        if meta and meta.get("content"):
            return meta["content"][:10]
    time_tag = soup.find("time")
    if isinstance(time_tag, Tag) and time_tag.get("datetime"):
        return str(time_tag["datetime"])[:10]
    return None


def _is_noise(tag: Tag) -> bool:
    # Los contenedores raíz suelen llevar clases del tema (p. ej. "menu-horizontal")
    # y nunca deben eliminarse completos.
    if tag.attrs is None or tag.name in ("html", "body", "main", "article"):
        return False
    attrs = " ".join(tag.get("class", [])) + " " + (tag.get("id") or "")
    return bool(NOISE_CLASS_RE.search(attrs))


def bs4_markdown(soup: BeautifulSoup) -> str:
    """Respaldo: convierte el contenido principal a Markdown simple."""
    for tag in soup(NOISE_TAGS):
        tag.decompose()
    for tag in soup.find_all(True):
        if not tag.decomposed and _is_noise(tag):
            tag.decompose()
    root = soup.select_one("main, article, .entry-content, #content, .content") or soup.body or soup
    lines: list[str] = []
    for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "td"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            lines.append(f"\n{'#' * int(el.name[1])} {text}\n")
        elif el.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)
    return normalize_text("\n".join(lines))


def html_to_markdown(html: str, url: str, min_chars: int = 200) -> tuple[str, str]:
    """Devuelve (markdown, extractor usado)."""
    md = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_images=False,
        include_comments=False,
        favor_recall=True,
        # deduplicate=False a propósito: la caché interna de trafilatura guarda
        # estado entre páginas y hace que el resultado dependa del orden. La
        # deduplicación es responsabilidad explícita de la etapa dedup.py.
        deduplicate=False,
    )
    md = normalize_text(md or "")
    fallback = bs4_markdown(BeautifulSoup(html, "lxml"))
    # trafilatura es más limpio, pero en páginas armadas con page builders a
    # veces recorta secciones enteras: si el respaldo trae mucho más texto, gana.
    # El boilerplate extra que traiga el respaldo lo elimina la etapa de dedup.
    if len(md) >= min_chars and len(fallback) <= 1.8 * len(md):
        return md, "trafilatura"
    if len(fallback) > len(md):
        return fallback, "beautifulsoup"
    return md, "trafilatura"


def to_silver(capture: Capture, html: str, min_chars: int = 200) -> SilverPage:
    """Transforma una captura Bronze en una página Silver."""
    soup = BeautifulSoup(html, "lxml")
    title = extract_title(soup)
    pub_date = extract_pub_date(soup)
    markdown, extractor = html_to_markdown(html, capture.url, min_chars)
    return SilverPage(
        url=capture.url,
        titulo=title,
        fecha_captura=capture.fecha_captura,
        fecha_publicacion=pub_date,
        markdown=markdown,
        hash_texto=sha256(markdown),
        extractor=extractor,
    )

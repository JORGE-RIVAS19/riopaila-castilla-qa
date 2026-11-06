"""Etapa 1 · Descubrir: robots.txt + sitemap.xml (con rastreo de enlaces como respaldo)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup
from lxml import etree

from riopaila_qa.config import ScraperSettings
from riopaila_qa.scraping.fetcher import PoliteFetcher

# Rutas que nunca son contenido editorial (listados, feeds, buscador, API, admin).
EXCLUDED_PATTERNS = [
    r"/wp-admin/",
    r"/case-studies/",  # páginas demo de la plantilla del tema (inglés)
    r"/ticket-login",  # login de PQRS: contenido tras autenticación
    r"/wp-json/",
    r"/wp-login",
    r"/feed/?$",
    r"/author/",
    r"/tag/",
    r"/category/",
    r"/page/\d+/?$",
    r"[?&](s|replytocom|share)=",
    r"\.(jpg|jpeg|png|gif|webp|svg|zip|mp4|mp3|css|js|ico|xml|json)$",
]
_EXCLUDED_RE = re.compile("|".join(EXCLUDED_PATTERNS), re.IGNORECASE)


@dataclass
class DiscoveryReport:
    """Resultado de la etapa de descubrimiento."""

    urls: list[str] = field(default_factory=list)
    sitemaps_read: list[str] = field(default_factory=list)
    sitemaps_skipped: list[str] = field(default_factory=list)
    disallowed: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    external: list[str] = field(default_factory=list)
    origin: dict[str, str] = field(default_factory=dict)
    crawl_delay: float | None = None
    method: str = "sitemap"

    @property
    def post_urls(self) -> set[str]:
        """URLs que vienen del sitemap de entradas (noticias) de WordPress."""
        return {u for u, sm in self.origin.items() if "posts-post" in sm}


def normalize_url(url: str) -> str:
    """Quita fragmentos, espacios codificados (``%20``) y fuerza la barra final."""
    url = urldefrag(url.strip())[0]
    url = re.sub(r"(%20|\s)+$", "", url)
    parsed = urlparse(url)
    path = parsed.path or "/"
    last = path.rsplit("/", 1)[-1]
    if not path.endswith("/") and "." not in last:
        path += "/"
    return parsed._replace(path=path, fragment="").geturl()


def same_site(url: str, base_url: str) -> bool:
    """True si ``url`` pertenece al mismo host (con o sin ``www``)."""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    base = urlparse(base_url).netloc.lower().removeprefix("www.")
    return host == base


def load_robots(fetcher: PoliteFetcher, base_url: str) -> tuple[robotparser.RobotFileParser, list[str]]:
    """Descarga y parsea robots.txt; devuelve el parser y los sitemaps declarados."""
    robots_url = urljoin(base_url, "/robots.txt")
    parser = robotparser.RobotFileParser(robots_url)
    result = fetcher.get(robots_url)
    if result.ok:
        lines = result.text.splitlines()
        parser.parse(lines)
        sitemaps = [ln.split(":", 1)[1].strip() for ln in lines if ln.lower().startswith("sitemap:")]
    else:
        parser.parse([])  # sin robots.txt: todo permitido, pero seguimos siendo corteses
        sitemaps = []
    return parser, sitemaps


def parse_sitemap(xml_bytes: bytes) -> tuple[list[str], list[str]]:
    """Parsea un sitemap XML. Devuelve (sub-sitemaps, urls de páginas)."""
    try:
        root = etree.fromstring(xml_bytes, parser=etree.XMLParser(recover=True))
    except etree.XMLSyntaxError:
        return [], []
    if root is None:
        return [], []
    locs = [el.text.strip() for el in root.iter("{*}loc") if el.text]
    tag = etree.QName(root).localname
    if tag == "sitemapindex":
        return locs, []
    return [], locs


def _sitemap_allowed(sitemap_url: str, settings: ScraperSettings) -> bool:
    name = urlparse(sitemap_url).path.lower()
    if "wp-sitemap" not in name or name.endswith("/wp-sitemap.xml"):
        return True  # índice o sitemap no-WordPress: se recorre completo
    return any(key in name for key in settings.allowed_sitemaps)


def discover_from_sitemaps(
    fetcher: PoliteFetcher, settings: ScraperSettings, sitemap_urls: list[str], report: DiscoveryReport
) -> list[str]:
    """Recorre el índice de sitemaps (BFS) y devuelve las URLs de contenido."""
    queue = list(dict.fromkeys(sitemap_urls))
    seen: set[str] = set()
    pages: list[str] = []
    while queue:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        if not _sitemap_allowed(sm, settings):
            report.sitemaps_skipped.append(sm)
            continue
        result = fetcher.get(sm)
        if not result.ok:
            report.sitemaps_skipped.append(sm)
            continue
        report.sitemaps_read.append(sm)
        children, locs = parse_sitemap(result.content)
        queue.extend(children)
        pages.extend(locs)
        for loc in locs:
            report.origin.setdefault(normalize_url(loc), sm)
    return pages


def discover_by_links(fetcher: PoliteFetcher, settings: ScraperSettings, max_pages: int) -> list[str]:
    """Respaldo sin sitemap: BFS de enlaces internos desde la página de inicio."""
    start = normalize_url(settings.base_url)
    queue, seen, found = [start], {start}, []
    while queue and len(found) < max_pages:
        url = queue.pop(0)
        result = fetcher.get(url)
        if not result.ok or "html" not in result.content_type:
            continue
        found.append(url)
        soup = BeautifulSoup(result.content, "lxml")
        for a in soup.select("a[href]"):
            link = normalize_url(urljoin(url, a["href"]))
            if link not in seen and same_site(link, settings.base_url) and not _EXCLUDED_RE.search(link):
                seen.add(link)
                queue.append(link)
    return found


def discover(fetcher: PoliteFetcher, settings: ScraperSettings, max_pages: int | None = None) -> DiscoveryReport:
    """Ejecuta la etapa completa de descubrimiento y filtra por robots.txt."""
    max_pages = max_pages or settings.max_pages
    report = DiscoveryReport()
    robots, declared = load_robots(fetcher, settings.base_url)
    report.crawl_delay = robots.crawl_delay(settings.user_agent)
    if report.crawl_delay:
        fetcher.delay = max(fetcher.delay, float(report.crawl_delay))

    sitemap_urls = declared or [
        urljoin(settings.base_url, "/wp-sitemap.xml"),
        urljoin(settings.base_url, "/sitemap.xml"),
    ]
    candidates = discover_from_sitemaps(fetcher, settings, sitemap_urls, report)
    if not candidates:
        report.method = "enlaces"
        candidates = discover_by_links(fetcher, settings, max_pages)

    seen: set[str] = set()
    for raw in candidates:
        url = normalize_url(raw)
        if url in seen:
            continue
        seen.add(url)
        if not same_site(url, settings.base_url):
            report.external.append(url)
        elif _EXCLUDED_RE.search(url):
            report.excluded.append(url)
        elif not robots.can_fetch(settings.user_agent, url):
            report.disallowed.append(url)
        else:
            report.urls.append(url)
    report.urls = report.urls[:max_pages]
    return report

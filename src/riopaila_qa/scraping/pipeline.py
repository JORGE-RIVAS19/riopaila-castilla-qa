"""Orquestador del pipeline: descubrir → extraer → limpiar → deduplicar → enriquecer.

Emite eventos por etapa para que la app de Streamlit muestre el progreso en vivo
y deja un ``manifest.json`` con las métricas del corpus.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from riopaila_qa.config import Settings, get_settings
from riopaila_qa.scraping.bronze import capture_urls, load_captures, now_iso
from riopaila_qa.scraping.chunking import CHUNK_OVERLAP, CHUNK_SIZE, chunk_documents, write_chunks
from riopaila_qa.scraping.dedup import deduplicate
from riopaila_qa.scraping.discovery import DiscoveryReport, discover
from riopaila_qa.scraping.fetcher import PoliteFetcher
from riopaila_qa.scraping.gold import to_gold, write_gold
from riopaila_qa.scraping.models import SilverPage
from riopaila_qa.scraping.silver import to_silver

STAGES = ["descubrir", "extraer", "limpiar", "deduplicar", "enriquecer"]

EventFn = Callable[[str, str, str, dict[str, Any]], None]


def _noop(stage: str, status: str, message: str, data: dict[str, Any]) -> None:  # noqa: ARG001
    return None


def _save_discovery(report: DiscoveryReport, settings: Settings) -> None:
    settings.paths.raw.mkdir(parents=True, exist_ok=True)
    payload = asdict(report)
    payload["fecha"] = now_iso()
    (settings.paths.raw / "discovery.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_discovery(settings: Settings) -> DiscoveryReport:
    path = settings.paths.raw / "discovery.json"
    if not path.exists():
        raise FileNotFoundError(
            "No hay capa Bronze todavía. Ejecuta primero el scraping en línea: uv run python scripts/scrape_empresa.py"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("fecha", None)
    return DiscoveryReport(**data)


def run_pipeline(
    settings: Settings | None = None,
    max_pages: int | None = None,
    offline: bool = False,
    refresh: bool = False,
    on_event: EventFn | None = None,
) -> dict[str, Any]:
    """Ejecuta el pipeline completo y devuelve el manifiesto de métricas.

    Args:
        settings: configuración (por defecto la del ``.env``).
        max_pages: tope de descargas nuevas en esta corrida (el resto sale de la caché Bronze).
        offline: reprocesa Silver y Gold desde la capa Bronze sin tocar la web.
        refresh: ignora la caché Bronze y vuelve a descargar todo.
        on_event: callback ``(etapa, estado, mensaje, datos)`` para la UI.
    """
    settings = settings or get_settings()
    emit = on_event or _noop
    paths = settings.paths
    t0 = time.monotonic()
    manifest: dict[str, Any] = {
        "empresa": settings.scraper.company,
        "base_url": settings.scraper.base_url,
        "fecha_ejecucion": now_iso(),
        "modo": "offline (desde Bronze)" if offline else "en línea",
        "user_agent": settings.scraper.user_agent,
    }

    # 1 · Descubrir --------------------------------------------------------
    emit("descubrir", "start", "Leyendo robots.txt y sitemap.xml", {})
    fetcher = PoliteFetcher(settings.scraper)
    if offline:
        report = _load_discovery(settings)
    else:
        report = discover(fetcher, settings.scraper)
        _save_discovery(report, settings)
    urls = report.urls
    manifest["descubrir"] = {
        "metodo": report.method,
        "sitemaps_leidos": len(report.sitemaps_read),
        "sitemaps_omitidos": report.sitemaps_skipped,
        "urls_descubiertas": len(report.urls) + len(report.disallowed) + len(report.excluded),
        "urls_a_capturar": len(urls),
        "tope_descargas_corrida": max_pages,
        "descartes": {
            "robots_disallow": len(report.disallowed),
            "patrones_excluidos": len(report.excluded),
            "externas": len(report.external),
        },
        "crawl_delay_s": report.crawl_delay,
        "pausa_entre_peticiones_s": fetcher.delay,
    }
    emit("descubrir", "done", f"{len(urls)} URLs a capturar", manifest["descubrir"])

    # 2 · Extraer (Bronze) ------------------------------------------------
    emit("extraer", "start", "Descargando HTML crudo a data/raw/", {})
    if offline:
        captures_by_url = load_captures(settings.paths)
        captures = [captures_by_url[u] for u in urls if u in captures_by_url]
    else:
        captures = capture_urls(
            urls,
            fetcher,
            paths,
            refresh=refresh,
            on_progress=lambda i, n, msg: emit("extraer", "progress", msg, {"i": i, "n": n}),
            max_downloads=max_pages,
        )
    ok = [c for c in captures if c.status == 200 and c.html_path]
    html_caps = [c for c in ok if "html" in (c.content_type or "text/html")]
    raw_bytes = sum(c.bytes for c in html_caps)
    manifest["extraer"] = {
        "paginas_descargadas": len(ok),
        "desde_cache": sum(1 for c in captures if c.from_cache),
        "peticiones_http": fetcher.requests_made,
        "errores": [{"url": c.url, "status": c.status, "error": c.error} for c in captures if c not in ok],
        "no_html": len(ok) - len(html_caps),
        "bytes_html": raw_bytes,
        "tokens_html_crudo_aprox": raw_bytes // 4,
    }
    emit("extraer", "done", f"{len(html_caps)} páginas HTML en Bronze", manifest["extraer"])

    # 3 · Limpiar (Silver) ------------------------------------------------
    emit("limpiar", "start", "Extrayendo el cuerpo editorial a Markdown", {})
    silver: list[SilverPage] = []
    for i, cap in enumerate(html_caps, start=1):
        html = (paths.root / cap.html_path).read_text(encoding="utf-8", errors="replace")
        silver.append(to_silver(cap, html, settings.scraper.min_chars))
        emit("limpiar", "progress", cap.url, {"i": i, "n": len(html_caps)})
    paths.processed.mkdir(parents=True, exist_ok=True)
    with paths.silver_pages.open("w", encoding="utf-8") as f:
        for page in silver:
            f.write(page.model_dump_json() + "\n")
    manifest["limpiar"] = {
        "paginas_limpias": len(silver),
        "extractor": dict(Counter(p.extractor for p in silver)),
    }
    emit("limpiar", "done", f"{len(silver)} páginas en Silver", manifest["limpiar"])

    # 4 · Deduplicar ------------------------------------------------------
    emit("deduplicar", "start", "Quitando duplicados y boilerplate", {})
    deduped, drep = deduplicate(silver, min_chars=settings.scraper.min_chars)
    manifest["deduplicar"] = {
        "duplicados_exactos": len(drep.exact_duplicates),
        "casi_duplicados": len(drep.near_duplicates),
        "muy_cortas": len(drep.too_short),
        "bloques_boilerplate_eliminados": drep.boilerplate_removed,
        "ejemplos_boilerplate": drep.boilerplate_blocks[:10],
        "detalle_descartes": {
            "duplicados_exactos": drep.exact_duplicates,
            "casi_duplicados": [{"url": u, "igual_a": o, "jaccard": s} for u, o, s in drep.near_duplicates],
            "muy_cortas": drep.too_short,
        },
    }
    emit("deduplicar", "done", f"{len(deduped)} páginas únicas", manifest["deduplicar"])

    # 5 · Enriquecer (Gold) -----------------------------------------------
    emit("enriquecer", "start", "Escribiendo Markdown con frontmatter en data/gold/", {})
    post_urls = report.post_urls or {p.url for p in deduped if p.fecha_publicacion and report.method != "sitemap"}
    docs = [to_gold(p, settings.scraper.company, post_urls) for p in deduped]
    write_gold(docs, paths, settings.scraper.company)
    chunks = chunk_documents(docs)
    write_chunks(chunks, paths)
    tokens_gold = sum(d.tokens for d in docs)
    by_section = Counter(d.seccion for d in docs)
    tokens_section: Counter[str] = Counter()
    for d in docs:
        tokens_section[d.seccion] += d.tokens
    manifest["enriquecer"] = {
        "documentos": len(docs),
        "tokens_totales": tokens_gold,
        "docs_por_seccion": dict(by_section.most_common()),
        "tokens_por_seccion": dict(tokens_section.most_common()),
        "noticias": sum(1 for d in docs if d.tipo == "noticia"),
        "paginas": sum(1 for d in docs if d.tipo == "pagina"),
        "chunks": len(chunks),
        "chunk_size_chars": CHUNK_SIZE,
        "chunk_overlap_chars": CHUNK_OVERLAP,
        "tokens_promedio_chunk": round(sum(c.tokens for c in chunks) / len(chunks)) if chunks else 0,
    }
    raw_tokens = manifest["extraer"]["tokens_html_crudo_aprox"]
    manifest["ahorro_tokens_pct"] = round(100 * (1 - tokens_gold / raw_tokens), 1) if raw_tokens else None
    manifest["duracion_s"] = round(time.monotonic() - t0, 1)
    paths.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    emit(
        "enriquecer",
        "done",
        f"{len(docs)} documentos · {len(chunks)} chunks · {tokens_gold:,} tokens",
        manifest["enriquecer"],
    )
    return manifest

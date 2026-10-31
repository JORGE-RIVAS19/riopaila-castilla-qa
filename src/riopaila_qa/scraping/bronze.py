"""Etapa 2 · Extraer (Bronze): guarda el HTML tal cual llegó y un JSONL de captura.

Contrato de la capa: nunca se edita a mano. Si el limpiador cambia, Silver y
Gold se regeneran desde aquí sin volver a la web.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path

from riopaila_qa.config import Paths
from riopaila_qa.scraping.fetcher import PoliteFetcher
from riopaila_qa.scraping.models import Capture
from riopaila_qa.textutils import sha256, short_hash

ProgressFn = Callable[[int, int, str], None]


def now_iso() -> str:
    """Fecha y hora actual en UTC, formato ISO-8601 sin microsegundos."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def load_captures(paths: Paths) -> dict[str, Capture]:
    """Lee el JSONL de captura (la última captura de cada URL gana)."""
    captures: dict[str, Capture] = {}
    if paths.captures.exists():
        for line in paths.captures.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cap = Capture.model_validate_json(line)
                captures[cap.url] = cap
    return captures


def html_file_for(paths: Paths, url: str) -> Path:
    """Ruta determinística del HTML crudo de una URL."""
    return paths.raw_html / f"{short_hash(url, 16)}.html"


def capture_urls(
    urls: Iterable[str],
    fetcher: PoliteFetcher,
    paths: Paths,
    refresh: bool = False,
    on_progress: ProgressFn | None = None,
    max_downloads: int | None = None,
) -> list[Capture]:
    """Descarga cada URL (o reutiliza la caché Bronze) y registra la captura.

    ``max_downloads`` limita las peticiones nuevas de esta corrida; las demás
    URLs se toman de la caché si existen. Así una demo en vivo con pocas
    páginas no destruye el corpus completo capturado antes.
    """
    urls = list(urls)
    paths.raw_html.mkdir(parents=True, exist_ok=True)
    previous = load_captures(paths)
    results: list[Capture] = []
    downloads = 0

    with paths.captures.open("a", encoding="utf-8") as log:
        for i, url in enumerate(urls, start=1):
            cached = previous.get(url)
            usable = bool(
                cached and cached.status == 200 and cached.html_path and (paths.root / cached.html_path).exists()
            )
            budget_left = max_downloads is None or downloads < max_downloads
            if usable and (not refresh or not budget_left):
                results.append(cached.model_copy(update={"from_cache": True}))
                if on_progress:
                    on_progress(i, len(urls), f"caché · {url}")
                continue
            if not budget_left:
                continue  # sin caché y sin cupo de descargas en esta corrida
            downloads += 1

            res = fetcher.get(url)
            html_rel = None
            if res.ok and res.content:
                target = html_file_for(paths, url)
                target.write_bytes(res.content)
                html_rel = str(target.relative_to(paths.root))
            cap = Capture(
                url=url,
                final_url=res.final_url,
                fecha_captura=now_iso(),
                status=res.status,
                content_type=res.content_type,
                bytes=len(res.content),
                hash=sha256(res.content) if res.content else "",
                html_path=html_rel,
                error=res.error,
            )
            log.write(json.dumps(cap.model_dump(), ensure_ascii=False) + "\n")
            results.append(cap)
            if on_progress:
                on_progress(i, len(urls), f"HTTP {res.status} · {url}")
    return results

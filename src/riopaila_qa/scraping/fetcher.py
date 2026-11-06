"""Cliente HTTP cortés: User-Agent identificable, timeout, rate limit y reintentos."""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from riopaila_qa.config import ScraperSettings


@dataclass
class FetchResult:
    """Respuesta mínima que necesita la capa Bronze."""

    url: str
    final_url: str
    status: int
    content_type: str
    content: bytes
    elapsed_s: float
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class PoliteFetcher:
    """Descarga URLs respetando una pausa mínima entre peticiones al mismo host.

    La pausa es ``max(delay configurado, Crawl-delay de robots.txt)``. Nunca
    se lanzan peticiones en paralelo: el sitio de la empresa no debe notar
    el scraper.
    """

    def __init__(self, settings: ScraperSettings, crawl_delay: float | None = None) -> None:
        self.settings = settings
        self.delay = max(settings.delay_s, crawl_delay or 0.0)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": settings.user_agent,
                "Accept-Language": "es-CO,es;q=0.9",
            }
        )
        self._last_request = 0.0
        self.requests_made = 0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if self._last_request and elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def get(self, url: str, retries: int = 2) -> FetchResult:
        """GET con reintentos exponenciales ante errores de red o 5xx."""
        last_error = "desconocido"
        for attempt in range(retries + 1):
            self._wait()
            start = time.monotonic()
            self._last_request = start
            self.requests_made += 1
            try:
                resp = self.session.get(url, timeout=self.settings.timeout_s)
                result = FetchResult(
                    url=url,
                    final_url=resp.url,
                    status=resp.status_code,
                    content_type=resp.headers.get("Content-Type", ""),
                    content=resp.content,
                    elapsed_s=round(time.monotonic() - start, 3),
                )
                if resp.status_code < 500:
                    return result
                last_error = f"HTTP {resp.status_code}"
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(min(8.0, 2**attempt))
        return FetchResult(
            url=url,
            final_url=url,
            status=0,
            content_type="",
            content=b"",
            elapsed_s=0.0,
            error=last_error,
        )

"""Configuración central del proyecto.

Todas las rutas y parámetros se leen de variables de entorno (archivo ``.env``,
que nunca se versiona) con valores por defecto seguros. Así el mismo código
corre en el equipo de cualquier integrante sin tocar el fuente.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    """Lee una variable de entorno y devuelve ``default`` si está vacía."""
    value = os.getenv(name, "").strip()
    return value or default


@dataclass(frozen=True)
class Paths:
    """Rutas de la arquitectura Medallion (Bronze → Silver → Gold)."""

    root: Path = ROOT_DIR
    raw: Path = ROOT_DIR / "data" / "raw"
    processed: Path = ROOT_DIR / "data" / "processed"
    gold: Path = ROOT_DIR / "data" / "gold"
    eval_dir: Path = ROOT_DIR / "data" / "eval"
    prompts: Path = ROOT_DIR / "prompts"

    @property
    def raw_html(self) -> Path:
        return self.raw / "html"

    @property
    def captures(self) -> Path:
        return self.raw / "captures.jsonl"

    @property
    def silver_pages(self) -> Path:
        return self.processed / "pages.jsonl"

    @property
    def gold_pages(self) -> Path:
        return self.gold / "pages"

    @property
    def corpus(self) -> Path:
        return self.gold / "corpus.jsonl"

    @property
    def chunks(self) -> Path:
        return self.gold / "chunks.jsonl"

    @property
    def knowledge_base(self) -> Path:
        return self.gold / "knowledge_base.md"

    @property
    def manifest(self) -> Path:
        return self.gold / "manifest.json"


@dataclass(frozen=True)
class ScraperSettings:
    """Parámetros de cortesía y alcance del scraper."""

    base_url: str = _env("SCRAPER_BASE_URL", "https://www.riopaila-castilla.com")
    company: str = _env("COMPANY_NAME", "Riopaila Castilla S.A.")
    user_agent: str = _env(
        "SCRAPER_USER_AGENT",
        "TAAML-UAO-Grupo3-bot/1.0 (proyecto academico Maestria IA UAO; uso no comercial)",
    )
    timeout_s: float = float(_env("SCRAPER_TIMEOUT", "15"))
    delay_s: float = float(_env("SCRAPER_DELAY", "1.0"))
    max_pages: int = int(_env("SCRAPER_MAX_PAGES", "400"))
    min_chars: int = int(_env("SCRAPER_MIN_CHARS", "200"))
    # Sub-sitemaps de WordPress que SÍ aportan contenido editorial.
    # Se excluye a propósito wp-sitemap-users (datos personales, Ley 1581)
    # y las taxonomías (páginas de listado que duplican contenido).
    allowed_sitemaps: tuple[str, ...] = ("posts-page", "posts-post", "posts-portfolio")


@dataclass(frozen=True)
class LLMSettings:
    """Proveedor y parámetros de muestreo del LLM (régimen Q1 de la Clase 4)."""

    provider: str = _env("LLM_PROVIDER", "ollama")
    ollama_model: str = _env("OLLAMA_MODEL", "llama3.2:3b")
    ollama_base_url: str = _env("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_num_ctx: int = int(_env("OLLAMA_NUM_CTX", "16384"))
    openai_model: str = _env("OPENAI_MODEL", "gpt-4o-mini")
    gemini_model: str = _env("GEMINI_MODEL", "gemini-2.5-flash")
    temperature: float = float(_env("LLM_TEMPERATURE", "0.0"))
    top_p: float = float(_env("LLM_TOP_P", "0.1"))
    max_context_tokens: int = int(_env("MAX_CONTEXT_TOKENS", "12000"))


@dataclass(frozen=True)
class Settings:
    """Agrupa toda la configuración del proyecto."""

    paths: Paths = field(default_factory=Paths)
    scraper: ScraperSettings = field(default_factory=ScraperSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)


def get_settings() -> Settings:
    """Devuelve la configuración leída del entorno al importar el módulo."""
    return Settings()

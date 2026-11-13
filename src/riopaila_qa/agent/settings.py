"""Configuración del agente del Módulo 2 (todo se lee del ``.env``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from riopaila_qa.config import ROOT_DIR, _env


def _flag(name: str, default: str = "0") -> bool:
    return _env(name, default).lower() in {"1", "true", "si", "sí", "yes"}


@dataclass(frozen=True)
class AgentSettings:
    """Rutas, modelos y parámetros del agente conversacional."""

    # --- LLM del agente -------------------------------------------------------
    provider: str = _env("LLM_PROVIDER", "gemini")
    router_provider: str = _env("ROUTER_PROVIDER", "")  # vacío = el mismo del agente
    router_mode: str = _env("ROUTER_MODE", "hibrido")  # reglas | llm | hibrido

    # --- Embeddings (Clase 6) -------------------------------------------------
    embed_provider: str = _env("EMBED_PROVIDER", "ollama")  # ollama | gemini | fake
    ollama_embed_model: str = _env("OLLAMA_EMBED_MODEL", "nomic-embed-text-v2-moe")
    gemini_embed_model: str = _env("GEMINI_EMBED_MODEL", "gemini-embedding-001")
    embed_dims: int = int(_env("EMBED_DIMS", "768"))  # Matryoshka: Gemini admite 768/1536/3072

    # --- Qdrant (Clase 7) -----------------------------------------------------
    qdrant_url: str = _env("QDRANT_URL", "")  # vacío = modo embebido en disco (sin Docker)
    qdrant_path: Path = Path(_env("QDRANT_PATH", str(ROOT_DIR / "data" / "qdrant")))
    collection_alias: str = _env("QDRANT_COLLECTION", "riopaila_chunks")
    top_k: int = int(_env("RAG_TOP_K", "5"))
    candidates: int = int(_env("RAG_CANDIDATES", "20"))
    include_adversarial: bool = _flag("RAG_INCLUDE_ADVERSARIAL", "1")

    # --- Memoria (Clase 6) ----------------------------------------------------
    memory_dir: Path = Path(_env("MEMORY_DIR", str(ROOT_DIR / "data" / "memory")))
    summary_trigger_tokens: int = int(_env("SUMMARY_TRIGGER_TOKENS", "6000"))
    summary_keep_messages: int = int(_env("SUMMARY_KEEP_MESSAGES", "8"))
    direct_history_tokens: int = int(_env("DIRECT_HISTORY_TOKENS", "2000"))

    # --- Datos estructurados --------------------------------------------------
    structured_csv: Path = Path(
        _env("STRUCTURED_CSV", str(ROOT_DIR / "data" / "structured" / "indicadores_riopaila.csv"))
    )
    adversarial_dir: Path = Path(_env("ADVERSARIAL_DIR", str(ROOT_DIR / "data" / "adversarial")))

    # --- Observabilidad -------------------------------------------------------
    trace_dir: Path = Path(_env("TRACE_DIR", str(ROOT_DIR / "logs")))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in _env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        )
    )

    @property
    def checkpoints_db(self) -> Path:
        return self.memory_dir / "checkpoints.sqlite"

    @property
    def store_db(self) -> Path:
        return self.memory_dir / "store.sqlite"


def get_agent_settings() -> AgentSettings:
    """Configuración del agente leída del entorno."""
    return AgentSettings()

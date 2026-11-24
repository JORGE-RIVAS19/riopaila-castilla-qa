"""Configuración del taller (todo desde el ``.env``; rutas por defecto dentro de ``data/``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from riopaila_qa.config import ROOT_DIR, _env

MUESTRA_DIR = ROOT_DIR / "data" / "taller" / "muestra"


@dataclass(frozen=True)
class TallerSettings:
    """Rutas de datos del taller, medios generados y colección de manuales (se leen del entorno al crearla)."""

    db_path: Path = field(
        default_factory=lambda: Path(_env("TALLER_DB", str(ROOT_DIR / "data" / "taller" / "taller.duckdb")))
    )
    novedades_db: Path = field(
        default_factory=lambda: Path(
            _env("TALLER_NOVEDADES_DB", str(ROOT_DIR / "data" / "taller" / "novedades.sqlite"))
        )
    )
    manuales_dir: Path = field(default_factory=lambda: Path(_env("MANUALES_DIR", str(ROOT_DIR / "data" / "manuales"))))
    media_dir: Path = field(default_factory=lambda: Path(_env("MEDIA_DIR", str(ROOT_DIR / "data" / "media"))))
    media_base_url: str = field(default_factory=lambda: _env("MEDIA_BASE_URL", ""))
    manuales_collection: str = field(default_factory=lambda: _env("QDRANT_MANUALES", "manuales_taller"))
    zona_horaria: str = field(default_factory=lambda: _env("ZONA_HORARIA", "America/Bogota"))
    # Roles por usuario (web: nombre; WhatsApp: número E.164). Ej.: "jorge=supervisor,+573001112233=tecnico"
    roles: str = field(default_factory=lambda: _env("TALLER_ROLES", ""))
    rol_defecto: str = field(default_factory=lambda: _env("TALLER_ROL_DEFECTO", "invitado"))
    vision_provider: str = field(default_factory=lambda: _env("VISION_PROVIDER", "gemini"))

    def rol_de(self, user_id: str) -> str:
        """El rol lo decide el servidor (nunca el cliente): lista blanca del .env."""
        tabla = {
            k.lstrip("+").lower(): v
            for k, v in (p.split("=", 1) for p in self.roles.replace(" ", "").split(",") if "=" in p)
        }
        rol = tabla.get(user_id.strip().lstrip("+").lower(), self.rol_defecto)
        return rol if rol in {"supervisor", "tecnico", "invitado"} else "invitado"

    @property
    def paginas_jsonl(self) -> Path:
        return self.manuales_dir / "paginas.jsonl"


def get_taller_settings() -> TallerSettings:
    return TallerSettings()

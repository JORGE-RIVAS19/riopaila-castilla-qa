"""CLI reproducible del pipeline de scraping.

Uso:
    uv run python scripts/scrape_empresa.py                 # corrida completa en línea
    uv run python scripts/scrape_empresa.py --refresh --max-pages 5  # demo: re-descarga 5 páginas
    uv run python scripts/scrape_empresa.py --offline       # regenera Silver/Gold desde Bronze
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from riopaila_qa.config import get_settings
from riopaila_qa.scraping import run_pipeline

ICONS = {"descubrir": "🗺️ ", "extraer": "🌐", "limpiar": "🧹", "deduplicar": "♻️ ", "enriquecer": "🥇"}


def _printer(stage: str, status: str, message: str, data: dict[str, Any]) -> None:
    icon = ICONS.get(stage, "•")
    if status == "start":
        print(f"\n{icon} [{stage.upper()}] {message}")
    elif status == "progress":
        i, n = data.get("i"), data.get("n")
        if i and n and (i == n or i % 10 == 0 or stage == "extraer"):
            print(f"   {i:>4}/{n:<4} {message}")
    else:
        print(f"   ✅ {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scraper Medallion de Riopaila Castilla")
    parser.add_argument(
        "--max-pages", type=int, default=None, help="tope de descargas nuevas (el resto sale de la caché Bronze)"
    )
    parser.add_argument("--offline", action="store_true", help="reprocesa desde data/raw sin ir a la web")
    parser.add_argument("--refresh", action="store_true", help="ignora la caché Bronze y descarga de nuevo")
    args = parser.parse_args()

    settings = get_settings()
    print(f"Empresa: {settings.scraper.company} · Sitio: {settings.scraper.base_url}")
    print(f"User-Agent: {settings.scraper.user_agent}")
    try:
        manifest = run_pipeline(
            settings, max_pages=args.max_pages, offline=args.offline, refresh=args.refresh, on_event=_printer
        )
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        return 1
    gold = manifest["enriquecer"]
    print("\n📊 Resumen del corpus")
    print(f"   Documentos Gold : {gold['documentos']} ({gold['paginas']} páginas, {gold['noticias']} noticias)")
    print(f"   Tokens Gold     : {gold['tokens_totales']:,}")
    print(f"   Ahorro vs HTML  : {manifest['ahorro_tokens_pct']} %")
    print(f"   Duración        : {manifest['duracion_s']} s")
    print(f"   Salidas         : {settings.paths.gold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

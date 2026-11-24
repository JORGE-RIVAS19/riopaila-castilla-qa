"""Construye la base del taller (DuckDB) desde los exportes de SAP, o la muestra anonimizada.

Servidor (datos reales, nunca se versionan):
    uv run python scripts/build_taller.py --equipos equipos.xlsx --historial historial.xlsx --materiales materiales.xlsx

Repositorio / CI (muestra anonimizada ya versionada en data/taller/muestra/*.csv):
    uv run python scripts/build_taller.py --muestra

Regenerar la muestra desde la base real:
    uv run python scripts/build_taller.py --regenerar-muestra data/taller/taller.duckdb
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from riopaila_qa.taller.base import cargar_csv, construir_base
from riopaila_qa.taller.config import MUESTRA_DIR, get_taller_settings
from riopaila_qa.taller.muestra import generar_muestra


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--equipos", type=Path)
    p.add_argument("--historial", type=Path)
    p.add_argument("--materiales", type=Path)
    p.add_argument("--hoja-materiales", default="RawData")
    p.add_argument("--destino", type=Path, default=get_taller_settings().db_path)
    p.add_argument("--muestra", action="store_true", help="Construir desde data/taller/muestra/*.csv")
    p.add_argument("--regenerar-muestra", type=Path, metavar="BASE_REAL")
    a = p.parse_args()
    t = time.perf_counter()
    if a.regenerar_muestra:
        print(generar_muestra(a.regenerar_muestra, MUESTRA_DIR))
    elif a.muestra:
        destino = MUESTRA_DIR / "taller_muestra.duckdb"
        print(
            cargar_csv(
                MUESTRA_DIR / "equipos.csv", MUESTRA_DIR / "materiales.csv", MUESTRA_DIR / "consumos.csv", destino
            )
        )
        print(f"→ {destino}")
    else:
        if not (a.equipos and a.historial and a.materiales):
            p.error("faltan --equipos, --historial y --materiales (o usa --muestra)")
        print(construir_base(a.equipos, a.historial, a.materiales, a.destino, a.hoja_materiales))
        print(f"→ {a.destino}")
    print(f"listo en {time.perf_counter() - t:.1f} s")


if __name__ == "__main__":
    main()

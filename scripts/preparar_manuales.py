"""Copia los PDF de manuales con su nombre estable (``<id>.pdf``) y extrae sus páginas (OCR en los escaneados).

Uso (en el servidor):  uv run python scripts/preparar_manuales.py ~/carga data/manuales
Los PDF tienen derechos de autor: quedan en el servidor y nunca en Git (``data/manuales/`` está en .gitignore).
"""

from __future__ import annotations

import argparse
import re
import shutil
import time
import unicodedata
from pathlib import Path

from riopaila_qa.taller.manuales import CATALOGO, extraer_paginas, guardar_paginas, resumen_catalogo

# Patrón (sobre el nombre original normalizado) → id del catálogo. El primero que coincide gana.
PATRONES: list[tuple[str, str]] = [
    (r"PARTES.*ALZADORA.*2254|PC9617", "jd2254-partes"),
    (r"OPERADOR.*ALZADORA|OMCXT10828", "jd2254-operador"),
    (r"OPERADOR.*PUMA ?165", "puma165-operador"),
    (r"PUMA.?165.?180.?195.?210", "puma165-210-operador-pt"),
    (r"PUMA.?200.?165", "puma190-230-servicio"),
    (r"CALIBRACION", "puma-calibracion-codigos"),
    (r"TECNICO.*6165", "jd6165j-tecnico"),
    (r"GAME.*77", "game77atx-partes"),
    (r"MANUAL.?ELECTRICO", "kenworth-electrico"),
    (r"BIT.?1014", "kw-bit-1014-cecu"),
    (r"FUSIBLES", "kw-fusibles"),
    (r"PLANO.?CECU", "kw-cecu-plano"),
    (r"C97.?1077", "kw-c97-1077"),
    *[(rf"P94.?{n}", f"kw-p94-{n}") for n in ("1476", "1456", "1585", "1896", "1458", "1398", "1389", "1383", "1469")],
]


def _norm(nombre: str) -> str:
    s = unicodedata.normalize("NFKD", nombre.upper())
    return re.sub(r"[^A-Z0-9]+", "_", "".join(c for c in s if not unicodedata.combining(c)))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("origen", type=Path)
    p.add_argument("destino", type=Path)
    a = p.parse_args()
    a.destino.mkdir(parents=True, exist_ok=True)
    ids = {m.id for m in CATALOGO}
    for pdf in sorted(a.origen.rglob("*.pdf")) + sorted(a.origen.rglob("*.PDF")):
        if pdf.stem in ids:
            mid = pdf.stem
        else:
            mid = next((i for pat, i in PATRONES if re.search(pat, _norm(pdf.name).replace("_", " "))), None)
        if not mid:
            print(f"  ? sin catálogo: {pdf.name} (se ignora)")
            continue
        destino = a.destino / f"{mid}.pdf"
        if not destino.exists():
            shutil.copy2(pdf, destino)
        print(f"  ✓ {pdf.name} → {destino.name}")
    t = time.perf_counter()
    paginas = extraer_paginas(a.destino, on_progress=lambda m, n: print(f"  · {m}: {n} páginas", flush=True))
    guardar_paginas(paginas, a.destino / "paginas.jsonl")
    faltan = [r["id"] for r in resumen_catalogo(paginas) if not r["paginas_indexadas"]]
    print(f"{len(paginas)} páginas en {time.perf_counter() - t:.0f} s. Manuales sin cargar: {faltan or 'ninguno'}")


if __name__ == "__main__":
    main()

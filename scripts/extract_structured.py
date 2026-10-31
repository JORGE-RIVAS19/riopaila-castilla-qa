"""Laboratorio de la Clase 4: JSONL verificable desde 3 páginas del corpus Gold.

Extrae una ficha con esquema Pydantic y temperatura 0. Si un dato no está en
la página, el campo queda vacío en lugar de inventarse.

Uso:
    uv run python scripts/extract_structured.py
    uv run python scripts/extract_structured.py --slugs somos-riopaila-castilla azucares energia
"""

from __future__ import annotations

import argparse
import json
import sys

from riopaila_qa.config import get_settings
from riopaila_qa.corpus import CorpusStore
from riopaila_qa.tasks import extract_ficha

DEFAULT_SLUGS = ["somos-riopaila-castilla", "azucares", "energia"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Extracción estructurada (Pydantic, T=0)")
    parser.add_argument("--slugs", nargs="+", default=DEFAULT_SLUGS, help="fragmento de la URL de cada página")
    args = parser.parse_args()
    settings = get_settings()
    store = CorpusStore(settings.paths)
    out = settings.paths.eval_dir / "ficha_empresa.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out.open("w", encoding="utf-8") as f:
        for slug in args.slugs:
            doc = next((d for d in store.docs if slug in d.url), None)
            if doc is None:
                print(f"⚠️  No hay documento Gold cuya URL contenga '{slug}'")
                continue
            ficha = extract_ficha(doc.markdown, settings.llm)
            record = {"url": doc.url, "titulo": doc.titulo, **ficha.model_dump()}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
            print(f"✅ {doc.url}\n{json.dumps(ficha.model_dump(), ensure_ascii=False, indent=2)}\n")
    print(f"{written} fichas validadas con Pydantic en {out}")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())

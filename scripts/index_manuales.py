"""Vectoriza las páginas de los manuales en Qdrant (colección versionada + alias ``manuales_taller``).

Uso (en el servidor, con el API detenido por el candado de Qdrant embebido):
    uv run python scripts/index_manuales.py
"""

from __future__ import annotations

import time

from riopaila_qa.agent.embeddings import get_embeddings
from riopaila_qa.agent.settings import get_agent_settings
from riopaila_qa.rag.index import close_clients, get_client
from riopaila_qa.taller.config import get_taller_settings
from riopaila_qa.taller.manuales import cargar_paginas, indexar


def main() -> None:
    s, t = get_agent_settings(), get_taller_settings()
    paginas = cargar_paginas(t.paginas_jsonl)
    if not paginas:
        raise SystemExit(f"No hay páginas en {t.paginas_jsonl}: corre primero scripts/preparar_manuales.py")
    emb, dims, nombre = get_embeddings(s)
    t0 = time.perf_counter()
    coleccion = indexar(
        paginas,
        emb,
        dims,
        get_client(s),
        t.manuales_collection,
        on_progress=lambda i, n: print(f"\r  {i}/{n} páginas", end="", flush=True),
    )
    print(
        f"\n{len(paginas)} páginas → {coleccion} (alias {t.manuales_collection}, {nombre}, {dims} dims) "
        f"en {time.perf_counter() - t0:.0f} s"
    )
    close_clients()


if __name__ == "__main__":
    main()

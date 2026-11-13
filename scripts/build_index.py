"""Indexación offline (load → clean → embed → store) del corpus Gold en Qdrant.

Uso::

    uv run python scripts/build_index.py                 # embeddings del .env (Ollama nomic por defecto)
    uv run python scripts/build_index.py --provider gemini
    uv run python scripts/build_index.py --rollback      # vuelve el alias a la colección anterior

Detén el backend antes de indexar: en modo embebido Qdrant bloquea la carpeta.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riopaila_qa.agent.embeddings import get_embeddings  # noqa: E402
from riopaila_qa.agent.settings import get_agent_settings  # noqa: E402
from riopaila_qa.config import Paths  # noqa: E402
from riopaila_qa.rag.documents import load_adversarial_chunks, load_corpus_chunks  # noqa: E402
from riopaila_qa.rag.index import build_index, close_clients, index_info, rollback  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Indexa los chunks Gold en Qdrant (blue/green)")
    ap.add_argument("--provider", choices=["ollama", "gemini", "fake"], help="Proveedor de embeddings")
    ap.add_argument("--sin-prueba-blindaje", action="store_true", help="No indexar el documento sintético del caso 5")
    ap.add_argument("--rollback", action="store_true", help="Apuntar el alias a la colección anterior")
    args = ap.parse_args()
    settings = get_agent_settings()

    if args.rollback:
        print(f"Alias {settings.collection_alias} → {rollback(settings)}")
        close_clients()
        return

    chunks, stats = load_corpus_chunks(Paths())
    print("Limpieza de chunks:", stats)
    if not args.sin_prueba_blindaje:
        adv = load_adversarial_chunks(settings.adversarial_dir)
        chunks += adv
        print(f"+ {len(adv)} documento(s) sintético(s) de prueba de blindaje (origen=sintetico)")

    embeddings, dims, model = get_embeddings(settings, args.provider)
    print(f"Embeddings: {model} · {dims} dimensiones · {len(chunks)} chunks")
    t0 = time.perf_counter()

    def progress(done: int, total: int) -> None:
        print(f"\r  vectorizando {done}/{total}  ({time.perf_counter() - t0:.0f} s)", end="", flush=True)

    report = build_index(chunks, embeddings, dims, model, settings, on_progress=progress)
    print()
    print(f"Colección nueva: {report.collection} ({report.points} puntos, modo {report.mode})")
    print(f"Alias {report.alias}: {report.previous or '(nuevo)'} → {report.collection}")
    if report.deleted:
        print("Colecciones antiguas borradas:", ", ".join(report.deleted))
    print("Estado:", index_info(settings))
    print(f"Listo en {time.perf_counter() - t0:.1f} s")
    close_clients()


if __name__ == "__main__":
    main()

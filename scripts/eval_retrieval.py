"""Evaluación del retrieval (criterio 4.2): recall@10, nDCG@10 y MRR con 28 consultas etiquetadas.

Compara tres configuraciones sobre el mismo índice: **densa** (Qdrant), **léxica**
(BM25 del M1) e **híbrida** (RRF). La relevancia es binaria a nivel de documento:
un fragmento cuenta si pertenece a una de las URLs etiquetadas en
``data/eval/retrieval_queries.jsonl``; los fragmentos repetidos de un mismo
documento solo cuentan la primera vez (no inflan la métrica).

Uso::

    uv run python scripts/eval_retrieval.py            # con los embeddings del .env
    uv run python scripts/eval_retrieval.py --k 10 --modos hibrida densa lexica
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riopaila_qa.agent.embeddings import get_embeddings  # noqa: E402
from riopaila_qa.agent.settings import get_agent_settings  # noqa: E402
from riopaila_qa.config import ROOT_DIR, Paths  # noqa: E402
from riopaila_qa.rag.documents import load_corpus_chunks  # noqa: E402
from riopaila_qa.rag.index import close_clients, index_info  # noqa: E402
from riopaila_qa.rag.retriever import HybridRetriever  # noqa: E402

QUERIES = ROOT_DIR / "data" / "eval" / "retrieval_queries.jsonl"
OUT_DIR = ROOT_DIR / "docs" / "evaluacion"


def is_relevant(url: str, relevant: list[str]) -> bool:
    return any(r in url for r in relevant)


def doc_ranking(urls: list[str]) -> list[str]:
    """Lista de documentos en orden, sin repetidos (primer fragmento de cada uno)."""
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def metrics(ranked_urls: list[str], relevant: list[str], k: int) -> dict:
    docs = doc_ranking(ranked_urls)[:k]
    gains = [1.0 if is_relevant(u, relevant) else 0.0 for u in docs]
    found = sum(gains)
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    first = next((i + 1 for i, g in enumerate(gains) if g), None)
    return {
        "recall": found / len(relevant),
        "ndcg": dcg / ideal if ideal else 0.0,
        "mrr": 1 / first if first else 0.0,
        "hit": 1.0 if found else 0.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="recall@k / nDCG@k del retrieval")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--modos", nargs="+", default=["densa", "lexica", "hibrida"])
    args = ap.parse_args()

    settings = get_agent_settings()
    info = index_info(settings)
    if not info.get("disponible"):
        raise SystemExit("No hay índice: ejecuta primero `uv run python scripts/build_index.py`.")
    embeddings, _, model = get_embeddings(settings)
    chunks, _ = load_corpus_chunks(Paths())
    retriever = HybridRetriever(chunks, embeddings, settings)
    queries = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]

    results: dict = {
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "k": args.k,
        "embeddings": model,
        "indice": info,
        "consultas": len(queries),
        "modos": {},
    }
    for mode in args.modos:
        rows, t0 = [], time.perf_counter()
        for q in queries:
            res = retriever.search(q["consulta"], k=args.k * 3, mode=mode, include_adversarial=False)
            m = metrics([h.chunk.url for h in res.hits], q["relevantes"], args.k)
            rows.append(
                {
                    "id": q["id"],
                    "consulta": q["consulta"],
                    **{key: round(v, 4) for key, v in m.items()},
                    "top3": doc_ranking([h.chunk.url for h in res.hits])[:3],
                }
            )
        n = len(rows)
        results["modos"][mode] = {
            f"recall@{args.k}": round(sum(r["recall"] for r in rows) / n, 4),
            f"ndcg@{args.k}": round(sum(r["ndcg"] for r in rows) / n, 4),
            "mrr": round(sum(r["mrr"] for r in rows) / n, 4),
            f"hit@{args.k}": round(sum(r["hit"] for r in rows) / n, 4),
            "latencia_media_ms": round((time.perf_counter() - t0) * 1000 / n, 1),
            "detalle": rows,
        }
        s = results["modos"][mode]
        print(
            f"{mode:8}  recall@{args.k}={s[f'recall@{args.k}']:.3f}  nDCG@{args.k}={s[f'ndcg@{args.k}']:.3f}  "
            f"MRR={s['mrr']:.3f}  hit@{args.k}={s[f'hit@{args.k}']:.3f}  ({s['latencia_media_ms']} ms/consulta)"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "retrieval_latest.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# Evaluación del retrieval · {results['fecha']}",
        "",
        f"Embeddings: `{model}` · índice `{info.get('coleccion')}` ({info.get('modo')}) · "
        f"{len(queries)} consultas etiquetadas · relevancia binaria por documento.",
        "",
        f"| Modo | recall@{args.k} | nDCG@{args.k} | MRR | hit@{args.k} | ms/consulta |",
        "|---|---|---|---|---|---|",
    ]
    for mode, s in results["modos"].items():
        lines.append(
            f"| {mode} | {s[f'recall@{args.k}']:.3f} | {s[f'ndcg@{args.k}']:.3f} | {s['mrr']:.3f} | "
            f"{s[f'hit@{args.k}']:.3f} | {s['latencia_media_ms']} |"
        )
    lines += ["", "## Detalle por consulta (modo híbrido)" if "hibrida" in results["modos"] else "", ""]
    if "hibrida" in results["modos"]:
        lines += ["| id | consulta | recall | nDCG | primer documento |", "|---|---|---|---|---|"]
        for r in results["modos"]["hibrida"]["detalle"]:
            top = r["top3"][0].replace("https://www.riopaila-castilla.com", "") if r["top3"] else "—"
            lines.append(f"| {r['id']} | {r['consulta']} | {r['recall']:.2f} | {r['ndcg']:.2f} | `{top}` |")
    (OUT_DIR / "retrieval_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Guardado en {OUT_DIR / 'retrieval_latest.md'}")
    close_clients()


if __name__ == "__main__":
    main()

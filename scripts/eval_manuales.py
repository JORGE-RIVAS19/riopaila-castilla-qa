"""Evaluación del retrieval de manuales (ítem 2.3): recall@10, nDCG@10, MRR y hit@10 con 25 consultas.

Relevancia por patrón (``data/eval/manuales_qrels.jsonl``): una página es relevante si es del manual esperado y su
texto cumple el patrón. Así el gold es reproducible y auditable. Compara cuatro modos para medir el aporte del
glosario español→inglés/portugués y de la búsqueda densa:

    uv run python scripts/eval_manuales.py            # en el servidor (con Qdrant + embeddings reales)
    uv run python scripts/eval_manuales.py --solo-lexica
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from datetime import datetime

from riopaila_qa.config import ROOT_DIR
from riopaila_qa.taller.config import get_taller_settings
from riopaila_qa.taller.manuales import BuscadorManuales, cargar_paginas

QRELS = ROOT_DIR / "data" / "eval" / "manuales_qrels.jsonl"
SALIDA = ROOT_DIR / "docs" / "evaluacion"


def metricas(ranking: list[str], relevantes: set[str], k: int) -> dict:
    top = ranking[:k]
    gains = [1.0 if pid in relevantes else 0.0 for pid in top]
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(relevantes), k)))
    primero = next((i + 1 for i, g in enumerate(gains) if g), None)
    return {
        "recall": sum(gains) / min(len(relevantes), k) if relevantes else 0.0,
        "ndcg": sum(g / math.log2(i + 2) for i, g in enumerate(gains)) / ideal if ideal else 0.0,
        "mrr": 1 / primero if primero else 0.0,
        "hit": 1.0 if primero else 0.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--solo-lexica", action="store_true", help="Sin Qdrant (p. ej. en CI o en un portátil)")
    a = ap.parse_args()
    t = get_taller_settings()
    paginas = cargar_paginas(t.paginas_jsonl)
    if not paginas:
        raise SystemExit(f"No hay páginas en {t.paginas_jsonl}")
    emb = client = None
    modos = ["lexica_sin_glosario", "lexica"]
    if not a.solo_lexica:
        from riopaila_qa.agent.embeddings import get_embeddings
        from riopaila_qa.agent.settings import get_agent_settings
        from riopaila_qa.rag.index import get_client

        s = get_agent_settings()
        emb, _, _ = get_embeddings(s)
        client = get_client(s)
        modos += ["densa", "hibrida"]
    buscador = BuscadorManuales(paginas, emb, client, t.manuales_collection)
    consultas = [json.loads(linea) for linea in QRELS.read_text(encoding="utf-8").splitlines() if linea.strip()]
    filas, resumen = [], {}
    for modo in modos:
        acumulado = {"recall": 0.0, "ndcg": 0.0, "mrr": 0.0, "hit": 0.0}
        t0 = time.perf_counter()
        for q in consultas:
            rel = {
                p.id
                for p in paginas
                if p.manual_id == q["manual_id"] and re.search(q["patron"], p.texto, re.IGNORECASE | re.DOTALL)
            }
            res = buscador.buscar(q["consulta"], q.get("modelo"), None, k=a.k, candidatos=max(30, a.k), modo=modo)
            ranking = [f"{r.manual_id}:{r.pagina}" for r in res]
            m = metricas(ranking, rel, a.k)
            for key in acumulado:
                acumulado[key] += m[key]
            filas.append(
                {
                    "modo": modo,
                    "id": q["id"],
                    "consulta": q["consulta"],
                    "relevantes": len(rel),
                    **m,
                    "primero": ranking[0] if ranking else None,
                }
            )
        n = len(consultas)
        resumen[modo] = {f"{k}@{a.k}" if k != "mrr" else k: round(v / n, 4) for k, v in acumulado.items()}
        resumen[modo]["ms_consulta"] = round((time.perf_counter() - t0) * 1000 / n, 1)
        print(f"{modo:20} " + "  ".join(f"{k}={v}" for k, v in resumen[modo].items()))
    SALIDA.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    datos = {
        "fecha": marca,
        "k": a.k,
        "consultas": len(consultas),
        "paginas": len(paginas),
        "resumen": resumen,
        "detalle": filas,
    }
    (SALIDA / "manuales_latest.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    lineas = [
        f"# Retrieval de manuales · {marca}",
        "",
        f"{len(consultas)} consultas · {len(paginas)} páginas · k={a.k}",
        "",
        f"| Modo | recall@{a.k} | nDCG@{a.k} | MRR | hit@{a.k} | ms/consulta |",
        "|---|---|---|---|---|---|",
    ]
    for modo, r in resumen.items():
        lineas.append(
            f"| {modo} | {r[f'recall@{a.k}']:.3f} | {r[f'ndcg@{a.k}']:.3f} | {r['mrr']:.3f} | "
            f"{r[f'hit@{a.k}']:.3f} | {r['ms_consulta']} |"
        )
    (SALIDA / f"manuales_{marca}.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

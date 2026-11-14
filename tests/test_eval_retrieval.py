"""Métricas del retrieval (recall@k, nDCG@k, MRR) y el set de consultas etiquetadas."""

from __future__ import annotations

import importlib.util
import json
import math

from riopaila_qa.config import ROOT_DIR

spec = importlib.util.spec_from_file_location("eval_retrieval", ROOT_DIR / "scripts" / "eval_retrieval.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def test_metricas_con_ejemplo_a_mano():
    ranked = ["https://x/a/", "https://x/b/", "https://x/a/", "https://x/c/"]
    m = ev.metrics(ranked, ["/b/", "/c/"], k=10)
    assert m["recall"] == 1.0 and m["mrr"] == 0.5
    ideal = 1 + 1 / math.log2(3)
    assert math.isclose(m["ndcg"], (1 / math.log2(3) + 1 / math.log2(4)) / ideal)


def test_set_de_consultas_etiquetadas():
    rows = [json.loads(line) for line in (ROOT_DIR / "data/eval/retrieval_queries.jsonl").open(encoding="utf-8")]
    assert 20 <= len(rows) <= 30 and len({r["id"] for r in rows}) == len(rows)
    urls = [json.loads(line)["url"] for line in (ROOT_DIR / "data/gold/corpus.jsonl").open(encoding="utf-8")]
    for r in rows:
        for rel in r["relevantes"]:
            assert sum(rel in u for u in urls) == 1, f"{r['id']}: {rel} debe identificar un único documento"

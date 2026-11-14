"""El CSV de indicadores es trazable: cada cifra viene de una noticia del corpus Gold."""

from __future__ import annotations

import csv
import json

from riopaila_qa.config import ROOT_DIR

CSV = ROOT_DIR / "data" / "structured" / "indicadores_riopaila.csv"
COLUMNS = [
    "id",
    "indicador",
    "categoria",
    "anio",
    "periodo",
    "valor",
    "unidad",
    "calificador",
    "descripcion",
    "fuente_url",
]


def _rows() -> list[dict]:
    with CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_columnas():
    with CSV.open(encoding="utf-8") as f:
        assert next(csv.reader(f)) == COLUMNS


def test_ids_unicos_y_valores_numericos():
    rows = _rows()
    assert len(rows) >= 30 and len({r["id"] for r in rows}) == len(rows)
    assert all(float(r["valor"]) > 0 for r in rows)
    assert {r["calificador"] for r in rows} <= {"exacto", "mas_de", "cerca_de"}


def test_fuentes_en_el_corpus():
    corpus = {json.loads(line)["url"] for line in (ROOT_DIR / "data/gold/corpus.jsonl").open(encoding="utf-8")}
    assert all(r["fuente_url"] in corpus for r in _rows()), "cada cifra debe venir de una noticia del corpus"

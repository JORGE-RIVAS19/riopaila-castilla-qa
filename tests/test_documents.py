"""Unidades del RAG: limpieza de plantilla en los chunks Gold y documento sintético marcado."""

from __future__ import annotations

from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.config import Paths
from riopaila_qa.rag.documents import boilerplate_lines, clean_text, load_adversarial_chunks, load_corpus_chunks


def test_limpieza_quita_panel_de_accesibilidad():
    chunks, stats = load_corpus_chunks(Paths())
    assert stats["chunks_indexables"] > 500 and stats["lineas_plantilla"] > 0
    assert not any("modo de ceguera" in c.texto.lower() for c in chunks)


def test_linea_repetida_en_muchos_documentos_es_plantilla():
    chunks = [{"doc_id": str(i), "texto": f"Contenido único {i}\nPie de página de la empresa"} for i in range(6)]
    boiler = boilerplate_lines(chunks)
    assert boiler == {"pie de página de la empresa"}
    assert clean_text(chunks[0]["texto"], boiler) == "Contenido único 0"


def test_anio_de_la_noticia():
    chunks, _ = load_corpus_chunks(Paths())
    years = {c.anio for c in chunks if "bonos-de-carbono" in c.url}
    assert years == {2025}


def test_documento_sintetico_marcado():
    adv = load_adversarial_chunks(AgentSettings().adversarial_dir)
    assert adv and all(c.origen == "sintetico" and c.seccion == "prueba_blindaje" for c in adv)

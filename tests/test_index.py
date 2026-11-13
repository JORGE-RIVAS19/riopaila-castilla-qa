"""Índice Qdrant embebido: colección versionada, payload, filtros y alias blue/green."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from riopaila_qa.agent.embeddings import get_embeddings
from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.config import Paths
from riopaila_qa.rag import index as rag_index
from riopaila_qa.rag.documents import load_corpus_chunks


@pytest.fixture()
def settings(tmp_path: Path):
    s = replace(AgentSettings(), embed_provider="fake", qdrant_url="", qdrant_path=tmp_path / "qdrant")
    yield s
    rag_index.close_clients()


def _build(settings: AgentSettings, n: int = 120, suffix: str = ""):
    chunks, _ = load_corpus_chunks(Paths())
    emb, dims, name = get_embeddings(settings)
    rag_index.build_index(chunks[:n], emb, dims, name + suffix, settings)
    return chunks[:n], emb


def test_indexa_con_payload(settings: AgentSettings):
    chunks, emb = _build(settings)
    info = rag_index.index_info(settings)
    assert info["disponible"] and info["puntos"] == len(chunks) and info["dimensiones"] == 256
    hits = rag_index.dense_search(emb.embed_query(chunks[0].texto), settings, 3)
    assert hits[0][0].chunk_id == chunks[0].chunk_id


def test_filtro_por_payload(settings: AgentSettings):
    chunks, emb = _build(settings)
    flt = rag_index.build_filter(seccion=chunks[0].seccion)
    hits = rag_index.dense_search(emb.embed_query("empresa"), settings, 10, flt)
    assert hits and all(c.seccion == chunks[0].seccion for c, _ in hits)


def test_alias_blue_green_y_rollback(settings: AgentSettings):
    _build(settings)
    first = rag_index.index_info(settings)["coleccion"]
    _build(settings, 40, "-v2")
    assert rag_index.index_info(settings)["coleccion"] != first
    assert rag_index.rollback(settings) == first
    assert rag_index.index_info(settings)["coleccion"] == first

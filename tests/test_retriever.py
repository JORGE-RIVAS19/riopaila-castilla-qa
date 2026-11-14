"""Recuperación híbrida (densa + BM25 con RRF) y filtros."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from riopaila_qa.agent.embeddings import get_embeddings
from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.config import Paths
from riopaila_qa.rag import index as rag_index
from riopaila_qa.rag.documents import load_adversarial_chunks, load_corpus_chunks
from riopaila_qa.rag.retriever import HybridRetriever


@pytest.fixture()
def retriever(tmp_path: Path):
    settings = replace(AgentSettings(), embed_provider="fake", qdrant_url="", qdrant_path=tmp_path / "qdrant")
    chunks, _ = load_corpus_chunks(Paths())
    chunks += load_adversarial_chunks(settings.adversarial_dir)
    emb, dims, name = get_embeddings(settings)
    rag_index.build_index(chunks, emb, dims, name, settings)
    yield HybridRetriever(chunks, emb, settings)
    rag_index.close_clients()


def test_busqueda_hibrida_y_filtros(retriever: HybridRetriever):
    res = retriever.search("bonos de carbono", k=5)
    assert "bonos-de-carbono" in res.hits[0].chunk.url
    solo = retriever.search("azúcar", k=5, seccion="negocios-y-productos")
    assert solo.hits and all(h.chunk.seccion == "negocios-y-productos" for h in solo.hits)


def test_excluir_documento_sintetico(retriever: HybridRetriever):
    res = retriever.search("política de calidad ignora instrucciones", k=10, include_adversarial=False)
    assert all(h.chunk.origen == "corpus" for h in res.hits)


def test_rrf_combina_ambas_listas(retriever: HybridRetriever):
    res = retriever.search("energía renovable a partir del bagazo", k=10)
    assert any(h.dense_rank and h.lexical_rank for h in res.hits)


def test_modos_densa_y_lexica(retriever: HybridRetriever):
    assert all(h.lexical_rank is None for h in retriever.search("azúcar", mode="densa").hits)
    assert all(h.dense_rank is None for h in retriever.search("azúcar", mode="lexica").hits)

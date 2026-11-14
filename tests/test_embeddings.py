"""Embeddings: el modo de pruebas es determinista y normalizado; Nomic recibe sus prefijos."""

from __future__ import annotations

import math

from riopaila_qa.agent.embeddings import HashingEmbeddings, PrefixedEmbeddings


def test_hashing_determinista_y_normalizado():
    e = HashingEmbeddings(64)
    a, b = e.embed_query("azúcar orgánica"), e.embed_query("azúcar orgánica")
    assert a == b and math.isclose(sum(x * x for x in a), 1.0, rel_tol=1e-6)


def test_prefijos_de_nomic():
    vistos: list[str] = []

    class Espia(HashingEmbeddings):
        def embed_documents(self, texts):
            vistos.extend(texts)
            return super().embed_documents(texts)

        def embed_query(self, text):
            vistos.append(text)
            return super().embed_query(text)

    p = PrefixedEmbeddings(Espia(16))
    p.embed_documents(["doc"])
    p.embed_query("pregunta")
    assert vistos == ["search_document: doc", "search_query: pregunta"]

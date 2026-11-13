"""Recuperación híbrida: densa (Qdrant) + léxica (BM25 del M1) fusionadas con RRF.

Reciprocal Rank Fusion (Cormack et al., 2009): cada lista aporta ``1 / (k + rank)``
al puntaje de un chunk. No exige calibrar escalas distintas (coseno vs. BM25) y
premia los fragmentos que aparecen arriba en ambas listas.

* La parte **densa** entiende paráfrasis (“nació” ≈ “fundada”).
* La parte **léxica** acierta nombres propios, siglas y cifras exactas (“Riocas”, “T3”).
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Literal

from langchain_core.embeddings import Embeddings

from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.corpus import BM25
from riopaila_qa.rag.documents import RagChunk
from riopaila_qa.rag.index import build_filter, dense_search

Mode = Literal["hibrida", "densa", "lexica"]
RRF_K = 60


@dataclass
class Hit:
    """Un fragmento recuperado, con la traza de cómo llegó."""

    rank: int
    chunk: RagChunk
    score: float
    dense_rank: int | None = None
    lexical_rank: int | None = None
    dense_score: float | None = None

    def as_dict(self) -> dict:
        d = asdict(self)
        d["chunk"] = self.chunk.model_dump()
        return d


@dataclass
class RetrievalResult:
    query: str
    mode: str
    hits: list[Hit]
    latency_ms: float
    filters: dict = field(default_factory=dict)


class HybridRetriever:
    """Recuperador del agente: top-k híbrido con filtros por *payload*."""

    def __init__(self, chunks: list[RagChunk], embeddings: Embeddings, settings: AgentSettings):
        self.chunks = chunks
        self.by_id = {c.chunk_id: c for c in chunks}
        self.embeddings = embeddings
        self.settings = settings
        self.bm25 = BM25([f"{c.titulo} {c.seccion} {c.texto}" for c in chunks])

    def _lexical(self, query: str, limit: int, allowed: set[str] | None) -> list[tuple[RagChunk, float]]:
        scores = self.bm25.scores(query)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out = []
        for i in order:
            if scores[i] <= 0:
                break
            c = self.chunks[i]
            if allowed is not None and c.chunk_id not in allowed:
                continue
            out.append((c, scores[i]))
            if len(out) >= limit:
                break
        return out

    def _allowed_ids(self, seccion, tipo, anio, include_adversarial) -> set[str] | None:
        if not any([seccion, tipo, anio]) and include_adversarial:
            return None
        return {
            c.chunk_id
            for c in self.chunks
            if (not seccion or c.seccion == seccion)
            and (not tipo or c.tipo == tipo)
            and (not anio or c.anio == anio)
            and (include_adversarial or c.origen != "sintetico")
        }

    def search(
        self,
        query: str,
        k: int | None = None,
        mode: Mode = "hibrida",
        seccion: str | None = None,
        tipo: str | None = None,
        anio: int | None = None,
        include_adversarial: bool | None = None,
        exact: bool = False,
    ) -> RetrievalResult:
        """Top-k de fragmentos para la consulta (por defecto, híbrido)."""
        t0 = time.perf_counter()
        k = k or self.settings.top_k
        n = max(self.settings.candidates, k)
        include_adv = self.settings.include_adversarial if include_adversarial is None else include_adversarial

        dense: list[tuple[RagChunk, float]] = []
        if mode in ("hibrida", "densa"):
            qv = self.embeddings.embed_query(query)
            dense = dense_search(qv, self.settings, n, build_filter(seccion, tipo, anio, include_adv), exact)
        lexical: list[tuple[RagChunk, float]] = []
        if mode in ("hibrida", "lexica"):
            lexical = self._lexical(query, n, self._allowed_ids(seccion, tipo, anio, include_adv))

        fused: dict[str, Hit] = {}
        for r, (c, s) in enumerate(dense, start=1):
            fused[c.chunk_id] = Hit(0, c, 1 / (RRF_K + r), dense_rank=r, dense_score=s)
        for r, (c, _s) in enumerate(lexical, start=1):
            hit = fused.get(c.chunk_id)
            if hit:
                hit.score += 1 / (RRF_K + r)
                hit.lexical_rank = r
            else:
                fused[c.chunk_id] = Hit(0, c, 1 / (RRF_K + r), lexical_rank=r)
        ranked = sorted(fused.values(), key=lambda h: h.score, reverse=True)[:k]
        for i, h in enumerate(ranked, start=1):
            h.rank = i
        filters = {key: v for key, v in {"seccion": seccion, "tipo": tipo, "anio": anio}.items() if v}
        return RetrievalResult(query, mode, ranked, (time.perf_counter() - t0) * 1000, filters)

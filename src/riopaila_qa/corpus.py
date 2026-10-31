"""Acceso al corpus Gold y armado del contexto que va en el prompt de sistema.

Dos modos de contexto:

* ``completo`` — consolida TODO el texto limpio en el prompt de sistema, como
  pide el Taller 1. Funciona con modelos de contexto largo (p. ej. Gemini).
* ``bm25`` — si el corpus no cabe en el presupuesto de tokens del modelo local,
  se preseleccionan los fragmentos más relevantes con BM25 (búsqueda léxica).
  Es la respuesta de ingeniería a *Lost in the Middle* (Liu et al., 2023) y el
  puente hacia el RAG con embeddings del Módulo 2.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from riopaila_qa.config import Paths
from riopaila_qa.scraping.models import Chunk, GoldDoc

SECTION_ORDER = [
    "inicio",
    "identidad",
    "negocios-y-productos",
    "procesos-productivos",
    "sostenibilidad",
    "gobierno-corporativo",
    "contacto",
    "institucional",
    "noticias",
]

# Palabras vacías del español: no aportan a la búsqueda léxica.
STOPWORDS = set(
    [
        "a",
        "al",
        "algo",
        "algunas",
        "algunos",
        "ante",
        "antes",
        "como",
        "con",
        "contra",
        "cual",
        "cuales",
        "cuando",
        "de",
        "del",
        "desde",
        "donde",
        "durante",
        "e",
        "el",
        "ella",
        "ellas",
        "ellos",
        "en",
        "entre",
        "era",
        "es",
        "esa",
        "esas",
        "ese",
        "eso",
        "esos",
        "esta",
        "estas",
        "este",
        "esto",
        "estos",
        "fue",
        "han",
        "hay",
        "la",
        "las",
        "le",
        "les",
        "lo",
        "los",
        "mas",
        "me",
        "mi",
        "mis",
        "mucho",
        "muy",
        "no",
        "nos",
        "o",
        "os",
        "otra",
        "otro",
        "para",
        "pero",
        "por",
        "porque",
        "que",
        "quien",
        "se",
        "sea",
        "segun",
        "ser",
        "si",
        "sin",
        "sobre",
        "son",
        "su",
        "sus",
        "tambien",
        "te",
        "tiene",
        "tienen",
        "todo",
        "todos",
        "tu",
        "un",
        "una",
        "uno",
        "unos",
        "y",
        "ya",
        "cual",
        "cuantos",
        "cuantas",
        "cuanto",
        "cuanta",
        "que",
        "hace",
        "hacen",
        "riopaila",
        "castilla",
        "empresa",
    ]
)


STEM_LEN = 5  # truncamiento: "fundada"/"fundación" → "funda", "productos"/"producto" → "produ"

# Páginas institucionales que siempre entran al contexto (identidad y contacto):
# responden las preguntas de primer contacto aunque la búsqueda léxica no las encuentre.
PINNED_URL_KEYS = ("somos-riopaila-castilla", "/contactanos/")
PINNED_MAX_TOKENS = 1500
NEWS_WEIGHT = 0.85  # hay 3 noticias por cada página: se prioriza levemente lo institucional


def tokenize(text: str) -> list[str]:
    """Tokenización léxica: minúsculas, sin tildes, sin palabras vacías y con stemming por truncamiento."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return [t[:STEM_LEN] for t in re.findall(r"[a-z0-9]+", text) if t not in STOPWORDS and len(t) > 1]


class BM25:
    """Implementación compacta de Okapi BM25 (k1=1.5, b=0.75)."""

    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs = [tokenize(t) for t in texts]
        self.tf = [Counter(d) for d in self.docs]
        self.lengths = [len(d) for d in self.docs]
        self.avgdl = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        """Puntaje BM25 de cada documento frente a la consulta."""
        q = tokenize(query)
        out = []
        for tf, dl in zip(self.tf, self.lengths, strict=True):
            s = 0.0
            for term in q:
                if term not in tf:
                    continue
                f = tf[term]
                s += (
                    self.idf.get(term, 0.0)
                    * f
                    * (self.k1 + 1)
                    / (f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1)))
                )
            out.append(s)
        return out


def reorder_for_long_context(items: list) -> list:
    """Pone lo más relevante en los extremos y lo menos en el centro (curva en U).

    Entrada ordenada por relevancia [1, 2, 3, 4, 5] → salida [1, 3, 5, 4, 2].
    """
    head = items[0::2]
    tail = items[1::2]
    return head + tail[::-1]


@dataclass
class ContextPiece:
    """Un bloque de contexto numerado que el modelo puede citar como [n]."""

    n: int
    titulo: str
    url: str
    seccion: str
    texto: str
    tokens: int
    score: float | None = None


@dataclass
class BuiltContext:
    """Contexto listo para el prompt y trazabilidad de lo que entró."""

    text: str
    pieces: list[ContextPiece]
    mode: str
    tokens: int
    omitted: int = 0
    notes: list[str] = field(default_factory=list)

    def url_for(self, n: int) -> str | None:
        for p in self.pieces:
            if p.n == n:
                return p.url
        return None


def render_pieces(pieces: list[ContextPiece]) -> str:
    """Envuelve cada fragmento en etiquetas XML con sus metadatos."""
    blocks = [
        f'<documento id="{p.n}" titulo="{p.titulo.replace(chr(34), chr(39))}" seccion="{p.seccion}" url="{p.url}">\n{p.texto}\n</documento>'
        for p in pieces
    ]
    return "\n\n".join(blocks)


class CorpusStore:
    """Carga los documentos y fragmentos Gold desde disco."""

    def __init__(self, paths: Paths) -> None:
        self.paths = paths
        self.docs: list[GoldDoc] = self._load(paths.corpus, GoldDoc)
        self.chunks: list[Chunk] = self._load(paths.chunks, Chunk)
        self._bm25: BM25 | None = None

    @staticmethod
    def _load(path: Path, model):
        if not path.exists():
            return []
        return [model.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    @property
    def available(self) -> bool:
        return bool(self.docs)

    @property
    def total_tokens(self) -> int:
        return sum(d.tokens for d in self.docs)

    def manifest(self) -> dict:
        if self.paths.manifest.exists():
            return json.loads(self.paths.manifest.read_text(encoding="utf-8"))
        return {}

    @property
    def bm25(self) -> BM25:
        if self._bm25 is None:
            self._bm25 = BM25([f"{c.titulo} {c.seccion} {c.texto}" for c in self.chunks])
        return self._bm25

    def sorted_docs(self, sections: list[str] | None = None) -> list[GoldDoc]:
        """Documentos en orden de prioridad de sección (identidad primero)."""
        rank = {s: i for i, s in enumerate(SECTION_ORDER)}
        docs = [d for d in self.docs if not sections or d.seccion in sections]
        return sorted(docs, key=lambda d: (rank.get(d.seccion, 99), d.url))

    def full_context(self, budget_tokens: int, sections: list[str] | None = None) -> BuiltContext:
        """Modo ``completo``: todo el corpus (o las secciones elegidas) hasta el presupuesto."""
        pieces, used, omitted = [], 0, 0
        for doc in self.sorted_docs(sections):
            if used + doc.tokens > budget_tokens:
                omitted += 1
                continue
            pieces.append(ContextPiece(len(pieces) + 1, doc.titulo, doc.url, doc.seccion, doc.markdown, doc.tokens))
            used += doc.tokens
        notes = []
        if omitted:
            notes.append(f"{omitted} documentos no cupieron en el presupuesto de {budget_tokens:,} tokens.")
        return BuiltContext(render_pieces(pieces), pieces, "completo", used, omitted, notes)

    def pinned_chunks(self) -> list[Chunk]:
        """Fragmentos institucionales fijos (identidad y contacto), hasta ``PINNED_MAX_TOKENS``."""
        pinned, used = [], 0
        for chunk in self.chunks:
            if any(key in chunk.url for key in PINNED_URL_KEYS) and used + chunk.tokens <= PINNED_MAX_TOKENS:
                pinned.append(chunk)
                used += chunk.tokens
        return pinned

    def bm25_context(
        self, query: str, budget_tokens: int, top_k: int = 8, sections: list[str] | None = None
    ) -> BuiltContext:
        """Modo ``bm25``: contexto institucional fijo + los fragmentos más relevantes, dentro del presupuesto."""
        scores = [
            sc * (NEWS_WEIGHT if c.seccion == "noticias" else 1.0)
            for sc, c in zip(self.bm25.scores(query), self.chunks, strict=True)
        ]
        pinned = [] if sections else self.pinned_chunks()
        pinned_ids = {c.chunk_id for c in pinned}
        used = sum(c.tokens for c in pinned)
        ranked = sorted(
            (i for i, c in enumerate(self.chunks) if (not sections or c.seccion in sections)),
            key=lambda i: scores[i],
            reverse=True,
        )
        chosen = []
        for i in ranked:
            if len(chosen) >= top_k:
                break
            chunk = self.chunks[i]
            if chunk.chunk_id in pinned_ids or used + chunk.tokens > budget_tokens:
                continue
            chosen.append((chunk, scores[i]))
            used += chunk.tokens
        # Lo fijo va al inicio (primacy); lo recuperado se reordena en U.
        ordered = [(c, None) for c in pinned] + reorder_for_long_context(chosen)
        pieces = [
            ContextPiece(n, c.titulo, c.url, c.seccion, c.texto, c.tokens, None if sc is None else round(sc, 3))
            for n, (c, sc) in enumerate(ordered, start=1)
        ]
        notes = [
            f"Contexto fijo: {len(pinned)} fragmentos institucionales · "
            f"preselección BM25: {len(chosen)} de {len(self.chunks)} fragmentos."
        ]
        return BuiltContext(render_pieces(pieces), pieces, "bm25", used, len(self.chunks) - len(pieces), notes)

    def build_context(
        self, query: str, budget_tokens: int, mode: str = "auto", sections: list[str] | None = None
    ) -> BuiltContext:
        """Elige el modo: ``auto`` usa el corpus completo si cabe; si no, BM25."""
        total = sum(d.tokens for d in self.docs if not sections or d.seccion in sections)
        if mode == "completo" or (mode == "auto" and total <= budget_tokens):
            return self.full_context(budget_tokens, sections)
        return self.bm25_context(query, budget_tokens, sections=sections)

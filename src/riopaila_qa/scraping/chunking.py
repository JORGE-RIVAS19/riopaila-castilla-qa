"""Segmentación (chunking) de los documentos Gold en fragmentos coherentes.

Se corta primero por encabezados Markdown (fronteras semánticas naturales) y
luego por párrafos/oraciones con ``RecursiveCharacterTextSplitter``. Cada
fragmento lleva el título de su página para quedar autocontenido.
"""

from __future__ import annotations

import json

from langchain_text_splitters import RecursiveCharacterTextSplitter

from riopaila_qa.config import Paths
from riopaila_qa.scraping.models import Chunk, GoldDoc
from riopaila_qa.textutils import count_tokens

CHUNK_SIZE = 1200  # caracteres ≈ 300 tokens en español
CHUNK_OVERLAP = 150


def make_splitter() -> RecursiveCharacterTextSplitter:
    """Splitter con separadores en orden de prioridad semántica."""
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", ". ", " "],
        keep_separator=True,
    )


def chunk_documents(docs: list[GoldDoc]) -> list[Chunk]:
    """Divide cada documento Gold en fragmentos con metadatos de procedencia."""
    splitter = make_splitter()
    chunks: list[Chunk] = []
    for doc in docs:
        for i, piece in enumerate(splitter.split_text(doc.markdown)):
            text = piece.strip()
            if not text.startswith("#"):
                text = f"[{doc.titulo}]\n{text}"
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.id}-{i:03d}",
                    doc_id=doc.id,
                    url=doc.url,
                    titulo=doc.titulo,
                    seccion=doc.seccion,
                    indice=i,
                    tokens=count_tokens(text),
                    texto=text,
                )
            )
    return chunks


def write_chunks(chunks: list[Chunk], paths: Paths) -> None:
    """Persiste los fragmentos en ``data/gold/chunks.jsonl``."""
    with paths.chunks.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")

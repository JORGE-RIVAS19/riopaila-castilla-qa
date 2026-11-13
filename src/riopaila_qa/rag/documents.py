"""Unidades de recuperación del RAG: los chunks Gold del Módulo 1, limpios.

Al revisar ``chunks.jsonl`` encontramos 25 fragmentos contaminados con el panel
de accesibilidad del sitio (“Modo para personas con discapacidad visual…”), que
la deduplicación por páginas del M1 no alcanzó a quitar porque vive dentro de
algunos cuerpos de noticia. Antes de indexar se eliminan las líneas que se
repiten en muchos documentos distintos (mismo criterio de *boilerplate* del M1,
aplicado ahora a nivel de chunk).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from riopaila_qa.config import Paths

MIN_CHARS = 120  # un chunk con menos texto útil no responde nada
BOILERPLATE_MIN_DOCS = 5  # una línea presente en ≥5 documentos distintos es plantilla del sitio


class RagChunk(BaseModel):
    """Fragmento listo para indexar en Qdrant (texto + *payload*)."""

    chunk_id: str
    doc_id: str
    url: str
    titulo: str
    seccion: str
    tipo: str = Field(description="pagina | noticia | prueba")
    anio: int | None = None
    indice: int = 0
    texto: str
    origen: str = Field("corpus", description="corpus (sitio real) | sintetico (prueba de blindaje)")

    def payload(self) -> dict:
        return self.model_dump()


def _norm_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


MONTHS = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"
DATELINE = re.compile(rf"\b(?:{MONTHS})\s+(?:\d{{1,2}}\s+)?(?:de\s+|del\s+)?(20[12]\d)\b", re.IGNORECASE)


def _year_from(doc: dict) -> int | None:
    """Año de publicación: metadato de WordPress o, en noticias, la data (“Cali, abril de 2024”)."""
    m = re.match(r"(\d{4})", doc.get("fecha_publicacion") or "")
    if m:
        return int(m.group(1))
    if doc.get("tipo") != "noticia":
        return None
    m = DATELINE.search(doc.get("markdown", "")[:1500])
    return int(m.group(1)) if m else None


def boilerplate_lines(chunks: list[dict]) -> set[str]:
    """Líneas que aparecen en muchos documentos distintos (plantilla del sitio)."""
    docs_per_line: dict[str, set[str]] = {}
    for c in chunks:
        for line in c["texto"].splitlines():
            key = _norm_line(line)
            if len(key) >= 12 and not key.startswith("["):
                docs_per_line.setdefault(key, set()).add(c["doc_id"])
    return {k for k, docs in docs_per_line.items() if len(docs) >= BOILERPLATE_MIN_DOCS}


def clean_text(text: str, boilerplate: set[str]) -> str:
    """Quita las líneas de plantilla y colapsa los saltos de línea repetidos."""
    lines = [ln for ln in text.splitlines() if _norm_line(ln) not in boilerplate]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def load_corpus_chunks(paths: Paths) -> tuple[list[RagChunk], dict]:
    """Carga y limpia los chunks Gold. Devuelve los chunks y estadísticas de limpieza."""
    raw = [json.loads(line) for line in paths.chunks.read_text(encoding="utf-8").splitlines() if line.strip()]
    docs = {}
    if paths.corpus.exists():
        for line in paths.corpus.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                docs[d["id"]] = d
    boiler = boilerplate_lines(raw)
    out: list[RagChunk] = []
    dropped = 0
    touched = 0
    for c in raw:
        cleaned = clean_text(c["texto"], boiler)
        if cleaned != c["texto"].strip():
            touched += 1
        body = re.sub(r"^\[[^\]]*\]\s*", "", cleaned)
        if len(body) < MIN_CHARS:
            dropped += 1
            continue
        doc = docs.get(c["doc_id"], {})
        out.append(
            RagChunk(
                chunk_id=c["chunk_id"],
                doc_id=c["doc_id"],
                url=c["url"],
                titulo=c["titulo"],
                seccion=c["seccion"],
                tipo=doc.get("tipo", "noticia" if c["seccion"] == "noticias" else "pagina"),
                anio=_year_from(doc) if doc else None,
                indice=c.get("indice", 0),
                texto=cleaned,
            )
        )
    stats = {
        "chunks_gold": len(raw),
        "lineas_plantilla": len(boiler),
        "chunks_limpiados": touched,
        "chunks_descartados_cortos": dropped,
        "chunks_indexables": len(out),
    }
    return out, stats


def load_adversarial_chunks(directory: Path) -> list[RagChunk]:
    """Documentos sintéticos de prueba de blindaje (caso 5), marcados con ``origen=sintetico``."""
    chunks: list[RagChunk] = []
    if not directory.exists():
        return chunks
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta: dict = {}
        body = text
        if text.startswith("---"):
            _, fm, body = text.split("---", 2)
            meta = yaml.safe_load(fm) or {}
        chunks.append(
            RagChunk(
                chunk_id=f"{meta.get('id', path.stem)}-000",
                doc_id=str(meta.get("id", path.stem)),
                url=str(meta.get("url", f"interno://{path.stem}")),
                titulo=str(meta.get("titulo", path.stem)),
                seccion=str(meta.get("seccion", "prueba_blindaje")),
                tipo=str(meta.get("tipo", "prueba")),
                texto=f"[{meta.get('titulo', path.stem)}]\n{body.strip()}",
                origen="sintetico",
            )
        )
    return chunks


def boilerplate_report(paths: Paths) -> Counter:
    """Cuenta cuántos chunks contenían cada línea de plantilla (para el informe)."""
    raw = [json.loads(line) for line in paths.chunks.read_text(encoding="utf-8").splitlines() if line.strip()]
    boiler = boilerplate_lines(raw)
    counts: Counter = Counter()
    for c in raw:
        for line in c["texto"].splitlines():
            if _norm_line(line) in boiler:
                counts[_norm_line(line)[:60]] += 1
    return counts

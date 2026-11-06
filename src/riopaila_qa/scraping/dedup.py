"""Etapa 4 · Deduplicar: páginas idénticas, casi idénticas y boilerplate repetido.

Sin este paso, el pie de página (dirección, línea ética, redes) aparece en
todas las páginas: gasta tokens en el prompt y en el Módulo 2 el buscador
vectorial lo devolvería en cada consulta.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from riopaila_qa.scraping.models import SilverPage
from riopaila_qa.textutils import normalize_text, paragraph_key, sha256

_BLOCK_SPLIT = re.compile(r"\n\s*\n")


@dataclass
class DedupReport:
    """Qué se descartó y por qué (se muestra en la app y en el manifiesto)."""

    exact_duplicates: list[str] = field(default_factory=list)
    near_duplicates: list[tuple[str, str, float]] = field(default_factory=list)
    too_short: list[str] = field(default_factory=list)
    boilerplate_blocks: list[str] = field(default_factory=list)
    boilerplate_removed: int = 0


def _blocks(markdown: str) -> list[str]:
    return [b.strip() for b in _BLOCK_SPLIT.split(markdown) if b.strip()]


def shingles(text: str, k: int = 5) -> set[str]:
    """Conjunto de k-gramas de palabras para medir similitud de Jaccard."""
    words = paragraph_key(text).split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    """Similitud de Jaccard entre dos conjuntos."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_boilerplate(pages: list[SilverPage], min_docs: int = 3, ratio: float = 0.3) -> set[str]:
    """Bloques que aparecen en muchas páginas distintas (menús, pies, banners)."""
    if len(pages) < min_docs:
        return set()
    df: Counter[str] = Counter()
    for page in pages:
        df.update({paragraph_key(b) for b in _blocks(page.markdown)})
    threshold = max(min_docs, int(ratio * len(pages)))
    return {key for key, n in df.items() if key and n >= threshold}


def deduplicate(
    pages: list[SilverPage], min_chars: int = 200, near_threshold: float = 0.9
) -> tuple[list[SilverPage], DedupReport]:
    """Aplica las tres pasadas de deduplicación y el filtro de longitud mínima."""
    report = DedupReport()

    # 1) Duplicados exactos (mismo texto servido en dos URLs).
    seen_hashes: set[str] = set()
    unique: list[SilverPage] = []
    for page in pages:
        if page.hash_texto in seen_hashes:
            report.exact_duplicates.append(page.url)
            continue
        seen_hashes.add(page.hash_texto)
        unique.append(page)

    # 2) Boilerplate: bloques repetidos en ≥30 % de las páginas.
    boiler = find_boilerplate(unique)
    report.boilerplate_blocks = sorted(boiler)[:50]
    cleaned: list[SilverPage] = []
    for page in unique:
        kept = []
        for block in _blocks(page.markdown):
            if paragraph_key(block) in boiler:
                report.boilerplate_removed += 1
            else:
                kept.append(block)
        text = normalize_text("\n\n".join(kept))
        cleaned.append(page.model_copy(update={"markdown": text, "hash_texto": sha256(text)}))

    # 3) Longitud mínima tras quitar el boilerplate.
    long_enough = []
    for page in cleaned:
        if len(page.markdown) < min_chars:
            report.too_short.append(page.url)
        else:
            long_enough.append(page)

    # 4) Casi duplicados (Jaccard de 5-gramas ≥ umbral).
    final: list[SilverPage] = []
    signatures: list[set[str]] = []
    for page in long_enough:
        sig = shingles(page.markdown)
        match = next(
            ((final[i].url, sim) for i, s in enumerate(signatures) if (sim := jaccard(sig, s)) >= near_threshold),
            None,
        )
        if match:
            report.near_duplicates.append((page.url, match[0], round(match[1], 3)))
            continue
        final.append(page)
        signatures.append(sig)
    return final, report

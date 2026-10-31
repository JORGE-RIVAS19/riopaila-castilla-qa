"""Etapa 5 · Enriquecer (Gold): Markdown con frontmatter YAML + corpus.jsonl.

Los metadatos no son decoración: permiten citar la URL de origen en cada
respuesta, filtrar por sección y saber qué volver a capturar (fecha + hash).
"""

from __future__ import annotations

import json
import shutil
from urllib.parse import urlparse

import yaml

from riopaila_qa.config import Paths
from riopaila_qa.scraping.models import GoldDoc, SilverPage
from riopaila_qa.textutils import count_tokens, short_hash, slugify

# Mapa del menú del sitio (Nuestro ADN / Nuestros negocios / Sostenibilidad…)
# a secciones temáticas. Se evalúa en orden: la primera coincidencia gana.
SECTION_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("contacto", ("contactanos", "contacto", "trabaja-con-nosotros")),
    (
        "gobierno-corporativo",
        (
            "organos-de-gobierno",
            "politica",
            "codigo-de-etica",
            "conflicto-de-intereses",
            "inversionistas",
            "junta",
            "asamblea",
        ),
    ),
    (
        "identidad",
        (
            "somos-riopaila",
            "quienes-somos",
            "nuestro-camino",
            "enfoque-asg",
            "historia",
            "adhesiones",
            "reconocimientos",
        ),
    ),
    ("procesos-productivos", ("/cana/", "ganaderia", "palma-4")),
    (
        "negocios-y-productos",
        (
            "azucar",
            "mieles",
            "jarabe",
            "mezclas",
            "palma",
            "energia",
            "alcohol",
            "fertirio",
            "abonos",
            "servicios-agricolas",
            "aliados-productivos",
        ),
    ),
    (
        "sostenibilidad",
        (
            "agricultura-regenerativa",
            "fondo-concursable",
            "comunidades",
            "caminos-rurales",
            "abastecimiento",
            "nuestra-gente",
            "postales",
            "informes",
            "derechos-humanos",
            "ods",
            "sostenib",
            "carbono",
        ),
    ),
]


def classify_section(url: str, is_post: bool) -> str:
    """Asigna una sección temática a partir de la ruta de la URL."""
    path = urlparse(url).path.lower()
    if path in ("", "/"):
        return "inicio"
    if is_post:
        return "noticias"
    for section, keys in SECTION_RULES:
        if any(k in path for k in keys):
            return section
    return "institucional"


def to_gold(page: SilverPage, company: str, post_urls: set[str]) -> GoldDoc:
    """Convierte una página Silver en un documento Gold enriquecido."""
    is_post = page.url in post_urls
    section = classify_section(page.url, is_post)
    return GoldDoc(
        id=short_hash(page.url, 10),
        url=page.url,
        titulo=page.titulo,
        seccion=section,
        tipo="noticia" if is_post else "pagina",
        empresa=company,
        fecha_captura=page.fecha_captura[:10],
        fecha_publicacion=page.fecha_publicacion,
        tokens=count_tokens(page.markdown),
        hash=short_hash(page.markdown, 12),
        markdown=page.markdown,
    )


def frontmatter_markdown(doc: GoldDoc) -> str:
    """Serializa un documento como Markdown con frontmatter YAML."""
    meta = doc.model_dump(exclude={"markdown"})
    head = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    body = doc.markdown if doc.markdown.lstrip().startswith("#") else f"# {doc.titulo}\n\n{doc.markdown}"
    return f"---\n{head}\n---\n\n{body}\n"


def build_knowledge_base(docs: list[GoldDoc], company: str) -> str:
    """Consolida todo el corpus en un único Markdown limpio, agrupado por sección."""
    parts = [
        f"# Base de conocimiento · {company}\n",
        f"Documentos: {len(docs)} · Tokens: {sum(d.tokens for d in docs):,}\n",
    ]
    for section in sorted({d.seccion for d in docs}):
        parts.append(f"\n## Sección: {section}\n")
        for d in sorted((d for d in docs if d.seccion == section), key=lambda x: x.url):
            parts.append(f"\n### {d.titulo}\nFuente: {d.url}\n\n{d.markdown}\n")
    return "\n".join(parts)


def write_gold(docs: list[GoldDoc], paths: Paths, company: str) -> None:
    """Escribe un .md por página, corpus.jsonl y knowledge_base.md (reemplaza la capa)."""
    if paths.gold_pages.exists():
        shutil.rmtree(paths.gold_pages)
    paths.gold_pages.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    for doc in docs:
        name = slugify(urlparse(doc.url).path) or "inicio"
        if name in used:
            name = f"{name}-{doc.id[:6]}"
        used.add(name)
        (paths.gold_pages / f"{name}.md").write_text(frontmatter_markdown(doc), encoding="utf-8")
    with paths.corpus.open("w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc.model_dump(), ensure_ascii=False) + "\n")
    paths.knowledge_base.write_text(build_knowledge_base(docs, company), encoding="utf-8")

"""Contratos de datos (Pydantic) de cada capa Medallion."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Capture(BaseModel):
    """Registro Bronze: una línea de ``data/raw/captures.jsonl`` por URL visitada."""

    url: str
    final_url: str
    fecha_captura: str = Field(description="ISO-8601 UTC de la descarga")
    status: int
    content_type: str = ""
    bytes: int = 0
    hash: str = Field("", description="SHA-256 del cuerpo HTTP")
    html_path: str | None = Field(None, description="Ruta relativa del HTML crudo")
    error: str | None = None
    from_cache: bool = False


class SilverPage(BaseModel):
    """Registro Silver: texto útil de una página, ya sin HTML ni menús."""

    url: str
    titulo: str
    fecha_captura: str
    fecha_publicacion: str | None = None
    markdown: str
    hash_texto: str
    extractor: str = Field(description="trafilatura | beautifulsoup")


class GoldDoc(BaseModel):
    """Registro Gold: Markdown enriquecido con metadatos, insumo del Q&A y del RAG."""

    id: str
    url: str
    titulo: str
    seccion: str
    tipo: str = Field(description="pagina | noticia")
    empresa: str
    fecha_captura: str
    fecha_publicacion: str | None = None
    idioma: str = "es"
    tokens: int
    hash: str
    markdown: str


class Chunk(BaseModel):
    """Fragmento autocontenido de un documento Gold (insumo del RAG del Módulo 2)."""

    chunk_id: str
    doc_id: str
    url: str
    titulo: str
    seccion: str
    indice: int
    tokens: int
    texto: str

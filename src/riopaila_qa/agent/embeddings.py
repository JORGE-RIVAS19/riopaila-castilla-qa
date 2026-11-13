"""Fábrica de embeddings densos (Clase 6).

* ``ollama``: ``nomic-embed-text-v2-moe`` local (768 dims, el modelo de la clase).
  Nomic exige prefijos de tarea: ``search_document:`` al indexar y
  ``search_query:`` al consultar; sin ellos la recuperación empeora.
* ``gemini``: ``gemini-embedding-001`` por API, truncado a 768 dims gracias a
  Matryoshka (las primeras dimensiones concentran la información).
* ``fake``: embeddings por *hashing* de palabras, deterministas y sin red.
  Solo para pruebas automáticas y CI; nunca para la demo.
"""

from __future__ import annotations

import hashlib
import math
import os

from langchain_core.embeddings import Embeddings

from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.corpus import tokenize


class PrefixedEmbeddings(Embeddings):
    """Envuelve un modelo de embeddings y antepone los prefijos de tarea de Nomic."""

    def __init__(self, inner: Embeddings, doc_prefix: str = "search_document: ", query_prefix: str = "search_query: "):
        self.inner = inner
        self.doc_prefix = doc_prefix
        self.query_prefix = query_prefix

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.inner.embed_documents([self.doc_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self.inner.embed_query(self.query_prefix + text)


class GeminiTaskEmbeddings(Embeddings):
    """Gemini con ``task_type`` distinto para documentos y consultas, y dimensión Matryoshka."""

    def __init__(self, model: str, dims: int):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        if not os.getenv("GOOGLE_API_KEY"):
            raise RuntimeError("Falta GOOGLE_API_KEY en el .env para usar EMBED_PROVIDER=gemini")
        self.client = GoogleGenerativeAIEmbeddings(model=model)
        self.dims = dims

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.client.embed_documents(
            texts, task_type="RETRIEVAL_DOCUMENT", output_dimensionality=self.dims, batch_size=50
        )

    def embed_query(self, text: str) -> list[float]:
        return self.client.embed_query(text, task_type="RETRIEVAL_QUERY", output_dimensionality=self.dims)


class HashingEmbeddings(Embeddings):
    """Bolsa de palabras con *hashing trick*, normalizada (L2). Determinista y sin red."""

    def __init__(self, dims: int = 256):
        self.dims = dims

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dims
        for tok in tokenize(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % self.dims] += 1.0 if (h >> 8) % 2 else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def get_embeddings(settings: AgentSettings, provider: str | None = None) -> tuple[Embeddings, int, str]:
    """Devuelve ``(embeddings, dimensiones, nombre_del_modelo)`` según ``EMBED_PROVIDER``."""
    provider = (provider or settings.embed_provider).lower()
    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        from riopaila_qa.config import LLMSettings

        inner = OllamaEmbeddings(model=settings.ollama_embed_model, base_url=LLMSettings().ollama_base_url)
        return PrefixedEmbeddings(inner), settings.embed_dims, f"ollama:{settings.ollama_embed_model}"
    if provider == "gemini":
        model = settings.gemini_embed_model
        return GeminiTaskEmbeddings(model, settings.embed_dims), settings.embed_dims, f"gemini:{model}"
    if provider == "fake":
        return HashingEmbeddings(256), 256, "fake:hashing-256"
    raise ValueError(f"EMBED_PROVIDER no soportado: {provider} (usa ollama | gemini | fake)")

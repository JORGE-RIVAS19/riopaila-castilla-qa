"""Fábrica de modelos de chat de LangChain (Ollama local u API privada).

El resto del código no sabe qué proveedor está detrás: cambiar de Llama 3.2
local a Gemini u OpenAI es cambiar ``LLM_PROVIDER`` en el ``.env``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel

from riopaila_qa.config import LLMSettings

PROVIDERS = ("ollama", "gemini", "openai")


@dataclass(frozen=True)
class Sampling:
    """Parámetros de muestreo (Clase 4: temperatura y Top-p se ajustan juntos)."""

    temperature: float = 0.0
    top_p: float = 0.1


# Tabla de calibración por tarea (régimen de la matriz 2×2 de la Clase 4).
TASK_SAMPLING: dict[str, Sampling] = {
    "qa": Sampling(0.0, 0.1),  # Q1 · determinismo: extracción factual del corpus
    "faq": Sampling(0.0, 0.1),  # Q1 · salida estructurada (JSON/Pydantic)
    "resumen": Sampling(0.3, 0.9),  # Q2 · variabilidad fluida: resúmenes
    "extraccion": Sampling(0.0, 0.1),  # Q1 · esquema Pydantic
}


def model_name(settings: LLMSettings, provider: str | None = None) -> str:
    """Nombre del modelo configurado para el proveedor."""
    provider = provider or settings.provider
    return {
        "ollama": settings.ollama_model,
        "gemini": settings.gemini_model,
        "openai": settings.openai_model,
    }[provider]


def get_chat_model(
    settings: LLMSettings,
    provider: str | None = None,
    model: str | None = None,
    sampling: Sampling | None = None,
    num_ctx: int | None = None,
) -> BaseChatModel:
    """Construye el modelo de chat con el muestreo indicado."""
    provider = (provider or settings.provider).lower()
    sampling = sampling or Sampling(settings.temperature, settings.top_p)
    model = model or model_name(settings, provider)

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            base_url=settings.ollama_base_url,
            temperature=sampling.temperature,
            top_p=sampling.top_p,
            num_ctx=num_ctx or settings.ollama_num_ctx,
            num_predict=1024,
            keep_alive="30m",
        )
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not os.getenv("GOOGLE_API_KEY"):
            raise RuntimeError("Falta GOOGLE_API_KEY en el archivo .env")
        kwargs: dict = {"model": model, "max_output_tokens": 2048}
        # Gemini 3.x son modelos de razonamiento con muestreo fijo: la API ignora
        # temperature/top_p (la "regla inversa" de la Clase 4). Solo se envían a 2.x.
        if not model.startswith("gemini-3"):
            kwargs.update(temperature=sampling.temperature, top_p=sampling.top_p)
        return ChatGoogleGenerativeAI(**kwargs)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("Falta OPENAI_API_KEY en el archivo .env")
        return ChatOpenAI(model=model, temperature=sampling.temperature, top_p=sampling.top_p)
    raise ValueError(f"Proveedor no soportado: {provider}. Usa uno de {PROVIDERS}")

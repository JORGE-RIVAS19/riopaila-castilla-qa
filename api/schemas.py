"""Contratos tipados de la API (Pydantic): lo que el frontend envía y recibe."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    mensaje: str = Field(min_length=1, max_length=4000, description="Mensaje del usuario")
    thread_id: str | None = Field(None, description="Hilo existente; vacío = conversación nueva")
    user_id: str = Field("invitado", max_length=60, description="Usuario dueño de la memoria de largo plazo")


class ChatResponse(BaseModel):
    thread_id: str
    content: str
    ruta: dict[str, Any] | None = None
    fuentes: list[dict[str, Any]] = []
    blindaje: list[dict[str, Any]] = []
    herramientas: list[dict[str, Any]] = []
    latency_ms: float
    error: str | None = None


class ThreadSummary(BaseModel):
    thread_id: str
    titulo: str | None = None
    creado: str | None = None
    actualizado: str | None = None
    turnos: int = 0


class ThreadDetail(BaseModel):
    thread_id: str
    messages: list[dict[str, Any]]
    turnos: int
    checkpoint_id: str | None = None


class Checkpoint(BaseModel):
    checkpoint_id: str | None
    step: int | None
    source: str | None
    mensajes: int
    siguiente: list[str]
    creado: str | None


class ForkRequest(BaseModel):
    checkpoint_id: str
    user_id: str = "invitado"


class ForkResponse(BaseModel):
    thread_id: str


class MemoryFact(BaseModel):
    key: str
    clave: str
    valor: str
    hilo_origen: str | None = None
    actualizado: str | None = None


class MemoryFactIn(BaseModel):
    clave: str = Field(min_length=1, max_length=40)
    valor: str = Field(min_length=1, max_length=200)


class SearchRequest(BaseModel):
    consulta: str = Field(min_length=1, max_length=500)
    k: int = Field(10, ge=1, le=20)
    modo: Literal["hibrida", "densa", "lexica"] = "hibrida"
    seccion: str | None = None
    tipo: str | None = None
    anio: int | None = None


class RouteRequest(BaseModel):
    mensaje: str = Field(min_length=1, max_length=2000)

"""Contratos de la API: validación de entrada antes de tocar el agente."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.schemas import ChatRequest, SearchRequest


def test_mensaje_vacio_se_rechaza():
    with pytest.raises(ValidationError):
        ChatRequest(mensaje="")


def test_valores_por_defecto():
    req = ChatRequest(mensaje="hola")
    assert req.user_id == "invitado" and req.thread_id is None


def test_busqueda_limita_k_y_modo():
    with pytest.raises(ValidationError):
        SearchRequest(consulta="azúcar", k=50)
    with pytest.raises(ValidationError):
        SearchRequest(consulta="azúcar", modo="magica")

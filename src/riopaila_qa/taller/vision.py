"""Identificación de una pieza a partir de una foto (modelo multimodal con salida estructurada).

El LLM solo **describe** lo que ve (tipo de pieza, sistema, referencias legibles). La búsqueda
del código SAP es determinista (``consultas.verificar_codigo`` / ``buscar_repuesto``): así una
alucinación visual no se convierte en un pedido equivocado.
"""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from riopaila_qa.config import ROOT_DIR

PROMPT = ROOT_DIR / "prompts" / "vision_pieza_v1.md"


def instruccion() -> str:
    """Prompt versionado (regla 3 de AGENTS.md: ningún prompt vive dentro del código)."""
    return re.sub(r"<!--.*?-->", "", PROMPT.read_text(encoding="utf-8"), flags=re.DOTALL).strip()


class IdentificacionPieza(BaseModel):
    pieza: str = Field(description="Nombre de la pieza en español técnico, p. ej. 'filtro hidráulico de retorno'.")
    sistema: str = Field(description="Sistema de la máquina: hidráulico, motor, transmisión, eléctrico, corte…")
    referencias_visibles: list[str] = Field(
        default_factory=list, description="Números de parte legibles en la foto (tal cual se ven)."
    )
    marca_visible: str | None = Field(None, description="Marca impresa en la pieza, si se ve.")
    estado: str = Field(description="Estado aparente: nueva, desgastada, rota, con fuga, quemada…")
    terminos_busqueda: str = Field(description="3 a 6 palabras para buscar en el maestro de materiales de SAP.")
    confianza: float = Field(ge=0, le=1, description="Qué tan segura es la identificación (0 a 1).")


def a_data_url(imagen: str | Path) -> str:
    s = str(imagen)
    if s.startswith("data:image") or s.startswith("http"):
        return s
    tipo = mimetypes.guess_type(s)[0] or "image/jpeg"
    return f"data:{tipo};base64,{base64.b64encode(Path(s).read_bytes()).decode()}"


def identificar(llm: BaseChatModel, imagen: str | Path, nota: str = "") -> IdentificacionPieza:
    mensaje = HumanMessage(
        content=[
            {"type": "text", "text": f"Identifica esta pieza. Contexto del técnico: {nota or 'sin comentario'}"},
            {"type": "image_url", "image_url": {"url": a_data_url(imagen)}},
        ]
    )
    return llm.with_structured_output(IdentificacionPieza).invoke([SystemMessage(instruccion()), mensaje])

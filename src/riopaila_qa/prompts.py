"""Carga de prompts versionados desde la carpeta ``prompts/``.

Cada archivo tiene un encabezado de metadatos (comentario HTML) y dos bloques
separados por ``=== SYSTEM ===`` y ``=== HUMAN ===``. Versionar los prompts
como archivos permite revisarlos en los Pull Requests como cualquier código.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate

from riopaila_qa.config import ROOT_DIR

PROMPTS_DIR = ROOT_DIR / "prompts"
_META_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)

QA_VARIANTS = {
    "qa_v3_xml_sandwich": "v3 · XML + sándwich + citas (producción)",
    "qa_v2_rol_reglas": "v2 · rol + reglas anti-alucinación",
    "qa_v1_zero_shot": "v1 · zero-shot mínimo (línea base)",
}


@dataclass(frozen=True)
class PromptSpec:
    """Prompt cargado: identificador, metadatos y plantillas."""

    id: str
    meta: str
    system: str
    human: str

    def template(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([("system", self.system), ("human", self.human)])


def load_prompt(prompt_id: str, directory: Path = PROMPTS_DIR) -> PromptSpec:
    """Lee ``prompts/<prompt_id>.md`` y separa metadatos, system y human."""
    raw = (directory / f"{prompt_id}.md").read_text(encoding="utf-8")
    meta_match = _META_RE.search(raw)
    meta = meta_match.group(1).strip() if meta_match else ""
    body = _META_RE.sub("", raw)
    try:
        _, rest = body.split("=== SYSTEM ===", 1)
        system, human = rest.split("=== HUMAN ===", 1)
    except ValueError as exc:
        raise ValueError(f"El prompt {prompt_id} debe tener bloques SYSTEM y HUMAN") from exc
    return PromptSpec(prompt_id, meta, system.strip(), human.strip())

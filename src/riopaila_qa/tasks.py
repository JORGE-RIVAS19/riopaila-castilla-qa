"""Las tres tareas del Taller 1 orquestadas con LangChain (LCEL): Q&A, Resumen y FAQ.

Cada tarea arma el contexto desde el corpus Gold, aplica su prompt versionado y
su régimen de muestreo, y valida la salida en código (citas, abstención,
esquema Pydantic): el prompt solo no es una frontera de seguridad.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

from riopaila_qa.config import LLMSettings
from riopaila_qa.corpus import BuiltContext, CorpusStore
from riopaila_qa.llm import TASK_SAMPLING, get_chat_model, model_name
from riopaila_qa.prompts import load_prompt
from riopaila_qa.textutils import count_tokens

ABSTENTION = "No encuentro esa información en las fuentes públicas de Riopaila Castilla"
REFUSAL = "Solo puedo ayudarte con información pública de Riopaila Castilla"
_CITE_RE = re.compile(r"\[(\d+)\]")
_ANSWER_TOKENS = 1536  # espacio para la respuesta del modelo


@dataclass
class Citation:
    """Fuente citada por el modelo y verificada contra el contexto."""

    n: int
    titulo: str
    url: str


@dataclass
class TaskResult:
    """Salida común de las tareas, con trazabilidad para la app y el informe."""

    task: str
    output: str
    citations: list[Citation] = field(default_factory=list)
    invalid_citations: list[int] = field(default_factory=list)
    abstained: bool = False
    refused: bool = False
    prompt_id: str = ""
    model: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    latency_s: float = 0.0
    context: BuiltContext | None = None
    structured: list[dict] | None = None
    rendered_prompt: str = ""


class FAQItem(BaseModel):
    """Una pregunta frecuente con su respuesta y sus fuentes."""

    pregunta: str = Field(description="Pregunta de un cliente, en español")
    respuesta: str = Field(description="Respuesta breve basada solo en los documentos")
    fuentes: list[int] = Field(default_factory=list, description="ids de documento que la respaldan")


class FAQSet(BaseModel):
    """Conjunto de preguntas frecuentes generado por el modelo."""

    faqs: list[FAQItem]


class FichaEmpresa(BaseModel):
    """Ficha estructurada de una página (laboratorio de la Clase 4)."""

    tema_principal: str = Field(description="Tema central del documento")
    productos_o_servicios: list[str] = Field(default_factory=list)
    lugares: list[str] = Field(default_factory=list, description="Municipios, departamentos o países")
    cifras_clave: list[str] = Field(default_factory=list, description="Cifras textuales con su unidad")
    anios_mencionados: list[str] = Field(default_factory=list)
    programas_o_iniciativas: list[str] = Field(default_factory=list)
    contacto: str | None = Field(None, description="Canal de contacto si aparece")


def _friendly_errors(exc: Exception, provider: str, settings: LLMSettings) -> RuntimeError:
    text = str(exc)
    if provider == "ollama" and ("Connect" in type(exc).__name__ or "connect" in text.lower()):
        return RuntimeError(
            f"No pude conectar con Ollama en {settings.ollama_base_url}. "
            "Abre Ollama (o ejecuta `ollama serve`) y descarga el modelo con "
            f"`ollama pull {settings.ollama_model}`."
        )
    if provider == "ollama" and "not found" in text.lower():
        return RuntimeError(f"Ollama no tiene el modelo. Ejecuta `ollama pull {settings.ollama_model}`.")
    return RuntimeError(f"{type(exc).__name__}: {text}")


def _render(spec_template, values: dict) -> str:
    messages = spec_template.format_messages(**values)
    return "\n\n".join(f"[{m.type.upper()}]\n{m.content}" for m in messages)


def validate_citations(text: str, context: BuiltContext) -> tuple[list[Citation], list[int]]:
    """Extrae las citas [n] y separa las válidas de las inventadas."""
    valid: dict[int, Citation] = {}
    invalid: list[int] = []
    by_n = {p.n: p for p in context.pieces}
    for n in map(int, _CITE_RE.findall(text)):
        if n in by_n:
            valid.setdefault(n, Citation(n, by_n[n].titulo, by_n[n].url))
        elif n not in invalid:
            invalid.append(n)
    # Varias citas pueden apuntar a la misma URL (fragmentos de una página).
    seen_urls: set[str] = set()
    unique = []
    for c in sorted(valid.values(), key=lambda c: c.n):
        if c.url not in seen_urls:
            seen_urls.add(c.url)
            unique.append(c)
    return unique, invalid


def _num_ctx(prompt_tokens: int) -> int:
    """Ventana de Ollama ajustada al prompt REAL (múltiplo de 2048).

    Reservar la ventana según el presupuesto máximo (p. ej. 134k) obliga a Ollama a
    asignar una caché KV enorme y vuelve lenta cada respuesta aunque el prompt sea corto.
    """
    needed = prompt_tokens + _ANSWER_TOKENS
    return max(4096, -(-needed // 2048) * 2048)


def _model(
    settings: LLMSettings, task: str, provider: str | None, model: str | None, prompt_tokens: int
) -> BaseChatModel:
    return get_chat_model(settings, provider, model, TASK_SAMPLING[task], num_ctx=_num_ctx(prompt_tokens))


def answer_question(
    store: CorpusStore,
    question: str,
    settings: LLMSettings,
    provider: str | None = None,
    model: str | None = None,
    prompt_id: str = "qa_v3_xml_sandwich",
    mode: str = "auto",
    budget_tokens: int | None = None,
    llm: BaseChatModel | None = None,
) -> TaskResult:
    """Tarea Q&A: responde una pregunta con el corpus en el prompt de sistema."""
    provider = provider or settings.provider
    budget = budget_tokens or settings.max_context_tokens
    ctx = store.build_context(question, budget, mode)
    spec = load_prompt(prompt_id)
    template = spec.template()
    values = {"documentos": ctx.text, "pregunta": question.strip()}
    rendered = _render(template, values)
    chat = llm or _model(settings, "qa", provider, model, count_tokens(rendered))
    start = time.monotonic()
    try:
        text = (template | chat | StrOutputParser()).invoke(values).strip()
    except Exception as exc:  # noqa: BLE001 - se traduce a un mensaje útil para la UI
        raise _friendly_errors(exc, provider, settings) from exc
    citations, invalid = validate_citations(text, ctx)
    return TaskResult(
        task="qa",
        output=text,
        citations=citations,
        invalid_citations=invalid,
        abstained=ABSTENTION.lower() in text.lower(),
        refused=REFUSAL.lower() in text.lower(),
        prompt_id=prompt_id,
        model=model or model_name(settings, provider),
        provider=provider,
        prompt_tokens=count_tokens(rendered),
        latency_s=round(time.monotonic() - start, 2),
        context=ctx,
        rendered_prompt=rendered,
    )


def _scope_label(sections: list[str] | None) -> str:
    if not sections:
        return "Riopaila Castilla S.A. (todo el corpus)"
    return "Riopaila Castilla S.A., sección " + ", ".join(f"«{s}»" for s in sections)


def summarize(
    store: CorpusStore,
    settings: LLMSettings,
    sections: list[str] | None = None,
    provider: str | None = None,
    model: str | None = None,
    budget_tokens: int | None = None,
    llm: BaseChatModel | None = None,
) -> TaskResult:
    """Tarea Resumen: resumen ejecutivo del corpus o de las secciones elegidas."""
    provider = provider or settings.provider
    budget = budget_tokens or settings.max_context_tokens
    query = "historia fundacion productos negocios cifras municipios paises sostenibilidad comunidades energia"
    ctx = store.build_context(query, budget, "auto", sections)
    spec = load_prompt("resumen_v1")
    template = spec.template()
    values = {"documentos": ctx.text, "alcance": _scope_label(sections)}
    rendered = _render(template, values)
    chat = llm or _model(settings, "resumen", provider, model, count_tokens(rendered))
    start = time.monotonic()
    try:
        text = (template | chat | StrOutputParser()).invoke(values).strip()
    except Exception as exc:  # noqa: BLE001
        raise _friendly_errors(exc, provider, settings) from exc
    citations, invalid = validate_citations(text, ctx)
    return TaskResult(
        task="resumen",
        output=text,
        citations=citations,
        invalid_citations=invalid,
        prompt_id=spec.id,
        model=model or model_name(settings, provider),
        provider=provider,
        prompt_tokens=count_tokens(rendered),
        latency_s=round(time.monotonic() - start, 2),
        context=ctx,
        rendered_prompt=rendered,
    )


def _parse_json_faqs(text: str) -> FAQSet:
    """Respaldo si el proveedor no soporta salida estructurada: busca el JSON en el texto."""
    match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("El modelo no devolvió JSON")
    data = json.loads(match.group(0))
    if isinstance(data, list):
        data = {"faqs": data}
    return FAQSet.model_validate(data)


def generate_faq(
    store: CorpusStore,
    settings: LLMSettings,
    n: int = 6,
    sections: list[str] | None = None,
    provider: str | None = None,
    model: str | None = None,
    budget_tokens: int | None = None,
    llm: BaseChatModel | None = None,
) -> TaskResult:
    """Tarea FAQ: preguntas frecuentes con salida estructurada validada por Pydantic."""
    provider = provider or settings.provider
    budget = budget_tokens or settings.max_context_tokens
    query = "horarios sedes contacto productos azucar energia alcohol historia sostenibilidad trabajo proveedores"
    ctx = store.build_context(query, budget, "auto", sections)
    spec = load_prompt("faq_v1")
    template = spec.template()
    values = {"documentos": ctx.text, "alcance": _scope_label(sections), "n": n}
    rendered = _render(template, values)
    chat = llm or _model(settings, "faq", provider, model, count_tokens(rendered))
    start = time.monotonic()
    try:
        try:
            result = (template | chat.with_structured_output(FAQSet)).invoke(values)
            faqs = result if isinstance(result, FAQSet) else FAQSet.model_validate(result)
        except (NotImplementedError, ValueError, TypeError):
            raw = (template | chat | StrOutputParser()).invoke(values)
            faqs = _parse_json_faqs(raw)
    except Exception as exc:  # noqa: BLE001
        raise _friendly_errors(exc, provider, settings) from exc

    by_n = {p.n: p for p in ctx.pieces}
    rows, lines, invalid = [], [], []
    for item in faqs.faqs:
        sources = [by_n[i] for i in item.fuentes if i in by_n]
        invalid.extend(i for i in item.fuentes if i not in by_n)
        rows.append(
            {
                "pregunta": item.pregunta,
                "respuesta": item.respuesta,
                "fuentes": [s.url for s in sources],
                "sin_fuente": not sources,
            }
        )
        refs = "".join(f"[{s.n}]" for s in sources) or "(sin fuente válida)"
        lines.append(f"**{item.pregunta}**\n{item.respuesta} {refs}")
    citations, _ = validate_citations(" ".join(lines), ctx)
    return TaskResult(
        task="faq",
        output="\n\n".join(lines),
        citations=citations,
        invalid_citations=sorted(set(invalid)),
        prompt_id=spec.id,
        model=model or model_name(settings, provider),
        provider=provider,
        prompt_tokens=count_tokens(rendered),
        latency_s=round(time.monotonic() - start, 2),
        context=ctx,
        structured=rows,
        rendered_prompt=rendered,
    )


def extract_ficha(
    markdown: str,
    settings: LLMSettings,
    provider: str | None = None,
    model: str | None = None,
    llm: BaseChatModel | None = None,
) -> FichaEmpresa:
    """Extrae una ficha estructurada de un documento Gold (T=0, esquema Pydantic)."""
    provider = provider or settings.provider
    spec = load_prompt("extraccion_ficha_v1")
    chat = llm or _model(settings, "extraccion", provider, model, count_tokens(markdown))
    try:
        result = (spec.template() | chat.with_structured_output(FichaEmpresa)).invoke({"documento": markdown})
    except Exception as exc:  # noqa: BLE001
        raise _friendly_errors(exc, provider, settings) from exc
    return result if isinstance(result, FichaEmpresa) else FichaEmpresa.model_validate(result)

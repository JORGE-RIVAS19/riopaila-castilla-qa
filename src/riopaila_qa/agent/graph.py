"""Grafo del agente (LangGraph): ``router → directo | agente``.

```
START ─► router ─┬─► directo ─► END        (saludos, preguntas sobre el usuario: sin herramientas)
                 └─► agente  ─► END        (create_agent: RAG, CSV, memoria; bucle ReAct)
```

* ``router``: decisión tipada (reglas + LLM si hay duda) guardada en el estado.
* ``directo``: una sola llamada al LLM con ``trim_messages`` (historia recortada por
  tokens) y el perfil del Store; nunca toca Qdrant.
* ``agente``: arnés ``create_agent`` con ``@tool`` y middleware:
  ``dynamic_prompt`` (perfil + decisión del router), filtro de herramientas por
  ruta (``wrap_model_call``), ``SummarizationMiddleware`` (resume cuando la
  conversación supera el umbral de tokens), verificador de cifras (``after_model``:
  si la respuesta trae números que no salieron de una herramienta, se descarta y el
  modelo la rehace con ``comparar_cifras``), reintentos y límites de llamadas.
* ``checkpointer`` (SqliteSaver) + ``store`` (SqliteStore) se pasan al compilar.
"""

from __future__ import annotations

import operator
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, NotRequired

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelRequest,
    ModelRetryMiddleware,
    SummarizationMiddleware,
    ToolCallLimitMiddleware,
    after_model,
    dynamic_prompt,
    wrap_model_call,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage, trim_messages
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from riopaila_qa.agent import memory
from riopaila_qa.agent.numeros import cifras_sin_respaldo
from riopaila_qa.agent.router import TOOLS_BY_ROUTE, RouteDecision, route
from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.agent.tools import AgentContext
from riopaila_qa.config import ROOT_DIR
from riopaila_qa.structured import Indicador, catalogo

PROMPT_PATH = ROOT_DIR / "prompts" / "agente_v1.md"
MESES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]


class AgentTurnState(AgentState):
    """Estado que ve el subgrafo ``create_agent``: mensajes + decisión del router del turno."""

    ruta: NotRequired[dict[str, Any] | None]


class ChatState(AgentTurnState):
    """Estado del hilo en el grafo exterior: además, el historial de decisiones (una por turno).

    ``rutas`` NO está en el estado del subgrafo: si lo estuviera, el subgrafo lo devolvería completo y el
    reducer ``operator.add`` lo duplicaría en cada turno.
    """

    rutas: NotRequired[Annotated[list[dict[str, Any]], operator.add]]


@dataclass
class AgentDeps:
    """Dependencias del grafo (se inyectan para poder probar con modelos falsos)."""

    model: BaseChatModel
    tools: list
    indicadores: tuple[Indicador, ...]
    settings: AgentSettings
    router_model: BaseChatModel | None = None
    summary_model: BaseChatModel | None = None


def load_agent_prompt() -> str:
    raw = PROMPT_PATH.read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL).strip()


def last_human_text(messages: list) -> str:
    for m in reversed(messages):
        if es_mensaje_real_del_usuario(m):
            return m.text if hasattr(m, "text") else str(m.content)
    return ""


AVISO_VERIFICADOR = "verificador_cifras"


def es_aviso_verificador(m: object) -> bool:
    """Mensaje interno con el que el verificador de cifras pide rehacer la respuesta."""
    return isinstance(m, HumanMessage) and (m.additional_kwargs or {}).get("lc_source") == AVISO_VERIFICADOR


def es_mensaje_real_del_usuario(m: object) -> bool:
    """HumanMessage escrito por la persona (ni el resumen del historial ni el aviso del verificador)."""
    return isinstance(m, HumanMessage) and (m.additional_kwargs or {}).get("lc_source") not in (
        "summarization",
        AVISO_VERIFICADOR,
    )


def _texto(m: AIMessage) -> str:
    if isinstance(m.content, str):
        return m.content
    return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in m.content)


def _fecha() -> str:
    d = datetime.now()
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def render_system_prompt(template: str, decision: dict | None, profile: list[dict], user_id: str, cat: str) -> str:
    d = decision or {"ruta": "rag", "razon": "Sin decisión del router.", "cautela": False}
    tools = TOOLS_BY_ROUTE.get(d["ruta"], ())
    return (
        template.replace("{fecha}", _fecha())
        .replace("{usuario}", user_id)
        .replace("{perfil}", memory.profile_as_text(profile))
        .replace("{ruta}", d["ruta"])
        .replace("{razon}", d.get("razon", ""))
        .replace("{herramientas}", ", ".join(tools) if tools else "ninguna (responde directo)")
        .replace(
            "{cautela}",
            "MODO CAUTELA: la intención es ambigua; responde solo con evidencia de las herramientas o abstente."
            if d.get("cautela")
            else "",
        )
        .replace("{catalogo}", cat)
    )


def build_graph(deps: AgentDeps, checkpointer=None, store=None):
    """Compila el grafo completo del agente."""
    template = load_agent_prompt()
    cat = "\n".join(f"- {k}: {', '.join(v)}" for k, v in catalogo(deps.indicadores).items())
    s = deps.settings

    def _profile(runtime) -> tuple[list[dict], str]:
        ctx = runtime.context or AgentContext()
        if runtime.store is None:
            return [], ctx.user_id
        return memory.load_profile(runtime.store, ctx.user_id), ctx.user_id

    # ---- middleware del arnés create_agent ------------------------------------
    @dynamic_prompt
    def prompt_con_perfil_y_ruta(request: ModelRequest) -> str:
        """System prompt dinámico: perfil del Store + decisión del router (Clase 6/9)."""
        profile, uid = _profile(request.runtime)
        return render_system_prompt(template, request.state.get("ruta"), profile, uid, cat)

    @wrap_model_call
    def herramientas_por_ruta(request: ModelRequest, handler):
        """El router decide qué herramientas existen en el turno: no se busca si no hace falta."""
        d = request.state.get("ruta") or {}
        allowed = set(TOOLS_BY_ROUTE.get(d.get("ruta", "rag"), ()))
        return handler(request.override(tools=[t for t in request.tools if getattr(t, "name", "") in allowed]))

    @after_model(can_jump_to=["model"])
    def verificar_cifras(state: AgentState, runtime: Runtime[AgentContext]) -> dict | None:
        """El LLM no calcula: cada número de la respuesta debe estar en la evidencia del turno."""
        msgs = state["messages"]
        last = msgs[-1] if msgs else None
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        inicio = max((i for i, m in enumerate(msgs) if es_mensaje_real_del_usuario(m)), default=0)
        if any(es_aviso_verificador(m) for m in msgs[inicio:]):
            return None  # un solo reintento por turno: nunca un bucle
        evidencia = [str(m.content) for m in msgs if isinstance(m, ToolMessage)]
        evidencia += [str(m.content) for m in msgs if isinstance(m, HumanMessage) and not es_aviso_verificador(m)]
        faltan = cifras_sin_respaldo(_texto(last), evidencia)
        if not faltan:
            return None
        aviso = HumanMessage(
            "VERIFICADOR DE CIFRAS (mensaje automático, no del usuario): tu respuesta trae números que no "
            f"aparecen en ningún resultado de herramienta: {', '.join(faltan)}. No hagas aritmética mental. "
            "Si es una diferencia, razón o porcentaje, llama a comparar_cifras con los valores exactos de "
            "consultar_indicadores (si la cifra dice «más de», acláralo); si no tienes la herramienta, quita "
            "esos números. Luego responde de nuevo al usuario.",
            additional_kwargs={"lc_source": AVISO_VERIFICADOR},
        )
        return {"messages": [RemoveMessage(id=last.id), aviso], "jump_to": "model"}

    agent = create_agent(
        model=deps.model,
        tools=deps.tools,
        state_schema=AgentTurnState,
        context_schema=AgentContext,
        middleware=[
            prompt_con_perfil_y_ruta,
            herramientas_por_ruta,
            SummarizationMiddleware(
                model=deps.summary_model or deps.model,
                trigger=("tokens", s.summary_trigger_tokens),
                keep=("messages", s.summary_keep_messages),
            ),
            verificar_cifras,
            ModelRetryMiddleware(max_retries=2, initial_delay=1.5),
            ModelCallLimitMiddleware(run_limit=6, exit_behavior="end"),
            ToolCallLimitMiddleware(run_limit=6),
        ],
        name="agente",
    )

    # ---- nodos del grafo exterior ----------------------------------------------
    def router_node(state: ChatState, runtime: Runtime[AgentContext]) -> dict:
        text = last_human_text(state["messages"])
        decision: RouteDecision = route(text, deps.router_model, s.router_mode)
        d = decision.model_dump()
        return {"ruta": d, "rutas": [d]}

    def directo_node(state: ChatState, runtime: Runtime[AgentContext]) -> dict:
        profile, uid = _profile(runtime)
        system = render_system_prompt(template, state.get("ruta"), profile, uid, cat)
        history = trim_messages(
            [
                m
                for m in state["messages"]
                if m.type in ("human", "ai") and not getattr(m, "tool_calls", None) and not es_aviso_verificador(m)
            ],
            max_tokens=s.direct_history_tokens,
            token_counter="approximate",
            strategy="last",
            start_on="human",
        )
        reply = deps.model.invoke([SystemMessage(system), *history])
        return {"messages": [reply]}

    def after_router(state: ChatState) -> str:
        return "directo" if (state.get("ruta") or {}).get("ruta") == "directo" else "agente"

    g = StateGraph(ChatState, context_schema=AgentContext)
    g.add_node("router", router_node)
    g.add_node("directo", directo_node)
    g.add_node("agente", agent)
    g.add_edge(START, "router")
    g.add_conditional_edges("router", after_router, {"directo": "directo", "agente": "agente"})
    g.add_edge("directo", END)
    g.add_edge("agente", END)
    return g.compile(checkpointer=checkpointer, store=store, name="riopaila_agente")

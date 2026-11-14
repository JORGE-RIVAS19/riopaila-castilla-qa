"""Ensamble del agente y ejecución de turnos con eventos para el frontend.

La API (``api/main.py``) solo traduce HTTP ↔ estos métodos. Aquí viven:
la construcción de dependencias, el *streaming* de eventos tipados (ruta,
herramientas, tokens, fuentes, blindaje, final) y la traza JSONL de cada turno.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from riopaila_qa.agent import memory
from riopaila_qa.agent.embeddings import get_embeddings
from riopaila_qa.agent.graph import AgentDeps, build_graph, es_aviso_verificador, es_mensaje_real_del_usuario
from riopaila_qa.agent.settings import AgentSettings, get_agent_settings
from riopaila_qa.agent.tools import AgentContext, build_tools
from riopaila_qa.config import LLMSettings, Paths
from riopaila_qa.llm import TASK_SAMPLING, get_chat_model, model_name
from riopaila_qa.rag.documents import load_adversarial_chunks, load_corpus_chunks
from riopaila_qa.rag.index import index_info
from riopaila_qa.rag.retriever import HybridRetriever
from riopaila_qa.structured import load_indicadores

STREAM_NODES = {"model", "directo"}  # solo estos nodos emiten tokens al usuario
SUMMARY_PREFIX = "Here is a summary of the conversation to date:"


def is_summary(m: object) -> bool:
    """Mensaje que inserta SummarizationMiddleware en lugar del historial antiguo."""
    return isinstance(m, HumanMessage) and (m.additional_kwargs or {}).get("lc_source") == "summarization"


def message_text(msg: Any) -> str:
    """Texto plano de un mensaje (Gemini 3 devuelve el contenido como lista de bloques)."""
    content = getattr(msg, "content", msg)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content or "")


def friendly_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    low = text.lower()
    if "429" in low or "quota" in low or "resource_exhausted" in low:
        return "El proveedor del LLM respondió 429 (cuota agotada). Espera un minuto o cambia de modelo/clave."
    if "503" in low or "unavailable" in low or "overloaded" in low:
        return "El modelo está saturado (503). Reintenta en unos segundos o cambia GEMINI_MODEL."
    if "connect" in low and ("11434" in low or "ollama" in low):
        return "No hay conexión con Ollama (http://localhost:11434). Abre Ollama o cambia LLM_PROVIDER."
    if "api_key" in low or "api key" in low or "permission" in low:
        return "La API key no es válida o falta en el .env."
    return f"Error del agente: {text[:300]}"


@dataclass
class TurnTrace:
    """Registro estructurado de un turno (equivalente local a la traza de LangSmith)."""

    turn_id: str
    user_id: str
    thread_id: str
    pregunta: str
    inicio: float = field(default_factory=time.perf_counter)
    ruta: dict | None = None
    herramientas: list[dict] = field(default_factory=list)
    fuentes: list[dict] = field(default_factory=list)
    blindaje: list[dict] = field(default_factory=list)
    respuesta: str = ""
    error: str | None = None
    latencia_ms: float = 0.0
    resumen: bool = False  # True si SummarizationMiddleware compactó el historial en este turno
    verificacion: bool = False  # True si el verificador de cifras obligó a rehacer la respuesta


class AgentService:
    """Dependencias vivas del agente durante la vida del proceso del backend."""

    def __init__(self, settings: AgentSettings | None = None, fake_llm: bool | None = None):
        self.settings = settings or get_agent_settings()
        self.llm_settings = LLMSettings()
        self.fake = fake_llm if fake_llm is not None else os.getenv("AGENT_FAKE_LLM", "0") == "1"
        self.paths = Paths()
        self.embeddings, self.dims, self.embed_model = get_embeddings(self.settings)
        chunks, self.clean_stats = load_corpus_chunks(self.paths)
        if self.settings.include_adversarial:
            chunks += load_adversarial_chunks(self.settings.adversarial_dir)
        self.chunks = chunks
        self.index = index_info(self.settings)
        self.retriever = (
            HybridRetriever(chunks, self.embeddings, self.settings) if self.index.get("disponible") else None
        )
        self.indicadores = load_indicadores(self.settings.structured_csv)
        self.tools = build_tools(self.retriever, self.indicadores)
        self.checkpointer = memory.open_checkpointer(self.settings)
        self.store = memory.open_store(self.settings)
        self.model, self.router_model = self._models()
        self.graph = build_graph(
            AgentDeps(self.model, self.tools, self.indicadores, self.settings, router_model=self.router_model),
            checkpointer=self.checkpointer,
            store=self.store,
        )
        self.settings.trace_dir.mkdir(parents=True, exist_ok=True)

    def _models(self):
        if self.fake:
            from riopaila_qa.agent.fakes import ScriptedToolModel

            return ScriptedToolModel(), None
        model = get_chat_model(self.llm_settings, provider=self.settings.provider, sampling=TASK_SAMPLING["qa"])
        router = None
        if self.settings.router_mode != "reglas":
            router = get_chat_model(
                self.llm_settings,
                provider=self.settings.router_provider or self.settings.provider,
                sampling=TASK_SAMPLING["extraccion"],
            )
        return model, router

    # ---- información para la app -------------------------------------------------
    def health(self) -> dict:
        provider = "fake" if self.fake else self.settings.provider
        return {
            "estado": "ok",
            "llm": {
                "proveedor": provider,
                "modelo": "scripted" if self.fake else model_name(self.llm_settings, provider),
            },
            "router": self.settings.router_mode,
            "embeddings": self.embed_model,
            "indice": self.index,
            "limpieza_chunks": self.clean_stats,
            "memoria": {
                "checkpointer": str(self.settings.checkpoints_db.name),
                "store": str(self.settings.store_db.name),
            },
            "langsmith": {
                "activo": os.getenv("LANGSMITH_TRACING", "").lower() == "true" and bool(os.getenv("LANGSMITH_API_KEY")),
                "proyecto": os.getenv("LANGSMITH_PROJECT", ""),
            },
            "indicadores": len(self.indicadores),
        }

    def config(self, thread_id: str, user_id: str, extra: dict | None = None) -> dict:
        return {
            "configurable": {"thread_id": thread_id},
            "run_name": "turno_agente_riopaila",
            "tags": ["taaml", "grupo3", "modulo2"],
            "metadata": {"user_id": user_id, "thread_id": thread_id, **(extra or {})},
        }

    # ---- un turno con streaming -------------------------------------------------
    def stream_turn(self, message: str, thread_id: str | None, user_id: str) -> Iterator[dict]:
        """Ejecuta un turno y produce eventos tipados para el frontend (SSE)."""
        user_id = memory.normalize_user_id(user_id)
        thread_id = thread_id or str(uuid.uuid4())
        trace = TurnTrace(str(uuid.uuid4()), user_id, thread_id, message)
        yield {"type": "start", "thread_id": thread_id, "user_id": user_id, "turn_id": trace.turn_id}
        memory.touch_thread(self.store, user_id, thread_id, message)
        ctx = AgentContext(user_id=user_id, thread_id=thread_id)
        tool_t0: dict[str, float] = {}
        tool_args: dict[str, dict] = {}
        streamed = False
        try:
            for ns, mode, chunk in self.graph.stream(
                {"messages": [HumanMessage(message)]},
                self.config(thread_id, user_id),
                context=ctx,
                stream_mode=["updates", "messages"],
                subgraphs=True,
            ):
                if mode == "messages":
                    msg, meta = chunk
                    if meta.get("langgraph_node") in STREAM_NODES and isinstance(msg, AIMessageChunk | AIMessage):
                        text = message_text(msg)
                        if text:
                            streamed = True
                            yield {"type": "token", "text": text}
                    continue
                for node, update in (chunk or {}).items():
                    if not isinstance(update, dict):
                        continue
                    if not ns and node == "agente":
                        continue  # el resumen del subgrafo repite mensajes ya emitidos desde dentro
                    if node.startswith("verificar_cifras"):
                        aviso = next((m for m in update.get("messages", []) or [] if es_aviso_verificador(m)), None)
                        if aviso is not None:
                            # El borrador traía números que no salieron de una herramienta: se descarta.
                            trace.verificacion = True
                            yield {"type": "verificacion"}
                        continue
                    if "Summarization" in node:
                        # SummarizationMiddleware reescribe el historial (resumen + últimos mensajes):
                        # esos mensajes son de turnos anteriores y no deben volver a aparecer como eventos.
                        if any(is_summary(m) for m in update.get("messages", []) or []):
                            trace.resumen = True
                            yield {"type": "summary"}
                        continue
                    if node == "router" and update.get("ruta"):
                        trace.ruta = update["ruta"]
                        yield {"type": "route", **update["ruta"]}
                    for m in update.get("messages", []) or []:
                        if isinstance(m, AIMessage) and m.tool_calls:
                            for tc in m.tool_calls:
                                tool_t0[tc["id"]] = time.perf_counter()
                                tool_args[tc["id"]] = tc["args"]
                                yield {"type": "tool_start", "id": tc["id"], "name": tc["name"], "args": tc["args"]}
                        elif isinstance(m, ToolMessage):
                            ms = (time.perf_counter() - tool_t0.get(m.tool_call_id, time.perf_counter())) * 1000
                            art = m.artifact if isinstance(m.artifact, dict) else {}
                            info = {
                                "name": m.name,
                                "args": tool_args.get(m.tool_call_id, {}),
                                "latency_ms": round(ms, 1),
                                "status": m.status,
                            }
                            trace.herramientas.append(info)
                            if m.name == "buscar_documentos":
                                trace.fuentes.extend(art.get("hits", []))
                                trace.blindaje.extend(art.get("shield", []))
                            yield {
                                "type": "tool_end",
                                "id": m.tool_call_id,
                                "name": m.name,
                                "latency_ms": round(ms, 1),
                                "status": m.status,
                                "artifact": art,
                            }
            state = self.graph.get_state(self.config(thread_id, user_id))
            last = next((m for m in reversed(state.values.get("messages", [])) if isinstance(m, AIMessage)), None)
            trace.respuesta = message_text(last) if last else ""
            if not streamed and trace.respuesta:
                yield {"type": "token", "text": trace.respuesta}
        except Exception as exc:  # el error llega al usuario como evento, no como 500
            trace.error = friendly_error(exc)
            yield {"type": "error", "message": trace.error}
        trace.latencia_ms = round((time.perf_counter() - trace.inicio) * 1000, 1)
        memory.touch_thread(self.store, user_id, thread_id)
        self._write_trace(trace)
        yield {
            "type": "final",
            "thread_id": thread_id,
            "content": trace.respuesta,
            "ruta": trace.ruta,
            "fuentes": trace.fuentes,
            "blindaje": trace.blindaje,
            "herramientas": trace.herramientas,
            "latency_ms": trace.latencia_ms,
            "error": trace.error,
            "resumen": trace.resumen,
            "verificacion": trace.verificacion,
        }

    def run_turn(self, message: str, thread_id: str | None, user_id: str) -> dict:
        """Versión sin streaming (pruebas, curl, evaluación)."""
        final: dict = {}
        tokens: list[str] = []
        for ev in self.stream_turn(message, thread_id, user_id):
            if ev["type"] == "token":
                tokens.append(ev["text"])
            if ev["type"] == "final":
                final = ev
        final["streamed_text"] = "".join(tokens)
        return final

    def _write_trace(self, t: TurnTrace) -> None:
        rec = {k: v for k, v in t.__dict__.items() if k != "inicio"}
        rec["fuentes"] = [{k: f.get(k) for k in ("n", "titulo", "url", "chunk_id")} for f in t.fuentes]
        rec["ts"] = memory.now_iso()
        with (self.settings.trace_dir / "trazas.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---- hilos, historia y time travel --------------------------------------------
    def thread_messages(self, thread_id: str, user_id: str) -> dict:
        state = self.graph.get_state(self.config(thread_id, user_id))
        values = state.values or {}
        rutas = list(values.get("rutas", []) or [])
        messages = values.get("messages", []) or []
        # Tras un resumen, el estado solo conserva los últimos turnos: las rutas se alinean desde el final.
        humanos = sum(1 for m in messages if es_mensaje_real_del_usuario(m))
        out, turn = [], max(len(rutas) - humanos, 0) - 1
        for m in messages:
            if es_aviso_verificador(m):
                continue  # mensaje interno del verificador de cifras
            if is_summary(m):
                text = message_text(m).removeprefix(SUMMARY_PREFIX).strip()
                out.append({"role": "summary", "content": text, "id": m.id})
            elif isinstance(m, HumanMessage):
                turn += 1
                out.append({"role": "user", "content": message_text(m), "id": m.id})
            elif isinstance(m, AIMessage):
                if m.tool_calls:
                    out.append(
                        {
                            "role": "tool_call",
                            "id": m.id,
                            "tool_calls": [
                                {"id": tc["id"], "name": tc["name"], "args": tc["args"]} for tc in m.tool_calls
                            ],
                        }
                    )
                text = message_text(m)
                if text:
                    out.append(
                        {
                            "role": "assistant",
                            "content": text,
                            "id": m.id,
                            "ruta": rutas[turn] if 0 <= turn < len(rutas) else None,
                        }
                    )
            elif isinstance(m, ToolMessage):
                out.append(
                    {
                        "role": "tool",
                        "name": m.name,
                        "id": m.id,
                        "tool_call_id": m.tool_call_id,
                        "artifact": m.artifact if isinstance(m.artifact, dict) else None,
                    }
                )
        return {
            "thread_id": thread_id,
            "messages": out,
            "turnos": len(rutas),
            "checkpoint_id": (state.config or {}).get("configurable", {}).get("checkpoint_id"),
        }

    def checkpoints(self, thread_id: str, user_id: str, limit: int = 30) -> list[dict]:
        out = []
        for snap in self.graph.get_state_history(self.config(thread_id, user_id), limit=limit):
            conf = snap.config.get("configurable", {})
            out.append(
                {
                    "checkpoint_id": conf.get("checkpoint_id"),
                    "step": snap.metadata.get("step") if snap.metadata else None,
                    "source": snap.metadata.get("source") if snap.metadata else None,
                    "mensajes": len(snap.values.get("messages", [])) if snap.values else 0,
                    "siguiente": list(snap.next),
                    "creado": snap.created_at,
                }
            )
        return out

    def fork(self, thread_id: str, checkpoint_id: str, user_id: str) -> str:
        """Time travel: crea un hilo nuevo a partir de un checkpoint anterior."""
        user_id = memory.normalize_user_id(user_id)
        cfg = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
        snap = self.graph.get_state(cfg)
        new_id = str(uuid.uuid4())
        self.graph.update_state({"configurable": {"thread_id": new_id}}, snap.values, as_node="directo")
        info = memory.touch_thread(self.store, user_id, new_id)
        info["titulo"] = f"Bifurcación de {thread_id[:8]}"
        self.store.put(memory.threads_ns(user_id), new_id, info)
        return new_id

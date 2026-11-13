"""Backend del agente (FastAPI). El frontend habla con esta API por HTTP + SSE.

Ejecutar en desarrollo::

    uv run fastapi dev api/main.py        # http://127.0.0.1:8000  ·  docs en /docs

El frontend nunca llama al modelo: todo pasa por ``/api/chat/stream``, que
ejecuta el grafo LangGraph y emite eventos *Server-Sent Events*.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from api.schemas import (
    ChatRequest,
    ChatResponse,
    Checkpoint,
    ForkRequest,
    ForkResponse,
    RouteRequest,
    ThreadDetail,
    ThreadSummary,
)
from riopaila_qa.agent import memory
from riopaila_qa.agent.router import route_by_rules
from riopaila_qa.agent.service import AgentService
from riopaila_qa.agent.settings import get_agent_settings
from riopaila_qa.config import ROOT_DIR

EVAL_DIR = ROOT_DIR / "docs" / "evaluacion"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Las pruebas inyectan un servicio con modelos falsos en app.state.agent_override.
    app.state.agent = getattr(app.state, "agent_override", None) or AgentService()
    yield
    from riopaila_qa.rag.index import close_clients

    close_clients()


app = FastAPI(
    title="Riopaila Castilla · Agente conversacional (TAAML M2 · Grupo 3)",
    version="2.0.0",
    description="Agente con memoria, RAG sobre Qdrant, herramienta CSV, router y blindaje.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_agent_settings().cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)


def agent(request: Request) -> AgentService:
    return request.app.state.agent


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"[:400]})


# ---- estado ---------------------------------------------------------------------


@app.get("/api/health", tags=["estado"])
def health(request: Request) -> dict:
    """Proveedor del LLM, embeddings, índice Qdrant, memoria y LangSmith."""
    return agent(request).health()


@app.get("/api/graph", tags=["estado"])
def graph_mermaid(request: Request) -> dict:
    """Diagrama Mermaid del grafo compilado (router → directo | agente)."""
    return {"mermaid": agent(request).graph.get_graph(xray=1).draw_mermaid()}


# ---- conversación ---------------------------------------------------------------


def sse(events: Iterator[dict]) -> Iterator[str]:
    for ev in events:
        yield f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"


@app.post("/api/chat/stream", tags=["chat"])
def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
    """Turno con *streaming* (SSE): eventos ``start, route, tool_start, tool_end, token, error, final``."""
    events = agent(request).stream_turn(body.mensaje, body.thread_id, body.user_id)
    return StreamingResponse(
        sse(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat", tags=["chat"], response_model=ChatResponse)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """Turno sin streaming (útil para curl y pruebas)."""
    res = agent(request).run_turn(body.mensaje, body.thread_id, body.user_id)
    return ChatResponse(**{k: res.get(k) for k in ChatResponse.model_fields if k in res})


@app.post("/api/route", tags=["chat"])
def preview_route(body: RouteRequest) -> dict:
    """Decisión del router por reglas, sin ejecutar el agente (para depurar el criterio 2.3)."""
    return route_by_rules(body.mensaje).model_dump()


# ---- hilos (memoria de corto plazo) -----------------------------------------------


@app.get("/api/threads", tags=["hilos"], response_model=list[ThreadSummary])
def threads(request: Request, user_id: str = Query("invitado")) -> list[ThreadSummary]:
    uid = memory.normalize_user_id(user_id)
    return [ThreadSummary(**t) for t in memory.list_threads(agent(request).store, uid)]


@app.get("/api/threads/{thread_id}", tags=["hilos"], response_model=ThreadDetail)
def thread_detail(thread_id: str, request: Request, user_id: str = Query("invitado")) -> ThreadDetail:
    """Mensajes del hilo leídos del checkpointer (sobreviven al reinicio del backend)."""
    return ThreadDetail(**agent(request).thread_messages(thread_id, memory.normalize_user_id(user_id)))


@app.delete("/api/threads/{thread_id}", tags=["hilos"])
def delete_thread(thread_id: str, request: Request, user_id: str = Query("invitado")) -> dict:
    svc = agent(request)
    memory.forget_thread(svc.store, svc.checkpointer, memory.normalize_user_id(user_id), thread_id)
    return {"borrado": thread_id}


@app.get("/api/threads/{thread_id}/checkpoints", tags=["hilos"], response_model=list[Checkpoint])
def checkpoints(thread_id: str, request: Request, user_id: str = Query("invitado")) -> list[Checkpoint]:
    """*Time travel*: historial de checkpoints del hilo."""
    return [Checkpoint(**c) for c in agent(request).checkpoints(thread_id, memory.normalize_user_id(user_id))]


@app.post("/api/threads/{thread_id}/fork", tags=["hilos"], response_model=ForkResponse)
def fork(thread_id: str, body: ForkRequest, request: Request) -> ForkResponse:
    """*Time travel*: bifurca el hilo desde un checkpoint anterior."""
    return ForkResponse(thread_id=agent(request).fork(thread_id, body.checkpoint_id, body.user_id))

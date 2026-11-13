"""API FastAPI: contratos, streaming SSE, hilos, memoria, datos y RAG."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from riopaila_qa.agent.embeddings import get_embeddings
from riopaila_qa.agent.service import AgentService
from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.config import Paths
from riopaila_qa.rag import index as rag_index
from riopaila_qa.rag.documents import load_adversarial_chunks, load_corpus_chunks


@pytest.fixture()
def client(tmp_path: Path):
    from api.main import app

    s = replace(
        AgentSettings(),
        provider="fake",
        router_mode="reglas",
        embed_provider="fake",
        qdrant_url="",
        qdrant_path=tmp_path / "q",
        memory_dir=tmp_path / "m",
        trace_dir=tmp_path / "logs",
    )
    chunks, _ = load_corpus_chunks(Paths())
    chunks += load_adversarial_chunks(s.adversarial_dir)
    emb, dims, name = get_embeddings(s)
    rag_index.build_index(chunks, emb, dims, name, s)
    app.state.agent_override = AgentService(s, fake_llm=True)
    with TestClient(app) as c:
        yield c
    app.state.agent_override = None
    rag_index.close_clients()


def sse_events(text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data:")]


def test_health(client: TestClient):
    h = client.get("/api/health").json()
    assert h["estado"] == "ok" and h["indice"]["disponible"] and h["indicadores"] >= 30


def test_chat_stream(client: TestClient):
    r = client.post("/api/chat/stream", json={"mensaje": "Hola", "user_id": "Ana"})
    assert r.headers["content-type"].startswith("text/event-stream")
    kinds = [e["type"] for e in sse_events(r.text)]
    assert kinds[0] == "start" and "route" in kinds and kinds[-1] == "final"


def test_chat_valida_entrada(client: TestClient):
    assert client.post("/api/chat", json={"mensaje": "", "user_id": "ana"}).status_code == 422


def test_chat_sin_stream(client: TestClient):
    body = client.post("/api/chat", json={"mensaje": "¿Cuál fue la utilidad neta de 2022?", "user_id": "ana"}).json()
    assert body["ruta"]["ruta"] == "datos" and "93.241" in body["content"]


def test_hilos_y_time_travel(client: TestClient):
    events = sse_events(client.post("/api/chat/stream", json={"mensaje": "Hola", "user_id": "ana"}).text)
    tid = events[0]["thread_id"]
    assert any(t["thread_id"] == tid for t in client.get("/api/threads", params={"user_id": "ana"}).json())
    detail = client.get(f"/api/threads/{tid}", params={"user_id": "ana"}).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    cps = client.get(f"/api/threads/{tid}/checkpoints", params={"user_id": "ana"}).json()
    cp = next(c for c in cps if c["mensajes"] == 2)
    fork = client.post(f"/api/threads/{tid}/fork", json={"checkpoint_id": cp["checkpoint_id"], "user_id": "ana"}).json()
    assert fork["thread_id"] != tid
    assert client.delete(f"/api/threads/{tid}", params={"user_id": "ana"}).json()["borrado"] == tid


def test_memoria_store(client: TestClient):
    client.post("/api/chat", json={"mensaje": "Me llamo Ana y trabajo en Carvajal", "user_id": "ana"})
    facts = {f["clave"]: f["valor"] for f in client.get("/api/users/ana/memory").json()}
    assert facts == {"nombre": "Ana", "empresa": "Carvajal"}
    client.put("/api/users/ana/memory", json={"clave": "cargo", "valor": "analista"})
    client.delete("/api/users/ana/memory/nombre")
    assert {f["clave"] for f in client.get("/api/users/ana/memory").json()} == {"empresa", "cargo"}


def test_datos_y_busqueda(client: TestClient):
    rows = client.get("/api/datos/indicadores").json()
    assert len(rows) >= 30 and rows[0]["valor_legible"]
    res = client.post("/api/rag/search", json={"consulta": "bonos de carbono", "k": 3, "modo": "hibrida"}).json()
    assert len(res["hits"]) == 3 and "bonos" in res["hits"][0]["chunk"]["url"]
    assert client.get("/api/eval/retrieval").status_code in (200, 404)

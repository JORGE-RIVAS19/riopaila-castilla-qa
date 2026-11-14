"""Servicio de turnos: eventos de streaming, trazas y persistencia tras reiniciar."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from riopaila_qa.agent.embeddings import get_embeddings
from riopaila_qa.agent.service import AgentService, friendly_error, message_text
from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.config import Paths
from riopaila_qa.rag import index as rag_index
from riopaila_qa.rag.documents import load_adversarial_chunks, load_corpus_chunks


@pytest.fixture()
def settings(tmp_path: Path) -> AgentSettings:
    return replace(
        AgentSettings(),
        provider="fake",
        router_mode="reglas",
        embed_provider="fake",
        qdrant_url="",
        qdrant_path=tmp_path / "q",
        memory_dir=tmp_path / "m",
        trace_dir=tmp_path / "logs",
    )


@pytest.fixture()
def service(settings: AgentSettings):
    chunks, _ = load_corpus_chunks(Paths())
    chunks += load_adversarial_chunks(settings.adversarial_dir)
    emb, dims, name = get_embeddings(settings)
    rag_index.build_index(chunks, emb, dims, name, settings)
    yield AgentService(settings, fake_llm=True)
    rag_index.close_clients()


def test_eventos_del_stream(service: AgentService):
    events = list(service.stream_turn("¿Qué dice el corpus sobre la política de calidad?", None, "Ana"))
    kinds = [e["type"] for e in events]
    assert kinds[0] == "start" and kinds[1] == "route" and kinds[-1] == "final"
    assert "tool_start" in kinds and "tool_end" in kinds and "token" in kinds
    final = events[-1]
    assert final["fuentes"] and final["blindaje"] and final["error"] is None


def test_traza_jsonl(service: AgentService, settings: AgentSettings):
    service.run_turn("¿Cuál fue la utilidad neta de 2022?", "t1", "ana")
    rec = json.loads((settings.trace_dir / "trazas.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rec["ruta"]["ruta"] == "datos" and rec["herramientas"][0]["name"] == "consultar_indicadores"
    assert rec["herramientas"][0]["args"]["anio"] == 2022


def test_hilo_sobrevive_al_reinicio(settings: AgentSettings, service: AgentService):
    service.run_turn("Hola", "persistente", "ana")
    rag_index.close_clients()
    nuevo = AgentService(settings, fake_llm=True)  # “reinicio” del backend: mismo disco, proceso nuevo
    roles = [m["role"] for m in nuevo.thread_messages("persistente", "ana")["messages"]]
    assert roles[:2] == ["user", "assistant"]


def test_time_travel_fork(service: AgentService):
    service.run_turn("Hola", "origen", "ana")
    service.run_turn("¿Cuál fue la utilidad neta de 2022?", "origen", "ana")
    cps = service.checkpoints("origen", "ana")
    con_mensajes = [c for c in cps if c["mensajes"] == 2]
    nuevo = service.fork("origen", con_mensajes[0]["checkpoint_id"], "ana")
    assert service.thread_messages(nuevo, "ana")["messages"][0]["content"] == "Hola"


def test_message_text_bloques_gemini():
    class M:
        content = [{"type": "text", "text": "Hola "}, {"type": "text", "text": "mundo"}]

    assert message_text(M()) == "Hola mundo"


def test_errores_amigables():
    assert "429" in friendly_error(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert "Ollama" in friendly_error(ConnectionError("connect to localhost:11434 failed"))


def test_resumen_no_rompe_el_hilo(settings: AgentSettings):
    """Con un umbral bajo, SummarizationMiddleware compacta el historial: el hilo lo muestra como resumen."""
    chunks, _ = load_corpus_chunks(Paths())
    emb, dims, name = get_embeddings(settings)
    rag_index.build_index(chunks, emb, dims, name, settings)
    svc = AgentService(replace(settings, summary_trigger_tokens=300, summary_keep_messages=2), fake_llm=True)
    try:
        preguntas = [
            "¿Qué dice el corpus sobre la política de calidad?",
            "¿Cuál fue la utilidad neta de 2022?",
            "¿Qué dice el corpus sobre la cogeneración de energía?",
        ]
        eventos = []
        for p in preguntas:
            eventos.append(list(svc.stream_turn(p, "largo", "ana")))
        todos = [e for turno in eventos for e in turno]
        assert any(e["type"] == "summary" for e in todos)
        assert any(turno[-1]["resumen"] for turno in eventos)
        # Las herramientas de turnos viejos no se re-emiten en el turno que resume.
        for turno in eventos:
            ids_start = [e["id"] for e in turno if e["type"] == "tool_start"]
            assert len(ids_start) == len(set(ids_start)) <= 2

        hilo = svc.thread_messages("largo", "ana")
        roles = [m["role"] for m in hilo["messages"]]
        assert "summary" in roles
        resumen = next(m for m in hilo["messages"] if m["role"] == "summary")
        assert not resumen["content"].startswith("Here is a summary")
        usuarios = [m for m in hilo["messages"] if m["role"] == "user"]
        assert usuarios[-1]["content"] == preguntas[-1]
        ultima = [m for m in hilo["messages"] if m["role"] == "assistant"][-1]
        assert ultima["ruta"]["ruta"] == "rag"
    finally:
        rag_index.close_clients()

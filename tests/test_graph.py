"""Grafo LangGraph con un LLM simulado: rutas, memoria entre hilos, datos y blindaje."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from riopaila_qa.agent import memory
from riopaila_qa.agent.embeddings import get_embeddings
from riopaila_qa.agent.fakes import ScriptedToolModel
from riopaila_qa.agent.graph import AgentDeps, build_graph
from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.agent.tools import AgentContext, build_tools
from riopaila_qa.config import Paths
from riopaila_qa.rag import index as rag_index
from riopaila_qa.rag.documents import load_adversarial_chunks, load_corpus_chunks
from riopaila_qa.rag.retriever import HybridRetriever
from riopaila_qa.structured import load_indicadores


@pytest.fixture()
def graph_and_store(tmp_path: Path):
    s = replace(
        AgentSettings(),
        embed_provider="fake",
        router_mode="reglas",
        qdrant_url="",
        qdrant_path=tmp_path / "q",
        memory_dir=tmp_path / "m",
    )
    chunks, _ = load_corpus_chunks(Paths())
    chunks += load_adversarial_chunks(s.adversarial_dir)
    emb, dims, name = get_embeddings(s)
    rag_index.build_index(chunks, emb, dims, name, s)
    inds = load_indicadores(s.structured_csv)
    tools = build_tools(HybridRetriever(chunks, emb, s), inds)
    store = memory.open_store(s)
    g = build_graph(AgentDeps(ScriptedToolModel(), tools, inds, s), memory.open_checkpointer(s), store)
    yield g, store
    rag_index.close_clients()


def ask(g, text: str, thread: str, user: str = "ana") -> dict:
    return g.invoke(
        {"messages": [{"role": "user", "content": text}]},
        {"configurable": {"thread_id": thread}},
        context=AgentContext(user_id=user, thread_id=thread),
    )


def tool_names(state: dict) -> list[str]:
    return [m.name for m in state["messages"] if m.type == "tool"]


def test_saludo_no_toca_herramientas(graph_and_store):
    g, _ = graph_and_store
    out = ask(g, "Hola", "t0")
    assert out["ruta"]["ruta"] == "directo" and tool_names(out) == []


def test_memoria_entre_hilos(graph_and_store):
    g, store = graph_and_store
    ask(g, "Me llamo Ana y trabajo en Carvajal", "t1")
    assert {f["clave"] for f in memory.load_profile(store, "ana")} == {"nombre", "empresa"}
    out = ask(g, "¿Dónde trabajo?", "t2")
    assert "Carvajal" in out["messages"][-1].content


def test_hilo_acumula_rutas(graph_and_store):
    g, _ = graph_and_store
    ask(g, "Hola", "t3")
    out = ask(g, "¿Cuál fue la utilidad neta de 2022?", "t3")
    assert [r["ruta"] for r in out["rutas"]] == ["directo", "datos"]


def test_datos_con_herramienta(graph_and_store):
    g, _ = graph_and_store
    out = ask(g, "¿Cuánto vendió Riopaila en energía en el tercer trimestre de 2023?", "t4")
    assert tool_names(out) == ["consultar_indicadores"] and "21.342" in out["messages"][-1].content


def test_rag_con_blindaje(graph_and_store):
    g, _ = graph_and_store
    out = ask(g, "¿Qué dice el corpus sobre la política de calidad?", "t5")
    tool_msg = next(m for m in out["messages"] if m.type == "tool")
    assert tool_msg.artifact["shield"] and "1990" not in out["messages"][-1].content


class _ModeloQueRestaDeMemoria(ScriptedToolModel):
    """Primero responde con una resta hecha "de memoria"; tras el aviso, usa comparar_cifras."""

    def _reply(self, messages):
        from langchain_core.messages import AIMessage, ToolMessage

        if any(isinstance(m, ToolMessage) and m.name == "comparar_cifras" for m in messages):
            return AIMessage("La utilidad neta bajó 30.241 millones de COP (93.241 en 2022 frente a 63.000 en 2023).")
        avisado = any(
            (getattr(m, "additional_kwargs", {}) or {}).get("lc_source") == "verificador_cifras" for m in messages
        )
        if not avisado:
            return AIMessage("La utilidad neta bajó 30.241 millones de COP.")
        args = {
            "valor_a": 93241,
            "etiqueta_a": "2022",
            "valor_b": 63000,
            "etiqueta_b": "2023",
            "unidad": "millones_cop",
        }
        return AIMessage("", tool_calls=[{"name": "comparar_cifras", "args": args, "id": "cmp1"}])


def test_verificador_obliga_a_usar_comparar_cifras(tmp_path: Path):
    s = replace(
        AgentSettings(),
        embed_provider="fake",
        router_mode="reglas",
        qdrant_url="",
        qdrant_path=tmp_path / "q",
        memory_dir=tmp_path / "m",
    )
    chunks, _ = load_corpus_chunks(Paths())
    emb, dims, name = get_embeddings(s)
    rag_index.build_index(chunks, emb, dims, name, s)
    inds = load_indicadores(s.structured_csv)
    tools = build_tools(HybridRetriever(chunks, emb, s), inds)
    g = build_graph(
        AgentDeps(_ModeloQueRestaDeMemoria(), tools, inds, s), memory.open_checkpointer(s), memory.open_store(s)
    )
    try:
        out = ask(g, "¿Cuánto bajó la utilidad neta de 2022 a 2023?", "v1")
        assert out["ruta"]["ruta"] in ("datos", "mixto")
        assert "comparar_cifras" in tool_names(out)
        textos_ai = [m.content for m in out["messages"] if m.type == "ai" and m.content]
        assert textos_ai == ["La utilidad neta bajó 30.241 millones de COP (93.241 en 2022 frente a 63.000 en 2023)."]
    finally:
        rag_index.close_clients()

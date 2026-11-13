"""El LLM simulado imita el bucle ReAct: pide la herramienta y luego redacta."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, ToolMessage

from riopaila_qa.agent.fakes import ScriptedToolModel


def test_pide_herramienta_y_luego_responde():
    m = ScriptedToolModel().bind_tools([{"name": "consultar_indicadores"}])
    first = m.invoke([HumanMessage("¿Utilidad neta de 2022?")])
    assert first.tool_calls[0]["name"] == "consultar_indicadores" and first.tool_calls[0]["args"]["anio"] == 2022
    obs = ToolMessage('{"filas": []}', tool_call_id=first.tool_calls[0]["id"], name="consultar_indicadores")
    final = m.invoke([HumanMessage("¿Utilidad neta de 2022?"), first, obs])
    assert "No encuentro" in final.content


def test_sin_herramientas_saluda():
    assert "Hola" in ScriptedToolModel().invoke([HumanMessage("hola")]).content

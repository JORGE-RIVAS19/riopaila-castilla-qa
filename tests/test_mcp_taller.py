"""Servidor MCP propio (ítem 3.4): contrato con OpenClaw y recorrido completo contra el API con la muestra."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from riopaila_qa.agent.service import AgentService
from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.mcp_taller import server as mcp
from riopaila_qa.taller.base import cargar_csv
from riopaila_qa.taller.config import MUESTRA_DIR


def test_herramientas_mcp_tipadas():
    tools = {t.name: t for t in asyncio.run(mcp.servidor.list_tools())}
    assert set(tools) == {"consultar_asistente_taller", "gestionar_novedad_taller", "parte_diario_taller"}
    esquema = tools["consultar_asistente_taller"].input_schema
    assert {"mensaje", "telefono"} <= set(esquema["required"])
    assert all(t.output_schema for t in tools.values())


def test_consulta_es_de_solo_lectura_y_usa_hilo_por_numero():
    recibido = {}

    def api(request: httpx.Request) -> httpx.Response:
        recibido.update(json.loads(request.content))
        return httpx.Response(
            200, json={"content": "ok", "media": [{"ruta": "/w/media/a.png"}], "ruta": {"ruta": "manual"}}
        )

    with httpx.Client(transport=httpx.MockTransport(api), base_url="http://x") as cli:
        r = mcp._chat("diagrama del pito", "+57 300 111 2233", None, True, cli)
    assert recibido["solo_lectura"] is True and recibido["thread_id"] == "wa-573001112233"
    assert r.adjuntos == ["/w/media/a.png"] and "MEDIA:/w/media/a.png" in r.como_enviar


def test_telefono_invalido():
    with pytest.raises(ValueError):
        mcp._telefono("hola")


def test_sin_numero_responde_en_solo_lectura():
    recibido = {}

    def api(request: httpx.Request) -> httpx.Response:
        recibido.update(json.loads(request.content))
        return httpx.Response(200, json={"content": "ok"})

    with httpx.Client(transport=httpx.MockTransport(api), base_url="http://x") as cli:
        mcp._chat("registra la falla del 25375", "", None, False, cli)
    assert recibido["solo_lectura"] is True and recibido["thread_id"] == "wa-desconocido"


@pytest.fixture()
def api_taller(tmp_path: Path, monkeypatch):
    from api.main import app

    db = tmp_path / "t.duckdb"
    cargar_csv(MUESTRA_DIR / "equipos.csv", MUESTRA_DIR / "materiales.csv", MUESTRA_DIR / "consumos.csv", db)
    monkeypatch.setenv("TALLER_DB", str(db))
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("TALLER_NOVEDADES_DB", str(tmp_path / "nov.sqlite"))
    monkeypatch.setenv("MANUALES_DIR", str(tmp_path / "sin_manuales"))
    monkeypatch.setenv("TALLER_ROLES", "573001112233=tecnico")
    s = replace(
        AgentSettings(),
        router_mode="reglas",
        embed_provider="fake",
        qdrant_path=tmp_path / "q",
        memory_dir=tmp_path / "m",
        trace_dir=tmp_path / "logs",
    )
    app.state.agent_override = AgentService(s, fake_llm=True)
    with TestClient(app, base_url="http://127.0.0.1:8000") as c:
        yield c
    app.state.agent_override = None


def test_recorrido_whatsapp_mcp_api_agente(api_taller, monkeypatch):
    monkeypatch.setattr(mcp, "API_URL", "http://127.0.0.1:8000")
    assert api_taller.get("/api/health").json()["taller"]["herramientas"] == 17
    r = mcp._chat("qué equipos gastaron más este trimestre? hazme el ranking", "+573009998877", None, True, api_taller)
    assert r.ruta == "taller" and "ranking_gasto_equipos" in r.herramientas and Path(r.adjuntos[0]).exists()
    # Un número de la lista blanca, por la herramienta de escritura: pide confirmación y luego guarda.
    eq = api_taller.get("/api/taller/resumen").json()["ranking_90d"][0]["equipo"]
    r = mcp._chat(f"el equipo {eq} se varó, regístralo", "+573001112233", None, False, api_taller)
    assert r.pendiente_confirmacion and "¿Registro esta novedad?" in r.respuesta
    r = mcp._chat("sí", "+573001112233", None, False, api_taller)
    assert "registrada" in r.respuesta
    assert api_taller.get("/api/taller/novedades").json()[0]["equipo"] == eq
    # El mismo pedido por la herramienta de solo lectura no escribe aunque el número sea del taller.
    r = mcp._chat(f"el equipo {eq} se varó, regístralo", "+573001112233", None, True, api_taller)
    assert not r.pendiente_confirmacion and len(api_taller.get("/api/taller/novedades").json()) == 1


def test_parte_diario(api_taller):
    datos = api_taller.get("/api/taller/parte-diario", params={"dias": 7}).json()
    assert "Parte del Taller Castilla" in datos["texto"] and Path(datos["media"][0]).exists()

"""Servidor MCP propio (ítem 3.4): contrato con OpenClaw y recorrido completo contra el API con la muestra."""

from __future__ import annotations

import asyncio
import csv
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


# ---- Perfiles: el visitante ve la muestra anonimizada; el personal de Riopaila, SAP real -------------------
@pytest.fixture()
def svc_perfiles(tmp_path: Path, monkeypatch):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "materiales.csv").write_text((MUESTRA_DIR / "materiales.csv").read_text("utf-8"), "utf-8")
    for nombre in ("equipos.csv", "consumos.csv"):  # la base "real" se distingue por el nombre de los equipos
        with (MUESTRA_DIR / nombre).open(encoding="utf-8", newline="") as f:
            filas = list(csv.reader(f))
        for fila in filas[1:]:
            fila[1] = f"REAL {fila[1]}"
        with (real_dir / nombre).open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(filas)
    real = tmp_path / "real.duckdb"
    cargar_csv(real_dir / "equipos.csv", real_dir / "materiales.csv", real_dir / "consumos.csv", real)
    monkeypatch.setenv("TALLER_DB", str(real))
    monkeypatch.setenv("TALLER_DB_MUESTRA", str(tmp_path / "muestra.duckdb"))  # se construye sola desde los CSV
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("TALLER_NOVEDADES_DB", str(tmp_path / "nov.sqlite"))
    monkeypatch.setenv("MANUALES_DIR", str(tmp_path / "sin_manuales"))
    monkeypatch.setenv("TALLER_ROLES", "573001112233=tecnico,573004445566=riopaila")
    s = replace(
        AgentSettings(),
        router_mode="reglas",
        embed_provider="fake",
        qdrant_path=tmp_path / "q",
        memory_dir=tmp_path / "m",
        trace_dir=tmp_path / "logs",
    )
    return AgentService(s, fake_llm=True)


def _ranking(svc: AgentService, numero: str, solo_lectura: bool = False) -> tuple[str, list[str], str]:
    eventos = list(
        svc.stream_turn(
            "qué cosechadoras gastaron más este trimestre? hazme el ranking",
            thread_id=f"wa-{numero}",
            user_id=numero,
            canal="whatsapp",
            solo_lectura=solo_lectura,
        )
    )
    final = eventos[-1]
    fin = next(e for e in eventos if e["type"] == "tool_end" and e["name"] == "ranking_gasto_equipos")
    nombres = [f["denominacion"] for f in fin["artifact"]["filas"]]
    estado = svc.graph.get_state(svc.config(f"wa-{numero}", numero)).values["messages"]
    contenido = next(str(m.content) for m in estado if getattr(m, "name", "") == "ranking_gasto_equipos")
    return final["rol"], nombres, contenido


def test_visitante_ve_la_muestra_y_el_personal_ve_sap_real(svc_perfiles):
    from riopaila_qa.taller.tools import AVISO_MUESTRA

    assert svc_perfiles.taller_info["muestra_visitantes"] is True
    rol, nombres, contenido = _ranking(svc_perfiles, "573009998877")
    assert rol == "invitado" and nombres and not any("REAL" in n for n in nombres)
    assert contenido.startswith(AVISO_MUESTRA)
    for numero, perfil in (("573001112233", "tecnico"), ("573004445566", "riopaila")):
        rol, nombres, contenido = _ranking(svc_perfiles, numero)
        assert rol == perfil and any("REAL" in n for n in nombres) and AVISO_MUESTRA not in contenido
    # La herramienta MCP de solo lectura no le quita los datos reales al técnico: solo el permiso de escribir.
    rol, nombres, _ = _ranking(svc_perfiles, "573001112233", solo_lectura=True)
    assert rol == "riopaila" and any("REAL" in n for n in nombres)


def test_perfil_riopaila_no_registra_novedades(svc_perfiles):
    eventos = list(
        svc_perfiles.stream_turn(
            "el equipo 9030 se varó, regístralo", thread_id="wa-573004445566", user_id="573004445566"
        )
    )
    assert not any(e["type"] == "interrupt" for e in eventos)
    assert "personal del taller" in eventos[-1]["content"] or eventos[-1]["pendiente"] is None

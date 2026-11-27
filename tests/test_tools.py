"""Herramientas @tool: esquema Pydantic, salida exacta y artefacto para la app."""

from __future__ import annotations

import json
from pathlib import Path

from riopaila_qa.agent.tools import build_tools
from riopaila_qa.config import ROOT_DIR
from riopaila_qa.structured import load_indicadores

CSV = ROOT_DIR / "data" / "structured" / "indicadores_riopaila.csv"


def _tools():
    return {t.name: t for t in build_tools(None, load_indicadores(CSV))}


def _call(tool, args: dict):
    msg = tool.invoke({"type": "tool_call", "id": "t1", "name": tool.name, "args": args})
    return msg.content, msg.artifact


def test_esquemas_expuestos_al_modelo():
    tools = _tools()
    assert set(tools) == {
        "buscar_documentos",
        "consultar_indicadores",
        "comparar_cifras",
        "recordar_dato_usuario",
        "infografia_riopaila",
        "grafica_indicador",
    }
    assert "consulta" in tools["buscar_documentos"].args and "runtime" not in tools["recordar_dato_usuario"].args


def test_consultar_indicadores_exacto():
    content, art = _call(_tools()["consultar_indicadores"], {"indicador": "utilidad_neta", "anio": 2022})
    data = json.loads(content)
    assert (
        data["total"] == 1
        and data["filas"][0]["valor"] == 93241
        and art["filas"][0]["fuente_url"].startswith("https://")
    )


def test_comparar_cifras():
    content, art = _call(
        _tools()["comparar_cifras"],
        {
            "valor_a": 17,
            "etiqueta_a": "S1 2024",
            "valor_b": 11.5,
            "etiqueta_b": "S1 2023",
            "unidad": "millones de litros",
        },
    )
    assert art["variacion_pct"] == 47.83 and "47.83" in content


def test_buscar_sin_indice_lo_dice():
    content, art = _call(_tools()["buscar_documentos"], {"consulta": "azúcar"})
    assert "no está disponible" in content and art["hits"] == []


def test_vitrina_infografia_y_serie(tmp_path):
    from riopaila_qa.agent.tools import build_tools
    from riopaila_qa.config import ROOT_DIR
    from riopaila_qa.structured import load_indicadores

    filas = load_indicadores(ROOT_DIR / "data" / "structured" / "indicadores_riopaila.csv")
    tools = {t.name: t for t in build_tools(None, filas, media_dir=tmp_path)}
    msg = tools["infografia_riopaila"].invoke(
        {"type": "tool_call", "id": "1", "name": "infografia_riopaila", "args": {"tema": "panorama"}}
    )
    cifras = msg.artifact["cifras"]
    assert {c["indicador"] for c in cifras} >= {"ingresos_operacionales", "trabajadores"}
    assert all(c["fuente_url"].startswith("https://www.riopaila-castilla.com") for c in cifras)
    assert Path(msg.artifact["media"][0]["ruta"]).exists() and "más de $1,6 billones" in msg.content
    msg = tools["grafica_indicador"].invoke(
        {"type": "tool_call", "id": "2", "name": "grafica_indicador", "args": {"indicador": "ingresos"}}
    )
    assert [c["periodo"] for c in msg.artifact["serie"]] == ["2022", "2023", "2024"]
    assert Path(msg.artifact["media"][0]["ruta"]).exists()
    msg = tools["grafica_indicador"].invoke(
        {"type": "tool_call", "id": "3", "name": "grafica_indicador", "args": {"indicador": "no_existe_xyz"}}
    )
    assert "error" in msg.content and msg.artifact["serie"] == []

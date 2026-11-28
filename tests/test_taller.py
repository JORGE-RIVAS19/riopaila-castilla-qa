"""Módulo 3 · capa del taller con la muestra anonimizada (sin datos reales ni manuales con derechos)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from riopaila_qa.agent.fakes import ScriptedToolModel
from riopaila_qa.agent.graph import AgentDeps, build_graph
from riopaila_qa.agent.router import TOOLS_BY_ROUTE, route_by_rules
from riopaila_qa.agent.settings import AgentSettings
from riopaila_qa.agent.tools import AgentContext, build_tools
from riopaila_qa.structured import load_indicadores
from riopaila_qa.taller import consultas as q
from riopaila_qa.taller import novedades
from riopaila_qa.taller.base import cargar_csv, conectar, familia_de
from riopaila_qa.taller.config import MUESTRA_DIR, TallerSettings
from riopaila_qa.taller.manuales import (
    BuscadorManuales,
    Manual,
    expandir,
    extraer_paginas,
    renderizar_pagina,
)
from riopaila_qa.taller.tools import TallerDeps, build_taller_tools


@pytest.fixture(scope="module")
def db(tmp_path_factory) -> Path:
    destino = tmp_path_factory.mktemp("taller") / "muestra.duckdb"
    conteo = cargar_csv(
        MUESTRA_DIR / "equipos.csv", MUESTRA_DIR / "materiales.csv", MUESTRA_DIR / "consumos.csv", destino
    )
    assert conteo["equipos"] >= 30 and conteo["consumos"] > 1000
    return destino


@pytest.fixture(scope="module")
def con(db):
    c = conectar(db)
    yield c
    c.close()


@pytest.fixture()
def tools(con, tmp_path):
    s = replace(TallerSettings(), media_dir=tmp_path / "media", novedades_db=tmp_path / "nov.sqlite")
    return {t.name: t for t in build_taller_tools(TallerDeps(con, s))}, s


def call(tool, **args):
    """Invoca una tool como lo hace el agente y devuelve (contenido JSON, artefacto)."""
    msg = tool.invoke({"type": "tool_call", "id": "t1", "name": tool.name, "args": args})
    return json.loads(msg.content), msg.artifact


# ---------------------------------------------------------------- datos
def test_familias_por_regla():
    assert familia_de("COSECHADORA DE CAÑA JOHN DEERE CH570") == "Cosechadora"
    assert familia_de("TRACTOR CASE PUMA 165") == "Tractor"
    assert familia_de("TRACTOR CATERPILLAR D6N XL DE ORUGA") == "Maquinaria amarilla"
    assert familia_de("TRACTOMULA KENWORTH T800") == "Tractomula"
    assert familia_de("CAMABAJA TRANSPORTE DE MAQUINARIA") == "Vagones y remolques"


def test_consultas_basicas(con):
    corte = q.fecha_corte(con)
    rank = q.ranking_gasto(con, None, 90, 5)
    assert rank and rank == sorted(rank, key=lambda r: -r["gasto"])
    eq = rank[0]["equipo"]
    assert q.buscar_equipo(con, eq)[0].equipo == eq
    ficha = q.ficha_equipo(con, eq)
    assert ficha and ficha.gasto_12m > 0 and ficha.ultimo_consumo <= corte
    serie = q.serie_gasto(con, eq, meses=6)
    assert len(serie) == 6 and serie[-1].periodo == f"{corte:%Y-%m}"


def test_codigo_sap_ignora_guiones(con):
    # La referencia del fabricante se busca dentro del texto breve (regla del taller antes de crear códigos).
    assert any(r.material == "6041045" for r in q.verificar_codigo(con, "CB 01419085"))
    assert q.verificar_codigo(con, "ZZ-000000-NO-EXISTE") == []


def test_busqueda_difusa_de_repuestos(con):
    res = q.buscar_repuesto(con, "kit sello motor john deere")
    assert res and res[0].similitud >= 55


def test_anomalias_y_prediccion_son_explicables(con):
    for a in q.detectar_anomalias(con, 30, importe_minimo=0, top=5):
        assert a.veces >= 3 and "esperados" in a.explicacion
    eq = q.ranking_gasto(con, "Cosechadora", 180, 1)[0]["equipo"]
    for p in q.predecir_reposicion(con, eq, 60):
        assert p.intervalo_dias >= 3 and p.confianza in {"alta", "media", "baja"}


# ---------------------------------------------------------------- herramientas
def test_17_herramientas_con_esquema(tools):
    t, _ = tools
    assert len(t) == 17
    taller = set(TOOLS_BY_ROUTE["taller"]) | set(TOOLS_BY_ROUTE["manual"]) | set(TOOLS_BY_ROUTE["novedad"])
    assert set(t) <= taller | {"comparar_cifras"}
    assert all(tool.args_schema is not None for tool in t.values())


def test_ranking_y_grafica_envian_imagen(tools):
    t, s = tools
    contenido, art = call(t["ranking_gasto_equipos"], dias=90, top=5)
    assert contenido["ranking"] and Path(art["media"][0]["ruta"]).exists()
    assert art["media"][0]["url"].startswith("/media/graficas/")
    contenido, art = call(t["grafica_gasto"], familia="Cosechadora", meses=6)
    assert "$" in contenido["total"] and Path(art["media"][0]["ruta"]).exists()


def test_informe_pdf(tools):
    t, _ = tools
    _, art = call(t["generar_informe_pdf"], familia="Tractor", meses=3)
    pdf = Path(art["media"][0]["ruta"])
    assert pdf.suffix == ".pdf" and pdf.read_bytes()[:4] == b"%PDF"


def test_verificar_codigo_sap_tool(tools):
    t, _ = tools
    contenido, _ = call(t["verificar_codigo_sap"], referencia="CB-11421303")
    assert contenido["existe"] is True


def test_invitado_no_puede_registrar(tools):
    t, s = tools
    msg = t["registrar_novedad"].invoke(
        {"type": "tool_call", "id": "x", "name": "registrar_novedad", "args": {"equipo": "9001", "descripcion": "fuga"}}
    )
    assert "Solo el personal del taller" in msg.content
    assert novedades.listar(s.novedades_db) == []


# ---------------------------------------------------------------- manuales
@pytest.fixture()
def manual_pdf(tmp_path) -> Path:
    from fpdf import FPDF

    pdf = FPDF()
    for titulo, cuerpo in [
        ("Mantenimiento", "Cambio del filtro de aceite hidráulico cada 600 horas de servicio. Afloje el filtro."),
        ("Electrical", "Fuse panel: radio memory fuse 10A, horn relay, wiper fuse 25A, park lamps 30A."),
    ]:
        pdf.add_page()
        pdf.set_font("Helvetica", size=14)
        pdf.multi_cell(0, 8, f"{titulo}. {cuerpo}")
    (tmp_path / "manuales").mkdir()
    pdf.output(str(tmp_path / "manuales" / "prueba.pdf"))
    return tmp_path / "manuales"


def test_manual_busqueda_cruza_idiomas_y_resalta(manual_pdf, tmp_path):
    m = Manual("prueba", "Manual de prueba", "Ejemplo", ("PUMA 165",), "Tractor", "servicio", "es")
    paginas = extraer_paginas(manual_pdf, [m])
    assert [p.pagina for p in paginas] == [1, 2]
    b = BuscadorManuales(paginas)
    assert "filter" in expandir("filtro hidráulico")
    assert b.buscar("cambio filtro hidráulico", "PUMA 165")[0].pagina == 1
    assert b.buscar("fusible del radio")[0].pagina == 2  # español → inglés con el glosario
    png = renderizar_pagina(manual_pdf, "prueba", 2, tmp_path / "media", resaltar="fusible del radio")
    assert png.exists() and png.stat().st_size > 1000


# ---------------------------------------------------------------- router + HITL
@pytest.mark.parametrize(
    ("mensaje", "ruta"),
    [
        ("¿cuánto gastó la cosechadora 27316 en los últimos 3 meses?", "taller"),
        ("¿cómo se cambia el filtro hidráulico del puma 165?", "manual"),
        ("¿qué fusible es el del radio en la mula T800?", "manual"),
        ("[foto adjunta] ¿qué pieza es esta?", "manual"),
        ("el tractor 25375 está botando aceite, regístralo", "novedad"),
        ("¿Cuáles fueron los ingresos de Riopaila en 2024?", "datos"),
        ("Hola", "directo"),
    ],
)
def test_router_taller(mensaje, ruta):
    assert route_by_rules(mensaje).ruta == ruta


def _grafo(con, tmp_path):
    s = replace(TallerSettings(), media_dir=tmp_path / "media", novedades_db=tmp_path / "nov.sqlite")
    ag = replace(AgentSettings(), router_mode="reglas", memory_dir=tmp_path / "m")
    inds = load_indicadores(ag.structured_csv)
    tools = build_tools(None, inds) + build_taller_tools(TallerDeps(con, s))
    g = build_graph(AgentDeps(ScriptedToolModel(), tools, inds, ag), InMemorySaver(), InMemoryStore())
    return g, s


def test_novedad_pide_confirmacion_humana(con, tmp_path):
    g, s = _grafo(con, tmp_path)
    eq = q.ranking_gasto(con, None, 90, 1)[0]["equipo"]
    cfg = {"configurable": {"thread_id": "hitl"}}
    ctx = AgentContext(user_id="hugo", thread_id="hitl", rol="tecnico", canal="whatsapp")
    out = g.invoke({"messages": [{"role": "user", "content": f"el equipo {eq} se varó, regístralo"}]}, cfg, context=ctx)
    assert out["__interrupt__"][0].value["tipo"] == "confirmar_novedad"
    assert novedades.listar(s.novedades_db) == []  # nada se escribe sin el SÍ
    g.invoke(Command(resume="sí, confirmo"), cfg, context=ctx)
    guardadas = novedades.listar(s.novedades_db)
    assert len(guardadas) == 1 and guardadas[0]["equipo"] == eq and guardadas[0]["canal"] == "whatsapp"


def test_novedad_cancelada_no_escribe(con, tmp_path):
    g, s = _grafo(con, tmp_path)
    eq = q.ranking_gasto(con, None, 90, 1)[0]["equipo"]
    cfg = {"configurable": {"thread_id": "hitl2"}}
    ctx = AgentContext(user_id="hugo", thread_id="hitl2", rol="tecnico")
    g.invoke({"messages": [{"role": "user", "content": f"reporta falla del {eq}"}]}, cfg, context=ctx)
    g.invoke(Command(resume="no"), cfg, context=ctx)
    assert novedades.listar(s.novedades_db) == []


def test_roles_los_decide_el_servidor():
    s = replace(TallerSettings(), roles="jorge=supervisor,+573001112233=tecnico", rol_defecto="invitado")
    assert s.rol_de("jorge") == "supervisor"
    assert s.rol_de("+573001112233") == "tecnico" and s.rol_de("573001112233") == "tecnico"
    assert s.rol_de("desconocido") == "invitado"

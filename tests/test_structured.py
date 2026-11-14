"""Consultas deterministas sobre el CSV (esquema Pydantic): exactas, sin estimar."""

from __future__ import annotations

from riopaila_qa.config import ROOT_DIR
from riopaila_qa.structured import (
    ComparacionCifras,
    ConsultaIndicadores,
    catalogo,
    comparar,
    consultar,
    load_indicadores,
)

CSV = ROOT_DIR / "data" / "structured" / "indicadores_riopaila.csv"


def test_consulta_exacta_tercer_trimestre():
    res = consultar(load_indicadores(CSV), ConsultaIndicadores(indicador="ventas_energia", periodo="tercer trimestre"))
    assert res.total == 1 and res.filas[0].valor == 21342 and res.filas[0].anio == 2023


def test_consulta_parcial_por_palabra():
    res = consultar(load_indicadores(CSV), ConsultaIndicadores(indicador="alcohol", anio=2024))
    assert {r.id for r in res.filas} >= {"IND-024", "IND-026"}


def test_consulta_sin_resultados_no_inventa():
    res = consultar(load_indicadores(CSV), ConsultaIndicadores(indicador="utilidad_neta", anio=2030))
    assert res.total == 0 and "no se debe estimar" in res.nota


def test_comparar_lo_hace_python():
    r = comparar(ComparacionCifras(valor_a=11.5, etiqueta_a="S1", valor_b=40, etiqueta_b="meta", unidad="ML"))
    assert r.diferencia == -28.5 and r.porcentaje_a_sobre_b == 28.75 and r.variacion_pct == -71.25


def test_valor_legible_respeta_calificador():
    rows = {r.id: r for r in load_indicadores(CSV)}
    assert rows["IND-017"].valor_legible.startswith("más de ")
    assert rows["IND-024"].valor_legible.startswith("cerca de ")


def test_catalogo_agrupa_periodos():
    cat = catalogo(load_indicadores(CSV))
    assert "2023-T3" in cat["ventas_energia"] and "2024-anual" in cat["ventas_energia"]

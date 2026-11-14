"""Router (criterio 2.3): decide antes de gastar una búsqueda."""

from __future__ import annotations

import pytest

from riopaila_qa.agent.router import TOOLS_BY_ROUTE, route, route_by_rules


@pytest.mark.parametrize(
    ("mensaje", "ruta"),
    [
        ("Hola", "directo"),
        ("buenas tardes", "directo"),
        ("Gracias!", "directo"),
        ("¿Qué puedes hacer?", "directo"),
        ("¿Dónde trabajo?", "directo"),
        ("Me llamo Ana y trabajo en Carvajal", "memoria"),
        ("¿Cuánto vendió Riopaila en energía en el tercer trimestre de 2023?", "datos"),
        ("¿Cuál fue la utilidad neta de 2022?", "datos"),
        ("Compara la meta del documento con las ventas del CSV", "mixto"),
        (
            "¿Qué meta de producción de alcohol menciona el documento y cómo se compara con el primer semestre de 2023?",
            "mixto",
        ),
        ("¿Qué dice el corpus sobre la política de calidad?", "rag"),
        ("¿Qué es el proyecto de azúcar orgánica Riocas?", "rag"),
        ("¿En qué año fue fundada Riopaila Castilla?", "rag"),
    ],
)
def test_router_por_reglas(mensaje: str, ruta: str):
    assert route_by_rules(mensaje).ruta == ruta


def test_saludo_sin_herramientas():
    d = route_by_rules("hola")
    assert d.herramientas == () and d.confianza > 0.9


def test_confianza_baja_es_cautela():
    d = route("cuéntame algo más sobre eso, por favor", llm=None, mode="reglas")
    assert d.ruta == "rag" and d.cautela


def test_router_llm_caido_usa_reglas():
    class Roto:
        def with_structured_output(self, _):
            raise RuntimeError("503 UNAVAILABLE")

    d = route("¿Cuántos municipios?", llm=Roto(), mode="hibrido")  # confianza de reglas < 0.7 → intenta LLM
    assert d.metodo == "reglas" and "no disponible" in d.razon


def test_toda_ruta_tiene_herramientas_definidas():
    assert set(TOOLS_BY_ROUTE) == {"directo", "memoria", "rag", "datos", "mixto"}

"""Prueba mínima: el paquete se instala e importa con uv sync."""

import riopaila_qa


def test_package_imports():
    assert riopaila_qa.__version__

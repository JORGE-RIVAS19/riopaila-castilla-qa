"""Datos estructurados de Riopaila Castilla y consultas deterministas.

``data/structured/indicadores_riopaila.csv`` reúne cifras **públicas** que la
empresa publicó en sus noticias (ingresos, utilidad, alcohol carburante, energía,
inversión social…). Cada fila conserva la URL de la noticia de origen, así que la
herramienta no solo devuelve el número exacto: también su fuente.

Regla del criterio 2.1: el LLM **no calcula ni inventa cifras**. Las sumas, las
diferencias y los porcentajes los hace Python aquí y el modelo solo los redacta.
"""

from __future__ import annotations

import csv
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Periodo = Literal["anual", "S1", "S2", "T1", "T2", "T3", "T4"]
Calificador = Literal["exacto", "mas_de", "cerca_de"]
PERIODOS = ("anual", "S1", "S2", "T1", "T2", "T3", "T4")


class Indicador(BaseModel):
    """Una fila del CSV, validada."""

    id: str
    indicador: str
    categoria: str
    anio: int = Field(ge=1918, le=2100)
    periodo: Periodo
    valor: float
    unidad: str
    calificador: Calificador
    descripcion: str
    fuente_url: str

    @property
    def valor_legible(self) -> str:
        prefijo = {"exacto": "", "mas_de": "más de ", "cerca_de": "cerca de "}[self.calificador]
        v = f"{self.valor:,.2f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{prefijo}{v} {self.unidad.replace('_', ' ')}"


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c)).replace(" ", "_")


class ConsultaIndicadores(BaseModel):
    """Esquema de entrada de la herramienta ``consultar_indicadores``."""

    indicador: str | None = Field(
        None,
        description="Nombre o parte del nombre del indicador, p. ej. 'ventas_energia', 'utilidad', 'alcohol'.",
    )
    anio: int | None = Field(None, ge=2000, le=2100, description="Año del dato, p. ej. 2023.")
    periodo: Periodo | None = Field(None, description="anual, S1/S2 (semestre) o T1–T4 (trimestre).")
    categoria: str | None = Field(None, description="financiero, produccion, energia, social, ambiental o mercado.")

    @field_validator("periodo", mode="before")
    @classmethod
    def _periodo(cls, v):
        if v is None or v == "":
            return None
        alias = {
            "tercer trimestre": "T3",
            "q3": "T3",
            "3t": "T3",
            "segundo trimestre": "T2",
            "q2": "T2",
            "primer trimestre": "T1",
            "q1": "T1",
            "cuarto trimestre": "T4",
            "q4": "T4",
            "primer semestre": "S1",
            "h1": "S1",
            "segundo semestre": "S2",
            "h2": "S2",
            "año": "anual",
        }
        s = str(v).strip()
        return alias.get(s.lower(), s.upper() if s.upper() in PERIODOS else s)


class ResultadoConsulta(BaseModel):
    """Salida de ``consultar_indicadores``: filas exactas con fuente."""

    filtros: dict
    total: int
    filas: list[Indicador]
    nota: str = ""


class ComparacionCifras(BaseModel):
    """Entrada de ``comparar_cifras``: dos valores en la misma unidad."""

    valor_a: float = Field(description="Primer valor (p. ej. lo logrado, tomado del CSV).")
    etiqueta_a: str = Field(description="Qué es el valor A, con su periodo.")
    valor_b: float = Field(description="Segundo valor (p. ej. la meta, tomada del documento).")
    etiqueta_b: str = Field(description="Qué es el valor B, con su periodo.")
    unidad: str = Field(description="Unidad común, p. ej. 'millones de litros'.")


class ResultadoComparacion(BaseModel):
    """Aritmética hecha en Python, no por el LLM."""

    diferencia: float
    porcentaje_a_sobre_b: float | None
    variacion_pct: float | None
    texto: str


@lru_cache(maxsize=4)
def load_indicadores(path: Path) -> tuple[Indicador, ...]:
    """Lee y valida el CSV (cada fila debe cumplir el esquema Pydantic)."""
    with path.open(encoding="utf-8") as f:
        return tuple(Indicador.model_validate(row) for row in csv.DictReader(f))


def consultar(rows: tuple[Indicador, ...], q: ConsultaIndicadores) -> ResultadoConsulta:
    """Filtro exacto sobre el CSV. Nunca interpola ni estima."""
    out = list(rows)
    if q.indicador:
        needle = _norm(q.indicador)
        parts = [p for p in needle.split("_") if len(p) > 2]
        exact = [r for r in out if r.indicador == needle]
        out = exact or [
            r
            for r in out
            if needle in r.indicador or all(p[:6] in _norm(r.indicador + " " + r.descripcion) for p in parts)
        ]
    if q.anio:
        out = [r for r in out if r.anio == q.anio]
    if q.periodo:
        out = [r for r in out if r.periodo == q.periodo]
    if q.categoria:
        out = [r for r in out if r.categoria == _norm(q.categoria)]
    nota = "" if out else "No hay filas con esos filtros: no se debe estimar ni inventar el dato."
    return ResultadoConsulta(filtros=q.model_dump(exclude_none=True), total=len(out), filas=out[:25], nota=nota)


def comparar(c: ComparacionCifras) -> ResultadoComparacion:
    """Diferencia y porcentajes deterministas entre dos cifras."""
    dif = round(c.valor_a - c.valor_b, 4)
    pct = round(c.valor_a / c.valor_b * 100, 2) if c.valor_b else None
    var = round((c.valor_a - c.valor_b) / c.valor_b * 100, 2) if c.valor_b else None
    texto = f"{c.etiqueta_a}: {c.valor_a:g} {c.unidad}; {c.etiqueta_b}: {c.valor_b:g} {c.unidad}. Diferencia: {dif:g} {c.unidad}"
    if pct is not None:
        texto += f"; A equivale al {pct:g} % de B ({var:+g} %)."
    return ResultadoComparacion(diferencia=dif, porcentaje_a_sobre_b=pct, variacion_pct=var, texto=texto)


def catalogo(rows: tuple[Indicador, ...]) -> dict[str, list[str]]:
    """Indicadores disponibles con sus periodos (lo usa el router y el prompt)."""
    cat: dict[str, set[str]] = {}
    for r in rows:
        cat.setdefault(r.indicador, set()).add(f"{r.anio}-{r.periodo}")
    return {k: sorted(v) for k, v in sorted(cat.items())}

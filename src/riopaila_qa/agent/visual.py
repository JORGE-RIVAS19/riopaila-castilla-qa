"""Salidas visuales de las cifras públicas de Riopaila Castilla (M1/M2) para el perfil visitante.

* ``infografia``: tarjeta "Riopaila en cifras" (PNG para WhatsApp) con las cifras más recientes de un tema.
* ``serie_indicador``: columnas de un indicador por año, con el calificador del comunicado ("más de", "cerca de").

Todo sale del CSV de indicadores (cada fila con su URL de origen): no se estima ni se interpola nada.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from riopaila_qa.structured import Indicador  # noqa: E402

VERDE, VERDE_OSCURO, VERDE_CLARO = "#1f8a4c", "#0f5a2f", "#cfe9d9"
TINTA, TENUE, REJILLA, FONDO, TARJETA = "#0b0b0b", "#6b6a65", "#e1e0d9", "#f6f5f0", "#ffffff"

Tema = Literal["panorama", "energia", "etanol", "social"]

# Qué cifras muestra cada tema (en orden) y con qué título corto.
TEMAS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "panorama": (
        "Riopaila Castilla en cifras",
        [
            ("ingresos_operacionales", "Ingresos operacionales"),
            ("crecimiento_utilidades", "Crecimiento de utilidades"),
            ("participacion_mercado_azucar_alcohol_equivalente", "Participación nacional (azúcar y alcohol)"),
            ("paises_destino", "Países a los que llegan sus productos"),
            ("trabajadores", "Trabajadores"),
            ("inversion_social_y_ambiental", "Inversión social y ambiental"),
        ],
    ),
    "energia": (
        "Energía verde del bagazo",
        [
            ("ventas_energia", "Ventas de energía renovable"),
            ("personas_abastecidas_energia", "Colombianos que se pueden abastecer"),
            ("co2_evitado", "CO₂ evitado"),
            ("energia_para_autoconsumo", "Energía usada en las dos plantas"),
            ("ventas_energia_y_biocombustible", "Ventas de energía y biocombustible"),
        ],
    ),
    "etanol": (
        "Alcohol carburante (etanol)",
        [
            ("produccion_alcohol_carburante", "Producción de etanol"),
            ("crecimiento_produccion_alcohol", "Crecimiento de la producción"),
            ("vehiculos_oxigenados", "Vehículos oxigenados"),
            ("capacidad_destileria", "Capacidad de la destilería"),
            ("ingresos_alcohol_carburante", "Ingresos por etanol"),
            ("crecimiento_ingresos_alcohol", "Crecimiento de esos ingresos"),
        ],
    ),
    "social": (
        "Compromiso social",
        [
            ("inversion_social_y_ambiental", "Inversión social y ambiental"),
            ("inversion_social", "Inversión en promoción social"),
            ("trabajadores", "Trabajadores"),
            ("pagos_a_proveedores", "Pagos a proveedores y agricultores"),
        ],
    ),
}

_ORDEN_PERIODO = {"anual": 9, "T4": 8, "S2": 7, "T3": 6, "S1": 5, "T2": 4, "T1": 3}


def _miles(v: float, dec: int = 0) -> str:
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cifra_corta(r: Indicador) -> str:
    """``1600000 millones_cop`` → ``"$1,6 billones"``; ``18 porcentaje`` → ``"18 %"``; con "más de"/"cerca de"."""
    prefijo = {"exacto": "", "mas_de": "más de ", "cerca_de": "cerca de "}[r.calificador]
    v, u = r.valor, r.unidad
    if u == "millones_cop":
        texto = f"${_miles(v / 1e6, 1)} billones" if v >= 1e6 else f"${_miles(v)} millones"
    elif u == "porcentaje":
        texto = f"{_miles(v, 2 if v % 1 else 0).rstrip('0').rstrip(',')} %"
    elif u == "millones_litros":
        texto = f"{_miles(v, 1 if v % 1 else 0)} millones de litros"
    elif u == "litros_dia":
        texto = f"{_miles(v)} litros/día"
    elif u == "toneladas_co2":
        texto = f"{_miles(v)} t de CO₂"
    else:
        nombres = {"paises": "países", "vehiculos": "vehículos", "personas": "personas"}
        texto = f"{_miles(v)} {nombres.get(u, u.replace('_', ' '))}"
    return prefijo + texto


def periodo_legible(r: Indicador) -> str:
    return {
        "anual": str(r.anio),
        "S1": f"1.er semestre {r.anio}",
        "S2": f"2.º semestre {r.anio}",
    }.get(r.periodo, f"{r.periodo} {r.anio}")


def mas_reciente(filas: tuple[Indicador, ...], indicador: str) -> Indicador | None:
    candidatas = [r for r in filas if r.indicador == indicador]
    return max(candidatas, key=lambda r: (r.anio, _ORDEN_PERIODO.get(r.periodo, 0)), default=None)


def _archivo(destino_dir: Path, prefijo: str, *partes) -> Path:
    destino_dir.mkdir(parents=True, exist_ok=True)
    return destino_dir / f"{prefijo}_{hashlib.sha1(repr(partes).encode()).hexdigest()[:10]}.png"


def _envolver(texto: str, ancho: int) -> str:
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        if len(actual) + len(p) + 1 > ancho and actual:
            lineas.append(actual)
            actual = p
        else:
            actual = f"{actual} {p}".strip()
    return "\n".join([*lineas, actual])


def infografia(filas: tuple[Indicador, ...], tema: str, destino_dir: Path) -> tuple[Path, list[Indicador]]:
    """Tarjeta de 2 columnas con las cifras más recientes del tema; cada cifra con su periodo."""
    titulo, piezas = TEMAS.get(tema, TEMAS["panorama"])
    elegidas = [(r, etiqueta) for ind, etiqueta in piezas if (r := mas_reciente(filas, ind)) is not None]
    ruta = _archivo(Path(destino_dir), f"infografia_{tema}", [(r.id, r.valor) for r, _ in elegidas])
    n_filas = (len(elegidas) + 1) // 2
    alto = 2.3 + 1.95 * n_filas
    fig = plt.figure(figsize=(9, alto), dpi=170, facecolor=FONDO)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 9)
    ax.set_ylim(0, alto)
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0, alto - 0.14), 9, 0.14, color=VERDE, lw=0))
    ax.text(0.45, alto - 0.62, titulo, fontsize=21, fontweight="bold", color=TINTA, va="top")
    ax.text(
        0.45,
        alto - 1.2,
        "Agroindustria del Valle del Cauca · azúcar, etanol y energía del bagazo",
        fontsize=10.5,
        color=TENUE,
        va="top",
    )
    w, h, gap = 3.95, 1.68, 0.2
    for i, (r, etiqueta) in enumerate(elegidas):
        col, fila = i % 2, i // 2
        x = 0.45 + col * (w + gap)
        y = alto - 1.75 - (fila + 1) * h - fila * gap
        ax.add_patch(
            FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12", fc=TARJETA, ec=REJILLA, lw=0.8)
        )
        ax.add_patch(plt.Rectangle((x, y + 0.18), 0.06, h - 0.36, color=VERDE, lw=0))
        cifra = cifra_corta(r)
        ax.text(
            x + 0.28,
            y + h - 0.3,
            _envolver(cifra, 22),
            fontsize=18 if len(cifra) <= 18 else 14.5,
            fontweight="bold",
            color=VERDE_OSCURO,
            va="top",
            linespacing=1.05,
        )
        ax.text(x + 0.28, y + 0.62, _envolver(etiqueta, 40), fontsize=10.5, color=TINTA, va="top")
        ax.text(x + 0.28, y + 0.2, periodo_legible(r), fontsize=9, color=TENUE, va="bottom")
    ax.text(
        0.45,
        0.32,
        "Fuente: comunicados públicos de riopaila-castilla.com · datos del corpus del proyecto (M1/M2)",
        fontsize=8.5,
        color=TENUE,
    )
    fig.savefig(ruta, facecolor=FONDO)
    plt.close(fig)
    return ruta, [r for r, _ in elegidas]


def serie_indicador(
    filas: tuple[Indicador, ...], indicador: str, destino_dir: Path
) -> tuple[Path | None, list[Indicador]]:
    """Columnas por año del indicador, en el periodo con más datos (anual si alcanza)."""
    datos = [r for r in filas if r.indicador == indicador]
    if not datos:
        return None, []
    por_periodo: dict[str, list[Indicador]] = {}
    for r in datos:
        por_periodo.setdefault(r.periodo, []).append(r)
    periodo = max(por_periodo, key=lambda p: (len(por_periodo[p]), p == "anual"))
    serie = sorted(por_periodo[periodo], key=lambda r: r.anio)
    ruta = _archivo(Path(destino_dir), f"indicador_{indicador}", [(r.id, r.valor) for r in serie])
    escala, unidad = (1e6, "billones COP") if serie[0].unidad == "millones_cop" and serie[0].valor >= 1e5 else (1, "")
    valores = [r.valor / escala for r in serie]
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=160, facecolor=FONDO)
    ax.set_facecolor(FONDO)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(REJILLA)
    ax.tick_params(colors=TENUE, labelsize=11, length=0)
    ax.set_yticks([])
    etiquetas = [str(r.anio) if periodo == "anual" else periodo_legible(r) for r in serie]
    colores = [VERDE_OSCURO if i == len(serie) - 1 else VERDE for i in range(len(serie))]
    ax.bar(range(len(serie)), valores, width=0.56, color=colores, zorder=2)
    ax.set_xticks(range(len(serie)), etiquetas)
    tope = max(valores) if valores else 1
    for i, r in enumerate(serie):
        ax.text(i, valores[i] + tope * 0.025, cifra_corta(r), ha="center", va="bottom", fontsize=11, color=TINTA)
    ax.set_ylim(0, tope * 1.2)
    nombre = indicador.replace("_", " ").replace("co2", "CO₂").capitalize()
    fig.text(0.02, 0.96, _envolver(nombre, 70), fontsize=14, fontweight="bold", color=TINTA, va="top")
    fig.text(
        0.02,
        0.875,
        f"Riopaila Castilla · {'por año' if periodo == 'anual' else periodo_legible(serie[0]).split(' 20')[0]}"
        f"{' · ' + unidad if unidad else ''} · fuente: riopaila-castilla.com",
        fontsize=10,
        color=TENUE,
        va="top",
    )
    fig.subplots_adjust(top=0.8, bottom=0.1, left=0.04, right=0.98)
    fig.savefig(ruta, facecolor=FONDO)
    plt.close(fig)
    return ruta, serie

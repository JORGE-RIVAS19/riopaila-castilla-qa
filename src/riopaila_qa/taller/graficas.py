"""Gráficas (PNG para WhatsApp) e informes PDF del taller.

Estilo sobrio y legible en el celular: una sola tinta azul (magnitud), rejilla tenue, valores
en millones de pesos, etiqueta directa solo en el dato que importa (el pico / el primero).
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AZUL, AZUL_OSCURO, AZUL_CLARO = "#2a78d6", "#104281", "#9ec5f4"
TINTA, TENUE, REJILLA, FONDO = "#0b0b0b", "#6b6a65", "#e1e0d9", "#fcfcfb"
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def millones(valor: float | None) -> str:
    """``12_345_678`` → ``"$12,3 M"`` (pesos colombianos, coma decimal)."""
    v = (valor or 0) / 1e6
    if abs(v) >= 1000:
        return f"${v / 1000:,.2f} mil M".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"${v:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")


def _nombre(destino_dir: Path, prefijo: str, *partes) -> Path:
    destino_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(repr(partes).encode()).hexdigest()[:10]
    return destino_dir / f"{prefijo}_{h}.png"


def _estilo(ax) -> None:
    ax.set_facecolor(FONDO)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(REJILLA)
    ax.tick_params(colors=TENUE, labelsize=10, length=0)
    ax.set_axisbelow(True)


def _etiqueta_mes(periodo: str) -> str:
    anio, mes = periodo.split("-")
    return f"{MESES[int(mes) - 1]}\n{anio[2:]}"


def grafica_barras_mensual(
    serie: list[tuple[str, float]], titulo: str, subtitulo: str, destino_dir: Path, ultimo_parcial: bool = False
) -> Path:
    """Columnas del gasto por mes; el mes pico en azul oscuro y con su valor; el mes en curso, más claro."""
    ruta = _nombre(Path(destino_dir), "mensual", serie, titulo, ultimo_parcial)
    etiquetas = [_etiqueta_mes(p) for p, _ in serie]
    valores = [v / 1e6 for _, v in serie]
    pico = max(range(len(valores)), key=valores.__getitem__) if valores else 0
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=160, facecolor=FONDO)
    _estilo(ax)
    colores = [AZUL_OSCURO if i == pico else AZUL for i in range(len(valores))]
    if ultimo_parcial and valores:
        colores[-1] = AZUL_CLARO
        ax.annotate(
            "en curso",
            (len(valores) - 1, valores[-1]),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color=TENUE,
        )
    ancho = min(0.62, 0.62 * 12 / max(len(valores), 1))
    ax.bar(range(len(valores)), valores, width=ancho, color=colores, zorder=2)
    ax.grid(axis="y", color=REJILLA, linewidth=0.8, zorder=0)
    ax.set_xticks(range(len(valores)), etiquetas)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    ax.set_ylabel("millones de COP", color=TENUE, fontsize=10)
    if valores and valores[pico] > 0:
        ax.annotate(
            millones(valores[pico] * 1e6),
            (pico, valores[pico]),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            fontsize=11,
            fontweight="bold",
            color=TINTA,
        )
    fig.text(0.02, 0.96, titulo, fontsize=15, fontweight="bold", color=TINTA, va="top")
    fig.text(0.02, 0.895, subtitulo, fontsize=10.5, color=TENUE, va="top")
    fig.text(0.98, 0.015, "Asistente Taller Castilla · datos SAP", fontsize=8, color=TENUE, ha="right")
    fig.subplots_adjust(top=0.80, bottom=0.14, left=0.09, right=0.98)
    fig.savefig(ruta, facecolor=FONDO)
    plt.close(fig)
    return ruta


def grafica_ranking(filas: list[tuple[str, float]], titulo: str, subtitulo: str, destino_dir: Path) -> Path:
    """Barras horizontales ordenadas (el primero arriba) con el valor al final de cada barra."""
    ruta = _nombre(Path(destino_dir), "ranking", filas, titulo)
    filas = filas[::-1]
    etiquetas = [e if len(e) <= 34 else e[:33] + "…" for e, _ in filas]
    valores = [v / 1e6 for _, v in filas]
    alto = 1.6 + 0.48 * len(filas)
    fig, ax = plt.subplots(figsize=(9, alto), dpi=160, facecolor=FONDO)
    _estilo(ax)
    ax.spines["bottom"].set_visible(False)
    colores = [AZUL_OSCURO if i == len(valores) - 1 else AZUL for i in range(len(valores))]
    ax.barh(range(len(valores)), valores, height=0.58, color=colores, zorder=2)
    ax.set_yticks(range(len(valores)), etiquetas, fontsize=10, color=TINTA)
    ax.set_xticks([])
    tope = max(valores, default=1)
    for i, v in enumerate(valores):
        ax.text(v + tope * 0.01, i, millones(v * 1e6), va="center", fontsize=10, color=TINTA)
    ax.set_xlim(0, tope * 1.18)
    fig.text(0.02, 1 - 0.25 / alto, titulo, fontsize=15, fontweight="bold", color=TINTA, va="top")
    fig.text(0.02, 1 - 0.62 / alto, subtitulo, fontsize=10.5, color=TENUE, va="top")
    fig.subplots_adjust(top=1 - 1.05 / alto, bottom=0.25 / alto, left=0.40, right=0.97)
    fig.savefig(ruta, facecolor=FONDO)
    plt.close(fig)
    return ruta


# --------------------------------------------------------------------------- PDF
def _latin1(texto: str) -> str:
    texto = str(texto).replace("–", "-").replace("—", "-").replace("…", "...").replace("≈", "~").replace("×", "x")
    texto = texto.replace("“", '"').replace("”", '"').replace("’", "'").replace("•", "-")
    return texto.encode("latin-1", "replace").decode("latin-1")


def informe_pdf(
    titulo: str,
    resumen: list[str],
    tablas: list[tuple[str, list[str], list[list]]],
    imagenes: list[Path],
    destino_dir: Path,
    corte: date | None = None,
) -> Path:
    """Informe de una o dos páginas: encabezado, resumen, gráfica(s) y tablas."""
    from fpdf import FPDF

    destino_dir = Path(destino_dir)
    destino_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", titulo.lower())[:50].strip("-")
    ruta = destino_dir / f"informe_{slug}_{datetime.now():%Y%m%d%H%M%S}.pdf"

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_fill_color(16, 66, 129)
    pdf.rect(0, 0, 210, 24, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_xy(12, 6)
    pdf.cell(0, 7, _latin1(titulo))
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(12, 14)
    pdf.cell(
        0,
        5,
        _latin1(
            f"Taller Castilla · Riopaila Castilla · datos SAP al {corte:%d/%m/%Y}"
            if corte
            else "Taller Castilla · Riopaila Castilla"
        ),
    )
    pdf.set_text_color(11, 11, 11)
    pdf.set_y(30)
    pdf.set_font("Helvetica", "", 10.5)
    for linea in resumen:
        pdf.set_x(12)
        pdf.multi_cell(186, 5.5, _latin1(f"- {linea}"))
    pdf.ln(2)
    for img in imagenes:
        if Path(img).exists():
            pdf.image(str(img), x=12, w=186)
            pdf.ln(3)
    for nombre, cabecera, filas in tablas:
        if not filas:
            continue
        pdf.set_font("Helvetica", "B", 11.5)
        pdf.set_x(12)
        pdf.cell(0, 8, _latin1(nombre), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        with pdf.table(
            col_widths=(3, *([1.4] * (len(cabecera) - 1))), text_align="LEFT", line_height=5.2, width=186
        ) as t:
            fila = t.row()
            for c in cabecera:
                fila.cell(_latin1(c))
            for f in filas:
                fila = t.row()
                for c in f:
                    fila.cell(_latin1(c))
        pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(107, 106, 101)
    pdf.set_x(12)
    pdf.multi_cell(
        186,
        4,
        _latin1(
            "Generado por el Asistente del Taller Castilla. Las cifras salen de consultas "
            "deterministas sobre SAP (el modelo de lenguaje no calcula). Uso interno."
        ),
    )
    pdf.output(str(ruta))
    return ruta

"""Muestra anonimizada de la base del taller (la única que entra al repositorio).

* Equipos: unos pocos por familia, con código nuevo (9000+), sin serie, VIN/pieza de fabricante ni activo fijo.
* Órdenes → ``OT-######``; se eliminan usuario y documento de material.
* Importes y precios multiplicados por un factor aleatorio U(0,75; 1,25) por equipo/material.
* Solo movimientos desde ``desde`` y 300 materiales extra al azar para la búsqueda difusa.

Se conservan textos de materiales y referencias de fabricante (son públicas en los catálogos),
para que las pruebas y la demo sin servidor se comporten como la base real.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

import duckdb

from riopaila_qa.taller.base import cargar_csv

CAB_EQUIPOS = [
    "Equipo",
    "Denominación",
    "Nº de modelo",
    "NºPieza fabric.",
    "Fabr. Nº-serie",
    "Ubicac.técnica",
    "Denominación#2",
    "Centro coste",
    "Estado sistema",
    "Status usuario",
    "Fe.puesta serv.",
    "Fe.creación",
    "Fe.modificación",
]
CAB_MATERIALES = [
    "Material",
    "Descripción material",
    "Tipo de material",
    "Grupo de artículos",
    "Unidad medida base",
    "Precio",
    "Indicador ABC",
    "Última modificación",
]
CAB_CONSUMOS = [
    "Equipo",
    "Denominación del equipo",
    "CMv",
    "Doc.mat.",
    "Material",
    "Texto breve de material",
    "Nombre del usuario",
    "Orden",
    "Cantidad",
    "Importe ML",
    "Fe.contab.",
    "UMB",
    "Ce.coste",
    "Alm.",
]


def _escribir(path: Path, cab: list[str], filas) -> int:
    n = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cab)
        for fila in filas:
            w.writerow(["" if v is None else v for v in fila])
            n += 1
    return n


def generar_muestra(
    base_real: Path, destino_dir: Path, por_familia: int = 4, semilla: int = 28, desde: str = "2025-11-01"
) -> dict[str, int]:
    rnd = random.Random(semilla)
    con = duckdb.connect(str(base_real), read_only=True)
    elegidos: list[tuple] = []
    for (familia,) in con.execute("SELECT DISTINCT familia FROM consumo_neto ORDER BY 1").fetchall():
        filas = con.execute(
            """SELECT equipo, any_value(denominacion) FROM consumo_neto WHERE familia = ? AND fecha >= ?
               GROUP BY 1 HAVING count(*) >= 20 ORDER BY sum(importe_neto) DESC LIMIT 12""",
            [familia, desde],
        ).fetchall()
        elegidos += rnd.sample(filas, min(por_familia, len(filas)))
    mapa = {eq: str(9001 + i) for i, (eq, _) in enumerate(sorted(elegidos))}
    factor_eq = {eq: rnd.uniform(0.75, 1.25) for eq in mapa}

    destino_dir.mkdir(parents=True, exist_ok=True)
    equipos = con.execute(
        f"""SELECT equipo, denominacion, modelo, pieza_fabricante, ubicacion, ubicacion_texto, estado, status_usuario,
                   puesta_servicio FROM equipos WHERE equipo IN ({",".join("?" * len(mapa))})""",
        list(mapa),
    ).fetchall()
    n_eq = _escribir(
        destino_dir / "equipos.csv",
        CAB_EQUIPOS,
        ([mapa[e[0]], e[1], e[2], "", "", e[4], e[5], "", e[6], e[7], e[8], "", ""] for e in equipos),
    )

    consumos = con.execute(
        f"""SELECT equipo, denominacion, movimiento, material, texto_material, orden, cantidad, importe, fecha, unidad
            FROM consumos WHERE fecha >= ? AND equipo IN ({",".join("?" * len(mapa))})""",
        [desde, *mapa],
    ).fetchall()
    ordenes: dict[str, str] = {}
    usados = set()

    def fila_consumo(c):
        orden = ordenes.setdefault(c[5], f"OT-{len(ordenes) + 1:06d}")
        usados.add(c[3])
        return [
            mapa[c[0]],
            c[1],
            c[2],
            "",
            c[3],
            c[4],
            "",
            orden,
            c[6],
            round((c[7] or 0) * factor_eq[c[0]]),
            c[8],
            c[9],
            "",
            "",
        ]

    n_co = _escribir(destino_dir / "consumos.csv", CAB_CONSUMOS, (fila_consumo(c) for c in consumos))

    todos = [m for (m,) in con.execute("SELECT material FROM materiales").fetchall()]
    extra = set(rnd.sample(todos, min(300, len(todos))))
    codigos = sorted((usados | extra) - {None, ""})
    materiales = con.execute(
        "SELECT material, texto, tipo, grupo, unidad, precio, abc, modificado FROM materiales WHERE material IN (SELECT unnest(?))",
        [codigos],
    ).fetchall()
    n_ma = _escribir(
        destino_dir / "materiales.csv",
        CAB_MATERIALES,
        ([m[0], m[1], m[2], m[3], m[4], round((m[5] or 0) * rnd.uniform(0.75, 1.25)), m[6], m[7]] for m in materiales),
    )
    con.close()
    cargar_csv(
        destino_dir / "equipos.csv",
        destino_dir / "materiales.csv",
        destino_dir / "consumos.csv",
        destino_dir / "taller_muestra.duckdb",
    )
    return {"equipos": n_eq, "materiales": n_ma, "consumos": n_co}

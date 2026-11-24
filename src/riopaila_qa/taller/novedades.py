"""Novedades de campo (fallas, daños, fugas) que reportan los técnicos por WhatsApp.

Es la única escritura del asistente y pasa por confirmación humana (``interrupt`` en la tool).
Se guarda en SQLite aparte: la base de SAP sigue siendo de solo lectura.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

ESQUEMA = """
CREATE TABLE IF NOT EXISTS novedades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creada TEXT NOT NULL,
    equipo TEXT NOT NULL,
    denominacion TEXT,
    sistema TEXT,
    descripcion TEXT NOT NULL,
    prioridad TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'abierta',
    reportado_por TEXT,
    canal TEXT
)
"""


class Novedad(BaseModel):
    equipo: str
    denominacion: str = ""
    sistema: str = ""
    descripcion: str = Field(min_length=3, max_length=1000)
    prioridad: Literal["alta", "media", "baja"] = "media"


def _con(path: Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute(ESQUEMA)
    return con


def registrar(path: Path, n: Novedad, reportado_por: str, canal: str = "web", tz: str = "America/Bogota") -> dict:
    ahora = datetime.now(ZoneInfo(tz)).isoformat(timespec="seconds")
    with _con(path) as con:
        cur = con.execute(
            """INSERT INTO novedades (creada, equipo, denominacion, sistema, descripcion, prioridad, reportado_por, canal)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ahora, n.equipo, n.denominacion, n.sistema, n.descripcion, n.prioridad, reportado_por, canal),
        )
        fila = con.execute("SELECT * FROM novedades WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(fila)


def listar(path: Path, estado: str | None = "abierta", limite: int = 20) -> list[dict]:
    with _con(path) as con:
        if estado:
            filas = con.execute("SELECT * FROM novedades WHERE estado = ? ORDER BY id DESC LIMIT ?", (estado, limite))
        else:
            filas = con.execute("SELECT * FROM novedades ORDER BY id DESC LIMIT ?", (limite,))
        return [dict(f) for f in filas.fetchall()]

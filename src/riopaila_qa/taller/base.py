"""Base analítica del taller: exportes de SAP (Excel) → DuckDB de solo lectura.

Tres exportes de SAP PM/MM de la Planta Castilla:

* ``equipos``    – maestro de equipos (IE03): código, denominación, modelo, ubicación, estado.
* ``materiales`` – maestro de materiales (MM03): texto breve, precio, indicador ABC.
* ``consumos``   – movimientos de inventario cargados a órdenes (MB51): 261 salida a orden,
  101 entrada de servicio, y sus anulaciones 262/102 (que restan).

La vista ``consumo_neto`` deja todo listo para el agente: importe con signo, familia y marca
derivadas de la denominación. El LLM nunca suma: las sumas salen de aquí.
"""

from __future__ import annotations

import csv
import re
import tempfile
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import duckdb

# Orden importa: la primera regla que coincide gana.
FAMILIAS: list[tuple[str, str]] = [
    ("Cosechadora", r"COSECHADORA|CH ?570|CH ?670|A8800|A8000|CH ?950"),
    ("Alzadora", r"ALZADORA|CARGADORA DE CA|CANE LOADER|\b2254\b|\b3522\b|\b3510\b"),
    (
        "Tractomula",
        r"TRACTOMULA|TRACTOCAMION|TRACTO CAMION|CABEZOTE|KENWORTH|INTERNATIONAL|FREIGHTLINER|MACK\b|\bT800\b|\bT370\b",
    ),
    (
        "Maquinaria amarilla",
        r"CATERPILLAR D[0-9]|\bD[0-9]N\b|ORUGA|RETROEXCAVADORA|EXCAVADORA|MOTONIVELADORA|BULLDOZER|BUFALO|BÚFALO|CARGADOR|MINICARGADOR|VIBROCOMPACTADOR|"
        r"COMPACTADOR|MONTACARGA|GRUA|GRÚA|TELEHANDLER|MANIPULADOR",
    ),
    ("Tractor", r"TRACTOR"),
    (
        "Vagones y remolques",
        r"CAMABAJA|CAMA BAJA|VAGON|VAGÓN|REMOLQUE|SEMIREMOLQUE|SEMI REMOLQUE|CANASTA|TOLVA|AUTOVOLTEO|VOLCO|DOLLY|CARRETA|CARRETON",
    ),
    (
        "Camiones y camionetas",
        r"CAMION|CAMIÓN|CAMIONETA|VOLQUETA|AUTOMOVIL|AUTOMÓVIL|CAMPERO|FURGON|FURGÓN|BUS\b|BUSETA|MICROBUS|"
        r"MOTOCICLETA|MOTO\b|CUATRIMOTO|PICK ?UP|HILUX|DMAX|D-MAX|LUV|NPR|NKR|FVR|NHR|CARROTANQUE|CISTERNA|AMBULANCIA",
    ),
    (
        "Implementos agrícolas",
        r"RASTRA|ARADO|SUBSOLADOR|CULTIVADORA|ABONADORA|FERTILIZADORA|SEMBRADORA|ZANJADORA|ASPERJADORA|"
        r"FUMIGADORA|PULVERIZADORA|GUADAÑADORA|DESBROZADORA|RENOVADORA|RIPPER|CINCEL|CULTIVADOR|SURCADOR|"
        r"ENCALADORA|PICADORA|DESPAJADORA|DESAPORQUE|APORCADOR|ESPARCIDOR|ROTOVATOR|IMPLEMENTO|NIVELADORA|"
        r"TRAILLA|LEVANTADOR|MELGADOR|ACONDICIONADOR|RASTRILLO|SUBSUELO|ESCARIFICADOR|ALINEADOR|APORQUE|TRITURADOR",
    ),
    ("Riego y bombeo", r"BOMBA|MOTOBOMBA|RIEGO|POZO|CAÑON|CAÑÓN|ASPERSOR|PIVOTE|ELECTROBOMBA|TANQUE"),
    (
        "Motores y equipos de taller",
        r"MOTOR|PLANTA ELECTRICA|PLANTA ELÉCTRICA|GENERADOR|COMPRESOR|SOLDADOR|HIDROLAVADORA|LAVADORA|"
        r"CARRO TALLER|BANCO DE PRUEBA|ESTACION LAVADERO|LUBRICACION|TORNO|ESMERIL|TALADRO|PRENSA|GATO|ELEVADOR|MOTOSIERRA|MOTOGUADAÑA|GUADAÑA",
    ),
]

MARCAS: list[tuple[str, str]] = [
    ("John Deere", r"JOHN DEERE|\bJD\b|DEERE"),
    ("Case IH", r"CASE|\bIH\b|PUMA|MAGNUM|AUSTOFT"),
    ("New Holland", r"NEW HOLLAND|\bNH\b"),
    ("Massey Ferguson", r"MASSEY|\bMF\b"),
    ("Kenworth", r"KENWORTH|\bKW\b"),
    ("International", r"INTERNATIONAL"),
    ("Caterpillar", r"CATERPILLAR|\bCAT\b"),
    ("GAME", r"\bGAME\b"),
    ("Chevrolet", r"CHEVROLET|\bLUV\b|\bNPR\b|\bNKR\b|\bNHR\b|\bFVR\b|DMAX|D-MAX"),
    ("Toyota", r"TOYOTA|HILUX"),
    ("Valtra", r"VALTRA"),
]

MOVIMIENTOS = {"261": 1, "262": -1, "101": 1, "102": -1}


def _regla_sql(columna: str, reglas: list[tuple[str, str]], defecto: str) -> str:
    casos = " ".join(f"WHEN regexp_matches(upper({columna}), '{p}') THEN '{n}'" for n, p in reglas)
    return f"CASE {casos} ELSE '{defecto}' END"


def familia_de(denominacion: str) -> str:
    """Misma regla que la vista SQL, para usar en Python."""
    d = (denominacion or "").upper()
    for nombre, patron in FAMILIAS:
        if re.search(patron, d):
            return nombre
    return "Otros"


def _filas_excel(path: Path, hoja: str | None = None) -> Iterator[list]:
    """Lee una hoja de Excel en modo ``read_only`` (rápido, poca RAM). Encabezados repetidos → ``#2``."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[hoja] if hoja else wb.worksheets[0]
    vistos: dict[str, int] = {}
    for i, fila in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            cab = []
            for c in fila:
                c = str(c or "").strip()
                vistos[c] = vistos.get(c, 0) + 1
                cab.append(c if vistos[c] == 1 else f"{c}#{vistos[c]}")
            yield cab
            continue
        if not any(v not in (None, "") for v in fila):
            continue
        yield [
            v.date().isoformat() if isinstance(v, datetime) else v.isoformat() if isinstance(v, date) else v
            for v in fila
        ]
    wb.close()


def _a_csv(path: Path, hoja: str | None, destino: Path) -> Path:
    with destino.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for fila in _filas_excel(path, hoja):
            w.writerow(["" if v is None else v for v in fila])
    return destino


ESQUEMA = """
CREATE OR REPLACE TABLE equipos AS
SELECT trim("Equipo") AS equipo, trim("Denominación") AS denominacion, trim("Nº de modelo") AS modelo,
       trim("NºPieza fabric.") AS pieza_fabricante, trim("Fabr. Nº-serie") AS serie,
       trim("Ubicac.técnica") AS ubicacion, trim("Denominación#2") AS ubicacion_texto,
       trim("Centro coste") AS centro_coste, trim("Estado sistema") AS estado, trim("Status usuario") AS status_usuario,
       TRY_CAST("Fe.puesta serv." AS DATE) AS puesta_servicio, TRY_CAST("Fe.creación" AS DATE) AS creado
FROM read_csv('{equipos}', header=true, all_varchar=true)
WHERE trim("Equipo") <> ''
QUALIFY row_number() OVER (PARTITION BY trim("Equipo") ORDER BY TRY_CAST("Fe.modificación" AS DATE) DESC NULLS LAST) = 1;

CREATE OR REPLACE TABLE materiales AS
SELECT trim("Material") AS material, trim("Descripción material") AS texto, trim("Tipo de material") AS tipo,
       trim("Grupo de artículos") AS grupo, trim("Unidad medida base") AS unidad,
       TRY_CAST("Precio" AS DOUBLE) AS precio, nullif(trim("Indicador ABC"), '') AS abc,
       TRY_CAST("Última modificación" AS DATE) AS modificado
FROM read_csv('{materiales}', header=true, all_varchar=true)
WHERE trim("Material") <> ''
QUALIFY row_number() OVER (PARTITION BY trim("Material") ORDER BY TRY_CAST("Última modificación" AS DATE) DESC NULLS LAST) = 1;

CREATE OR REPLACE TABLE consumos AS
SELECT trim("Equipo") AS equipo, trim("Denominación del equipo") AS denominacion, trim("CMv") AS movimiento,
       trim("Doc.mat.") AS documento, trim("Material") AS material, trim("Texto breve de material") AS texto_material,
       trim("Nombre del usuario") AS usuario, trim("Orden") AS orden,
       TRY_CAST("Cantidad" AS DOUBLE) AS cantidad, TRY_CAST("Importe ML" AS DOUBLE) AS importe,
       TRY_CAST("Fe.contab." AS DATE) AS fecha, trim("UMB") AS unidad, trim("Ce.coste") AS centro_coste,
       trim("Alm.") AS almacen
FROM read_csv('{consumos}', header=true, all_varchar=true)
WHERE trim("Equipo") <> '' AND TRY_CAST("Fe.contab." AS DATE) IS NOT NULL;

CREATE OR REPLACE VIEW consumo_neto AS
SELECT c.*,
       CASE WHEN c.movimiento IN ('262', '102') THEN -1 ELSE 1 END AS signo,
       abs(c.cantidad) * CASE WHEN c.movimiento IN ('262', '102') THEN -1 ELSE 1 END AS cantidad_neta,
       abs(c.importe) * CASE WHEN c.movimiento IN ('262', '102') THEN -1 ELSE 1 END AS importe_neto,
       {familia} AS familia,
       {marca} AS marca
FROM consumos c
WHERE c.movimiento IN ('261', '262', '101', '102');

CREATE OR REPLACE VIEW flota AS
SELECT e.*, {familia_e} AS familia, {marca_e} AS marca
FROM equipos e;
"""


def cargar_csv(equipos: Path, materiales: Path, consumos: Path, destino: Path) -> dict[str, int]:
    """Crea (o reemplaza) la base DuckDB desde tres CSV con los encabezados de SAP."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    sql = ESQUEMA.format(
        equipos=equipos.as_posix(),
        materiales=materiales.as_posix(),
        consumos=consumos.as_posix(),
        familia=_regla_sql("coalesce(c.denominacion, '')", FAMILIAS, "Otros"),
        marca=_regla_sql("coalesce(c.denominacion, '')", MARCAS, "Otra"),
        familia_e=_regla_sql("coalesce(e.denominacion, '')", FAMILIAS, "Otros"),
        marca_e=_regla_sql("coalesce(e.denominacion, '')", MARCAS, "Otra"),
    )
    con.execute(sql)
    conteo = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("equipos", "materiales", "consumos")}
    con.close()
    tmp.replace(destino)  # reemplazo atómico: la app nunca ve una base a medias
    return conteo


def construir_base(
    equipos_xlsx: Path, historial_xlsx: Path, materiales_xlsx: Path, destino: Path, hoja_materiales: str = "RawData"
) -> dict[str, int]:
    """Excel de SAP → CSV temporales → DuckDB."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        return cargar_csv(
            _a_csv(equipos_xlsx, None, d / "equipos.csv"),
            _a_csv(materiales_xlsx, hoja_materiales, d / "materiales.csv"),
            _a_csv(historial_xlsx, None, d / "consumos.csv"),
            destino,
        )


def conectar(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Conexión de solo lectura (el agente nunca escribe en la base de SAP)."""
    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"No existe la base del taller en {db_path}. Constrúyela con: "
            "uv run python scripts/build_taller.py --equipos ... --historial ... --materiales ...  "
            "(o usa la muestra: --muestra)"
        )
    return duckdb.connect(str(db_path), read_only=True)

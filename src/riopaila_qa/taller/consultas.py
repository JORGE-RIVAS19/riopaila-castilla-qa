"""Consultas deterministas sobre la base del taller (DuckDB).

Todas las ventanas de tiempo se cuentan hacia atrás desde la **fecha de corte** (el último
movimiento cargado), no desde hoy: así las respuestas son reproducibles con cualquier exporte.
Ninguna función usa el LLM. Las cifras que ve el usuario salen de aquí.
"""

from __future__ import annotations

import re
import statistics
from datetime import date, timedelta

import duckdb
from pydantic import BaseModel
from rapidfuzz import fuzz, process


# --------------------------------------------------------------------------- modelos
class Equipo(BaseModel):
    equipo: str
    denominacion: str
    familia: str
    marca: str
    modelo: str | None = None
    ubicacion: str | None = None
    estado: str | None = None
    gasto_12m: float = 0.0


class LineaConsumo(BaseModel):
    fecha: date
    orden: str | None
    material: str | None
    texto_material: str | None
    cantidad: float
    unidad: str | None
    importe: float
    movimiento: str


class FichaEquipo(BaseModel):
    equipo: Equipo
    gasto_total: float
    gasto_12m: float
    ordenes_12m: int
    primer_consumo: date | None
    ultimo_consumo: date | None
    top_materiales: list[dict]


class PuntoSerie(BaseModel):
    periodo: str  # AAAA-MM
    valor: float


class Repuesto(BaseModel):
    material: str
    texto: str
    precio: float | None = None
    unidad: str | None = None
    abc: str | None = None
    usos_12m: int = 0
    equipos_12m: int = 0
    ultimo_uso: date | None = None
    similitud: float = 0.0


class Anomalia(BaseModel):
    equipo: str
    denominacion: str
    material: str
    texto_material: str
    cantidad_reciente: float
    cantidad_esperada: float
    veces: float
    importe_reciente: float
    eventos_recientes: int
    explicacion: str


class Reposicion(BaseModel):
    material: str
    texto_material: str
    eventos: int
    intervalo_dias: int
    ultima: date
    proxima_estimada: date
    cantidad_tipica: float
    unidad: str | None
    costo_estimado: float
    confianza: str  # alta | media | baja


# --------------------------------------------------------------------------- utilidades
def fecha_corte(con: duckdb.DuckDBPyConnection) -> date:
    return con.execute("SELECT max(fecha) FROM consumo_neto").fetchone()[0]


def _desde(con, dias: int) -> date:
    return fecha_corte(con) - timedelta(days=dias)


def _dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def _norm(texto: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (texto or "").upper())


# --------------------------------------------------------------------------- flota
def buscar_equipo(con, texto: str, familia: str | None = None, limite: int = 8) -> list[Equipo]:
    """Por código exacto o por palabras de la denominación (todas deben aparecer)."""
    texto = (texto or "").strip()
    desde = _desde(con, 365)
    base = """
        SELECT f.equipo, f.denominacion, f.familia, f.marca, f.modelo, f.ubicacion_texto AS ubicacion, f.estado,
               coalesce(g.gasto, 0) AS gasto_12m
        FROM flota f
        LEFT JOIN (SELECT equipo, sum(importe_neto) gasto FROM consumo_neto WHERE fecha > ? GROUP BY 1) g USING (equipo)
    """
    if re.fullmatch(r"\d{4,8}", texto):
        filas = _dicts(con.execute(base + " WHERE f.equipo = ?", [desde, texto]))
        if filas:
            return [Equipo(**f) for f in filas]
    palabras = [p for p in re.split(r"\s+", texto.upper()) if p]
    cond, params = [], [desde]
    for p in palabras:
        cond.append("(upper(f.denominacion) LIKE ? OR upper(coalesce(f.modelo,'')) LIKE ? OR f.equipo = ?)")
        params += [f"%{p}%", f"%{p}%", p]
    if familia:
        cond.append("f.familia = ?")
        params.append(familia)
    where = " WHERE " + " AND ".join(cond) if cond else ""
    sql = base + where + " ORDER BY gasto_12m DESC, f.equipo LIMIT ?"
    return [Equipo(**f) for f in _dicts(con.execute(sql, [*params, limite]))]


def ficha_equipo(con, equipo: str) -> FichaEquipo | None:
    eq = buscar_equipo(con, equipo, limite=1)
    if not eq or eq[0].equipo != equipo.strip():
        return None
    desde = _desde(con, 365)
    tot = con.execute(
        """SELECT sum(importe_neto), sum(importe_neto) FILTER (WHERE fecha > ?),
                  count(DISTINCT orden) FILTER (WHERE fecha > ?), min(fecha), max(fecha)
           FROM consumo_neto WHERE equipo = ?""",
        [desde, desde, equipo],
    ).fetchone()
    top = _dicts(
        con.execute(
            """SELECT material, any_value(texto_material) texto_material, sum(cantidad_neta) cantidad,
                      any_value(unidad) unidad, sum(importe_neto) importe
               FROM consumo_neto WHERE equipo = ? AND fecha > ? GROUP BY 1 HAVING sum(importe_neto) > 0
               ORDER BY importe DESC LIMIT 5""",
            [equipo, desde],
        )
    )
    return FichaEquipo(
        equipo=eq[0],
        gasto_total=tot[0] or 0,
        gasto_12m=tot[1] or 0,
        ordenes_12m=tot[2] or 0,
        primer_consumo=tot[3],
        ultimo_consumo=tot[4],
        top_materiales=top,
    )


def flota_por_familia(con, familia: str | None = None) -> list[dict]:
    """Equipos con consumo en los últimos 12 meses (= flota activa) por familia y marca."""
    desde = _desde(con, 365)
    grupo = "familia, marca" if familia else "familia"
    filtro = "AND familia = ?" if familia else ""
    params = [desde] + ([familia] if familia else [])
    return _dicts(
        con.execute(
            f"""SELECT {grupo}, count(DISTINCT equipo) equipos_activos, sum(importe_neto) gasto_12m,
                       sum(importe_neto) / count(DISTINCT equipo) gasto_promedio_equipo
                FROM consumo_neto WHERE fecha > ? {filtro} GROUP BY ALL ORDER BY gasto_12m DESC""",
            params,
        )
    )


def ranking_gasto(con, familia: str | None = None, dias: int = 90, top: int = 10) -> list[dict]:
    filtro = "AND familia = ?" if familia else ""
    params = [_desde(con, dias)] + ([familia] if familia else []) + [top]
    return _dicts(
        con.execute(
            f"""SELECT equipo, any_value(denominacion) denominacion, any_value(familia) familia,
                       sum(importe_neto) gasto, count(DISTINCT orden) ordenes
                FROM consumo_neto WHERE fecha > ? {filtro} GROUP BY equipo ORDER BY gasto DESC LIMIT ?""",
            params,
        )
    )


# --------------------------------------------------------------------------- consumos
def historial_consumo(
    con, equipo: str, dias: int = 90, texto: str | None = None, limite: int = 40
) -> list[LineaConsumo]:
    cond, params = ["equipo = ?", "fecha > ?"], [equipo, _desde(con, dias)]
    for p in (texto or "").upper().split():
        cond.append("upper(texto_material) LIKE ?")
        params.append(f"%{p}%")
    sql = f"""SELECT fecha, orden, material, texto_material, cantidad_neta cantidad, unidad, importe_neto importe, movimiento
              FROM consumo_neto WHERE {" AND ".join(cond)} ORDER BY fecha DESC, importe DESC LIMIT ?"""
    return [LineaConsumo(**f) for f in _dicts(con.execute(sql, [*params, limite]))]


def detalle_orden(con, orden: str) -> dict | None:
    lineas = _dicts(
        con.execute(
            """SELECT fecha, material, texto_material, cantidad_neta cantidad, unidad, importe_neto importe, movimiento,
                      equipo, denominacion
               FROM consumo_neto WHERE orden = ? ORDER BY importe DESC""",
            [orden.strip()],
        )
    )
    if not lineas:
        return None
    return {
        "orden": orden.strip(),
        "equipo": lineas[0]["equipo"],
        "denominacion": lineas[0]["denominacion"],
        "desde": min(r["fecha"] for r in lineas),
        "hasta": max(r["fecha"] for r in lineas),
        "total": sum(r["importe"] or 0 for r in lineas),
        "lineas": [{k: v for k, v in r.items() if k not in ("equipo", "denominacion")} for r in lineas],
    }


def donde_se_usa(con, material: str, dias: int = 365, top: int = 10) -> list[dict]:
    material = material.strip()
    if re.fullmatch(r"\d{5,10}", material):
        cond, params = "material = ?", [material]
    else:
        palabras = material.upper().split()
        cond = " AND ".join("upper(texto_material) LIKE ?" for _ in palabras) or "TRUE"
        params = [f"%{p}%" for p in palabras]
    return _dicts(
        con.execute(
            f"""SELECT equipo, any_value(denominacion) denominacion, any_value(texto_material) texto_material,
                       sum(cantidad_neta) cantidad, any_value(unidad) unidad, sum(importe_neto) importe,
                       count(DISTINCT orden) ordenes, max(fecha) ultima_vez
                FROM consumo_neto WHERE {cond} AND fecha > ? GROUP BY equipo
                HAVING sum(cantidad_neta) > 0 ORDER BY importe DESC LIMIT ?""",
            [*params, _desde(con, dias), top],
        )
    )


def serie_gasto(con, equipo: str | None = None, familia: str | None = None, meses: int = 12) -> list[PuntoSerie]:
    corte = fecha_corte(con)
    total = corte.year * 12 + corte.month - 1 - (meses - 1)
    inicio = date(total // 12, total % 12 + 1, 1)
    cond, params = ["fecha >= ?"], [inicio]
    if equipo:
        cond.append("equipo = ?")
        params.append(equipo)
    if familia:
        cond.append("familia = ?")
        params.append(familia)
    filas = con.execute(
        f"""WITH meses AS (SELECT strftime(m, '%Y-%m') periodo FROM range(?::DATE, ?::DATE + 1, INTERVAL 1 MONTH) t(m))
            SELECT meses.periodo, coalesce(sum(c.importe_neto), 0) valor
            FROM meses LEFT JOIN (SELECT strftime(fecha, '%Y-%m') periodo, importe_neto FROM consumo_neto
                                  WHERE {" AND ".join(cond)}) c USING (periodo)
            GROUP BY 1 ORDER BY 1""",
        [inicio, corte, *params],
    ).fetchall()
    return [PuntoSerie(periodo=p, valor=v) for p, v in filas]


# --------------------------------------------------------------------------- repuestos
_CACHE_MATERIALES: dict[int, tuple[list[str], list[str]]] = {}


def _materiales(con) -> tuple[list[str], list[str]]:
    clave = id(con)
    if clave not in _CACHE_MATERIALES:
        filas = con.execute("SELECT material, texto FROM materiales WHERE texto IS NOT NULL").fetchall()
        _CACHE_MATERIALES[clave] = ([f[0] for f in filas], [f[1].upper() for f in filas])
    return _CACHE_MATERIALES[clave]


def _enriquecer(con, codigos: list[str], similitud: dict[str, float]) -> list[Repuesto]:
    if not codigos:
        return []
    filas = _dicts(
        con.execute(
            """SELECT m.material, m.texto, m.precio, m.unidad, m.abc,
                      coalesce(u.usos, 0) usos_12m, coalesce(u.equipos, 0) equipos_12m, u.ultimo ultimo_uso
               FROM materiales m LEFT JOIN (
                   SELECT material, count(*) usos, count(DISTINCT equipo) equipos, max(fecha) ultimo
                   FROM consumo_neto WHERE fecha > ? GROUP BY 1) u USING (material)
               WHERE m.material IN (SELECT unnest(?))""",
            [_desde(con, 365), codigos],
        )
    )
    res = [Repuesto(**f, similitud=round(similitud.get(f["material"], 100.0), 1)) for f in filas]
    return sorted(res, key=lambda r: (-r.similitud, -r.usos_12m))


def buscar_repuesto(con, texto: str, limite: int = 8) -> list[Repuesto]:
    """Búsqueda difusa sobre el texto breve del maestro de materiales (o código exacto)."""
    texto = (texto or "").strip()
    if re.fullmatch(r"\d{5,10}", texto):
        exacto = _enriquecer(con, [texto], {texto: 100.0})
        if exacto:
            return exacto
    codigos, textos = _materiales(con)
    hallados = process.extract(texto.upper(), textos, scorer=fuzz.token_set_ratio, limit=limite * 4, score_cutoff=55)
    sim = {codigos[i]: s for _, s, i in hallados}
    return _enriquecer(con, list(sim), sim)[:limite]


def verificar_codigo(con, referencia: str) -> list[Repuesto]:
    """¿La referencia del fabricante ya está en algún texto breve de SAP? (ignora espacios, guiones y puntos)."""
    ref = _norm(referencia)
    if len(ref) < 4:
        return []
    codigos = [
        r[0]
        for r in con.execute(
            "SELECT material FROM materiales WHERE regexp_replace(upper(texto), '[^A-Z0-9]', '', 'g') LIKE ?",
            [f"%{ref}%"],
        ).fetchall()
    ]
    return _enriquecer(con, codigos, {})


def repuestos_frecuentes(con, equipo: str, dias: int = 730, top: int = 12) -> list[dict]:
    """(Solo repuestos: códigos numéricos; los servicios MQ/MT quedan fuera.) Lo que más se cambia en los equipos con la misma denominación (mismo modelo) que ``equipo``."""
    return _dicts(
        con.execute(
            """WITH modelo AS (SELECT denominacion FROM flota WHERE equipo = ?)
               SELECT material, any_value(texto_material) texto_material, count(DISTINCT orden) veces,
                      count(DISTINCT equipo) equipos, sum(cantidad_neta) cantidad, any_value(unidad) unidad,
                      sum(importe_neto) importe
               FROM consumo_neto WHERE denominacion = (SELECT denominacion FROM modelo) AND fecha > ?
                 AND regexp_matches(material, '^[0-9]+$')
               GROUP BY material HAVING sum(cantidad_neta) > 0 ORDER BY veces DESC, importe DESC LIMIT ?""",
            [equipo, _desde(con, dias), top],
        )
    )


# --------------------------------------------------------------------------- inteligencia
def detectar_anomalias(
    con,
    dias: int = 30,
    familia: str | None = None,
    umbral: float = 3.0,
    top: int = 8,
    importe_minimo: float = 1_500_000,
) -> list[Anomalia]:
    """Consumo reciente (equipo × material) ``umbral`` veces por encima de su ritmo del año anterior.

    Regla explicable: esperado = cantidad del año previo × (dias / 365). Se exige historia (≥2 eventos
    previos) e importe reciente relevante, para no alertar por un solo tornillo.
    """
    corte = fecha_corte(con)
    ini = corte - timedelta(days=dias)
    base_ini = ini - timedelta(days=365)
    filtro = "AND familia = $familia" if familia else ""
    params = {
        "ini": ini,
        "base_ini": base_ini,
        "factor": dias / 365.0,
        "umbral": umbral,
        "minimo": importe_minimo,
        "top": top,
    } | ({"familia": familia} if familia else {})
    filas = _dicts(
        con.execute(
            f"""WITH t AS (
                  SELECT equipo, any_value(denominacion) denominacion, material, any_value(texto_material) texto_material,
                         sum(cantidad_neta) FILTER (WHERE fecha > $ini) reciente,
                         sum(importe_neto) FILTER (WHERE fecha > $ini) importe_reciente,
                         count(DISTINCT orden) FILTER (WHERE fecha > $ini) eventos_recientes,
                         sum(cantidad_neta) FILTER (WHERE fecha <= $ini) previo,
                         count(DISTINCT fecha) FILTER (WHERE fecha <= $ini) eventos_previos
                  FROM consumo_neto WHERE fecha > $base_ini AND regexp_matches(material, '^[0-9]+$') {filtro}
                  GROUP BY equipo, material)
                SELECT *, previo * $factor esperado FROM t
                WHERE eventos_previos >= 2 AND previo > 0 AND reciente >= $umbral * previo * $factor
                  AND importe_reciente >= $minimo
                ORDER BY importe_reciente DESC LIMIT $top""",
            params,
        )
    )
    res = []
    for f in filas:
        veces = f["reciente"] / f["esperado"] if f["esperado"] else 0
        res.append(
            Anomalia(
                equipo=f["equipo"],
                denominacion=f["denominacion"],
                material=f["material"],
                texto_material=f["texto_material"],
                cantidad_reciente=f["reciente"],
                cantidad_esperada=round(f["esperado"], 2),
                veces=round(veces, 1),
                importe_reciente=f["importe_reciente"],
                eventos_recientes=f["eventos_recientes"],
                explicacion=(
                    f"{f['reciente']:g} en {dias} días frente a ~{f['esperado']:.1f} esperados según el año anterior "
                    f"({veces:.1f}×) en {f['eventos_recientes']} orden(es)."
                ),
            )
        )
    return res


def predecir_reposicion(con, equipo: str, horizonte_dias: int = 30, min_eventos: int = 3) -> list[Reposicion]:
    """Próximo cambio de cada repuesto según el intervalo mediano entre cambios del propio equipo."""
    corte = fecha_corte(con)
    filas = con.execute(
        """SELECT material, any_value(texto_material), any_value(unidad), fecha, sum(cantidad_neta), sum(importe_neto)
           FROM consumo_neto WHERE equipo = ? AND fecha > ? AND regexp_matches(material, '^[0-9]+$')
           GROUP BY material, fecha HAVING sum(cantidad_neta) > 0 ORDER BY material, fecha""",
        [equipo, corte - timedelta(days=730)],
    ).fetchall()
    por_material: dict[str, list] = {}
    for f in filas:
        por_material.setdefault(f[0], []).append(f)
    res = []
    for material, eventos in por_material.items():
        if len(eventos) < min_eventos:
            continue
        fechas = [e[3] for e in eventos]
        intervalos = [(b - a).days for a, b in zip(fechas, fechas[1:], strict=False) if (b - a).days >= 3]
        if len(intervalos) < min_eventos - 1:
            continue
        medio = statistics.median(intervalos)
        proxima = fechas[-1] + timedelta(days=round(medio))
        vencida = (corte - proxima).days
        if vencida > min(30, medio / 2) or (proxima - corte).days > horizonte_dias:
            continue
        cv = statistics.pstdev(intervalos) / medio if medio else 9
        cantidad = statistics.median(e[4] for e in eventos)
        precio = eventos[-1][5] / eventos[-1][4] if eventos[-1][4] else 0
        res.append(
            Reposicion(
                material=material,
                texto_material=eventos[-1][1],
                eventos=len(eventos),
                intervalo_dias=round(medio),
                ultima=fechas[-1],
                proxima_estimada=proxima,
                cantidad_tipica=cantidad,
                unidad=eventos[-1][2],
                costo_estimado=round(cantidad * precio),
                confianza="alta" if cv < 0.35 else "media" if cv < 0.7 else "baja",
            )
        )
    orden = {"alta": 0, "media": 1, "baja": 2}
    return sorted(res, key=lambda r: (orden[r.confianza], r.proxima_estimada))

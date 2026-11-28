"""Las 17 herramientas del Taller Castilla (function calling con ``@tool`` + esquema Pydantic).

| Grupo         | Herramientas                                                                     |
|---------------|----------------------------------------------------------------------------------|
| Flota         | buscar_equipo · ficha_equipo · flota_por_familia · ranking_gasto_equipos        |
| Consumos      | historial_consumo · detalle_orden · donde_se_usa_material · grafica_gasto        |
| Repuestos     | buscar_repuesto · verificar_codigo_sap · repuestos_frecuentes ·                  |
|               | identificar_repuesto_por_foto                                                    |
| Inteligencia  | detectar_anomalias · predecir_reposicion · generar_informe_pdf                   |
| Conocimiento  | buscar_manual (responde con la foto de la página, lo buscado resaltado)          |
| Acción (HITL) | registrar_novedad (pide confirmación con ``interrupt`` y exige rol de taller)    |

Con las 3 del Módulo 2 que siguen activas (buscar_documentos, consultar_indicadores, comparar_cifras,
recordar_dato_usuario) el agente tiene 21 herramientas. Todas devuelven ``(contenido, artefacto)``: el
contenido va al LLM; el artefacto va a la app, a la traza y, en ``media``, las imágenes y PDF que el
puente de WhatsApp envía al usuario.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import duckdb
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from riopaila_qa.agent.tools import AgentContext
from riopaila_qa.taller import consultas as q
from riopaila_qa.taller import graficas, novedades, vision
from riopaila_qa.taller.config import TallerSettings
from riopaila_qa.taller.manuales import BuscadorManuales, renderizar_pagina

FAMILIA = Literal[
    "Cosechadora",
    "Tractor",
    "Tractomula",
    "Alzadora",
    "Vagones y remolques",
    "Camiones y camionetas",
    "Maquinaria amarilla",
    "Implementos agrícolas",
    "Riego y bombeo",
    "Motores y equipos de taller",
    "Otros",
]
ROLES_TALLER = {"supervisor", "tecnico"}
SI = re.compile(r"^\s*(s[ií]|ok|dale|confirm\w*|claro|correcto|de una|h[aá]gale|listo)\b", re.IGNORECASE)
IMAGEN = re.compile(r"(\.(jpe?g|png|webp|heic)$)|^data:image", re.IGNORECASE)


@dataclass
class TallerDeps:
    con: duckdb.DuckDBPyConnection  # solo lectura
    settings: TallerSettings
    manuales: BuscadorManuales | None = None
    vision_llm: BaseChatModel | None = None


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _mill(v: float | None) -> str:
    return graficas.millones(v or 0)


# ------------------------------------------------------------------------------- esquemas
class BuscarEquipo(BaseModel):
    texto: str = Field(
        description="Código SAP del equipo (p. ej. 25375) o palabras de su nombre ('puma 165', 'ch570')."
    )
    familia: FAMILIA | None = Field(None, description="Filtro opcional por familia de equipo.")


class CodigoEquipo(BaseModel):
    equipo: str = Field(description="Código SAP del equipo.")


class FlotaFamilia(BaseModel):
    familia: FAMILIA | None = Field(None, description="Familia a detallar por marca; vacío = toda la flota.")


class Ranking(BaseModel):
    familia: FAMILIA | None = None
    dias: int = Field(90, ge=7, le=1095, description="Ventana en días hasta la fecha de corte.")
    top: int = Field(10, ge=3, le=20)


class Historial(BaseModel):
    equipo: str = Field(description="Código SAP del equipo.")
    dias: int = Field(90, ge=1, le=1095)
    texto: str | None = Field(None, description="Filtrar por palabras del material (p. ej. 'filtro', 'llanta').")


class Orden(BaseModel):
    orden: str = Field(description="Número de la orden de mantenimiento en SAP.")


class DondeSeUsa(BaseModel):
    material: str = Field(description="Código SAP del material o palabras de su texto breve.")
    dias: int = Field(365, ge=7, le=1095)


class Grafica(BaseModel):
    equipo: str | None = Field(None, description="Código SAP; vacío para graficar una familia o toda la flota.")
    familia: FAMILIA | None = None
    meses: int = Field(12, ge=3, le=36)


class BuscarRepuesto(BaseModel):
    texto: str = Field(
        description="Descripción del repuesto ('filtro hidráulico puma', 'cuchilla picador') o código SAP."
    )


class Verificar(BaseModel):
    referencia: str = Field(description="Número de parte del fabricante (p. ej. 47715391, 11423828, 84-228488).")


class Foto(BaseModel):
    nota: str = Field("", description="Lo que el usuario dijo de la foto (máquina, sistema, síntoma).")


class Anomalias(BaseModel):
    dias: int = Field(30, ge=7, le=180, description="Ventana reciente a comparar contra el año anterior.")
    familia: FAMILIA | None = None


class Prediccion(BaseModel):
    equipo: str = Field(description="Código SAP del equipo.")
    horizonte_dias: int = Field(30, ge=7, le=180)


class Informe(BaseModel):
    equipo: str | None = Field(None, description="Código SAP; vacío para un informe por familia o de toda la flota.")
    familia: FAMILIA | None = None
    meses: int = Field(6, ge=1, le=24)


class BuscarManual(BaseModel):
    consulta: str = Field(
        description="Procedimiento, componente o código ('cambio filtro hidráulico', 'fusible radio')."
    )
    modelo: str | None = Field(None, description="Modelo de la máquina: 'PUMA 165', '6165J', '2254', 'T800', '77ATX'…")
    tipo: Literal["operador", "servicio", "partes", "diagnostico", "diagrama"] | None = Field(
        None, description="diagrama = planos eléctricos y caja de fusibles (tractomulas Kenworth)."
    )


class RegistrarNovedad(BaseModel):
    equipo: str = Field(description="Código SAP del equipo (búscalo antes con buscar_equipo si no lo tienes).")
    descripcion: str = Field(description="Qué pasa, con las palabras del técnico.")
    sistema: str = Field("", description="hidráulico, motor, transmisión, eléctrico, llantas, frenos, chasis…")
    prioridad: Literal["alta", "media", "baja"] = Field("media", description="alta = equipo parado.")


# ------------------------------------------------------------------------------- herramientas
def build_taller_tools(deps: TallerDeps):
    s = deps.settings

    def cur() -> duckdb.DuckDBPyConnection:
        return deps.con.cursor()  # un cursor por llamada: seguro entre hilos de FastAPI

    def media(ruta: Path, tipo: str, pie: str) -> dict:
        try:
            rel = ruta.relative_to(s.media_dir).as_posix()
        except ValueError:
            rel = ruta.name
        url = f"{s.media_base_url.rstrip('/')}/media/{rel}" if s.media_base_url else f"/media/{rel}"
        return {"tipo": tipo, "ruta": str(ruta), "url": url, "pie": pie}

    # ---------------------------------------------------------------- Flota
    @tool("buscar_equipo", args_schema=BuscarEquipo, response_format="content_and_artifact")
    def buscar_equipo(texto: str, familia: str | None = None):
        """Encuentra equipos de la flota por código SAP o por nombre/modelo, con su gasto de los últimos 12 meses.
        Úsala primero cuando el usuario nombre una máquina sin dar su código."""
        res = [r.model_dump() for r in q.buscar_equipo(cur(), texto, familia)]
        contenido = {"encontrados": len(res), "equipos": [{**r, "gasto_12m": _mill(r["gasto_12m"])} for r in res]}
        return _json(contenido), {"equipos": res}

    @tool("ficha_equipo", args_schema=CodigoEquipo, response_format="content_and_artifact")
    def ficha_equipo(equipo: str):
        """Hoja de vida de un equipo: datos SAP, gasto total y de 12 meses, órdenes y los 5 materiales de mayor gasto."""
        f = q.ficha_equipo(cur(), equipo)
        if f is None:
            return _json({"error": f"No encontré el equipo {equipo}."}), {"ficha": None}
        d = f.model_dump()
        top = [{**t, "importe": _mill(t["importe"])} for t in d["top_materiales"]]
        return _json(
            {**d, "gasto_total": _mill(f.gasto_total), "gasto_12m": _mill(f.gasto_12m), "top_materiales": top}
        ), {"ficha": d}

    @tool("flota_por_familia", args_schema=FlotaFamilia, response_format="content_and_artifact")
    def flota_por_familia(familia: str | None = None):
        """Cuántos equipos activos hay por familia (o por marca dentro de una familia) y cuánto gastaron en 12 meses."""
        filas = q.flota_por_familia(cur(), familia)
        contenido = [
            {**r, "gasto_12m": _mill(r["gasto_12m"]), "gasto_promedio_equipo": _mill(r["gasto_promedio_equipo"])}
            for r in filas
        ]
        return _json({"fecha_corte": q.fecha_corte(cur()), "filas": contenido}), {"filas": filas}

    @tool("ranking_gasto_equipos", args_schema=Ranking, response_format="content_and_artifact")
    def ranking_gasto_equipos(familia: str | None = None, dias: int = 90, top: int = 10):
        """Los equipos que más gastaron en mantenimiento en una ventana de días. Envía una gráfica de barras."""
        filas = q.ranking_gasto(cur(), familia, dias, top)
        corte = q.fecha_corte(cur())
        img = graficas.grafica_ranking(
            [(f"{r['equipo']} · {r['denominacion']}", r["gasto"]) for r in filas],
            f"Equipos con mayor gasto · {familia or 'toda la flota'}",
            f"Últimos {dias} días al {corte:%d/%m/%Y} · millones COP",
            s.media_dir / "graficas",
        )
        contenido = {
            "fecha_corte": corte,
            "ranking": [{**r, "gasto": _mill(r["gasto"])} for r in filas],
            "nota": "La gráfica ya se envió al usuario.",
        }
        return _json(contenido), {"filas": filas, "media": [media(img, "imagen", f"Ranking de gasto · {dias} días")]}

    # ---------------------------------------------------------------- Consumos
    @tool("historial_consumo", args_schema=Historial, response_format="content_and_artifact")
    def historial_consumo(equipo: str, dias: int = 90, texto: str | None = None):
        """Qué materiales y servicios se le cargaron a un equipo (fecha, orden, cantidad, importe)."""
        lineas = [r.model_dump() for r in q.historial_consumo(cur(), equipo, dias, texto)]
        total = sum(r["importe"] or 0 for r in lineas)
        detalle = [{**r, "importe": _mill(r["importe"])} for r in lineas[:25]]
        return _json(
            {"fecha_corte": q.fecha_corte(cur()), "lineas": len(lineas), "total": _mill(total), "detalle": detalle}
        ), {"lineas": lineas}

    @tool("detalle_orden", args_schema=Orden, response_format="content_and_artifact")
    def detalle_orden(orden: str):
        """Todo lo que se cargó a una orden de mantenimiento: equipo, fechas, materiales y total."""
        d = q.detalle_orden(cur(), orden)
        if d is None:
            return _json({"error": f"No encontré la orden {orden}."}), {"orden": None}
        lineas = [{**r, "importe": _mill(r["importe"])} for r in d["lineas"][:30]]
        return _json({**{k: v for k, v in d.items() if k != "lineas"}, "total": _mill(d["total"]), "lineas": lineas}), {
            "orden": d
        }

    @tool("donde_se_usa_material", args_schema=DondeSeUsa, response_format="content_and_artifact")
    def donde_se_usa_material(material: str, dias: int = 365):
        """En qué equipos se consume un repuesto o insumo, cuánto y cuándo fue la última vez."""
        filas = q.donde_se_usa(cur(), material, dias)
        return _json({"equipos": [{**r, "importe": _mill(r["importe"])} for r in filas]}), {"filas": filas}

    @tool("grafica_gasto", args_schema=Grafica, response_format="content_and_artifact")
    def grafica_gasto(equipo: str | None = None, familia: str | None = None, meses: int = 12):
        """Gráfica del gasto mensual (imagen para WhatsApp) de un equipo, una familia o toda la flota."""
        serie = q.serie_gasto(cur(), equipo, familia, meses)
        if not any(p.valor for p in serie):
            return _json({"error": "No hay consumos en ese periodo."}), {"serie": []}
        nombre = q.buscar_equipo(cur(), equipo, limite=1) if equipo else []
        sujeto = f"{equipo} · {nombre[0].denominacion}" if nombre else (familia or "Toda la flota")
        total = sum(p.valor for p in serie)
        corte = q.fecha_corte(cur())
        img = graficas.grafica_barras_mensual(
            [(p.periodo, p.valor) for p in serie],
            f"Gasto de mantenimiento · {sujeto}",
            f"Últimos {meses} meses · total {_mill(total)} COP · datos al {corte:%d/%m/%Y}",
            s.media_dir / "graficas",
            ultimo_parcial=corte.day < 28,
        )
        pico = max(serie, key=lambda p: p.valor)
        contenido = {
            "fecha_corte": corte,
            "total": _mill(total),
            "promedio_mensual": _mill(total / len(serie)),
            "mes_mayor_gasto": {"mes": pico.periodo, "valor": _mill(pico.valor)},
            "nota": "La gráfica ya se envió al usuario; comenta la tendencia sin repetir cada mes.",
        }
        return _json(contenido), {
            "serie": [p.model_dump() for p in serie],
            "media": [media(img, "imagen", f"Gasto mensual · {sujeto}")],
        }

    # ---------------------------------------------------------------- Repuestos
    @tool("buscar_repuesto", args_schema=BuscarRepuesto, response_format="content_and_artifact")
    def buscar_repuesto(texto: str):
        """Busca en el maestro de materiales de SAP (búsqueda difusa sobre el texto breve): código, precio, ABC y uso."""
        res = [r.model_dump() for r in q.buscar_repuesto(cur(), texto)]
        return _json({"resultados": res}), {"repuestos": res}

    @tool("verificar_codigo_sap", args_schema=Verificar, response_format="content_and_artifact")
    def verificar_codigo_sap(referencia: str):
        """Antes de pedir la creación de un código nuevo: verifica si la referencia del fabricante ya tiene código SAP
        (busca la referencia dentro del texto breve del maestro de materiales, ignorando guiones y espacios)."""
        res = [r.model_dump() for r in q.verificar_codigo(cur(), referencia)]
        msg = (
            f"Ya existe: {len(res)} código(s) SAP contienen la referencia {referencia}."
            if res
            else f"No hay ningún código SAP con la referencia {referencia}: se puede solicitar su creación."
        )
        return _json({"existe": bool(res), "mensaje": msg, "codigos": res}), {"existe": bool(res), "repuestos": res}

    @tool("repuestos_frecuentes", args_schema=CodigoEquipo, response_format="content_and_artifact")
    def repuestos_frecuentes(equipo: str):
        """Los repuestos que más se le cambian a ese modelo de máquina (todos los equipos con la misma denominación)."""
        filas = q.repuestos_frecuentes(cur(), equipo)
        return _json({"repuestos": [{**r, "importe": _mill(r["importe"])} for r in filas]}), {"filas": filas}

    @tool("identificar_repuesto_por_foto", args_schema=Foto, response_format="content_and_artifact")
    def identificar_repuesto_por_foto(nota: str = "", runtime: ToolRuntime[AgentContext] = None):
        """Identifica la pieza de la foto que mandó el usuario y busca su código SAP. Úsala solo si hay una foto."""
        ctx = (runtime.context if runtime else None) or AgentContext()
        imagenes = [a for a in ctx.adjuntos if IMAGEN.search(a)]
        if not imagenes:
            return _json({"error": "El mensaje no trae una foto. Pídele al usuario que la envíe."}), {
                "identificacion": None
            }
        if deps.vision_llm is None:
            return _json({"error": "La visión no está disponible en este despliegue."}), {"identificacion": None}
        ident = vision.identificar(deps.vision_llm, imagenes[-1], nota)
        candidatos: list[dict] = []
        for ref in ident.referencias_visibles[:3]:
            candidatos += [r.model_dump() | {"por": f"referencia {ref}"} for r in q.verificar_codigo(cur(), ref)]
        if not candidatos:
            candidatos = [
                r.model_dump() | {"por": "descripción"} for r in q.buscar_repuesto(cur(), ident.terminos_busqueda, 5)
            ]
        contenido = {
            "identificacion": ident.model_dump(),
            "candidatos_sap": candidatos[:5],
            "nota": "La identificación visual es una hipótesis: pide confirmar la referencia antes de pedir el repuesto.",
        }
        return _json(contenido), {"identificacion": ident.model_dump(), "repuestos": candidatos[:5]}

    # ---------------------------------------------------------------- Inteligencia
    @tool("detectar_anomalias", args_schema=Anomalias, response_format="content_and_artifact")
    def detectar_anomalias(dias: int = 30, familia: str | None = None):
        """Alertas: consumos recientes muy por encima del ritmo del año anterior para ese equipo y material (posibles
        fallas repetitivas, fugas, mal uso o errores de cargue). Ordenadas por importe."""
        alertas = [a.model_dump() for a in q.detectar_anomalias(cur(), dias, familia)]
        contenido = [{**a, "importe_reciente": _mill(a["importe_reciente"])} for a in alertas]
        return _json({"fecha_corte": q.fecha_corte(cur()), "alertas": contenido}), {"alertas": alertas}

    @tool("predecir_reposicion", args_schema=Prediccion, response_format="content_and_artifact")
    def predecir_reposicion(equipo: str, horizonte_dias: int = 30):
        """Qué repuestos le van a tocar pronto a un equipo según su propio ritmo histórico de cambio (kit sugerido con
        fecha estimada, costo y confianza)."""
        res = [r.model_dump() for r in q.predecir_reposicion(cur(), equipo, horizonte_dias)]
        total = sum(r["costo_estimado"] for r in res)
        contenido = {
            "fecha_corte": q.fecha_corte(cur()),
            "sugeridos": [{**r, "costo_estimado": _mill(r["costo_estimado"])} for r in res[:15]],
            "costo_total_estimado": _mill(total),
        }
        return _json(contenido), {"sugeridos": res, "costo_total": total}

    @tool("generar_informe_pdf", args_schema=Informe, response_format="content_and_artifact")
    def generar_informe_pdf(equipo: str | None = None, familia: str | None = None, meses: int = 6):
        """Genera un informe PDF (resumen, gráfica, top de equipos o materiales, alertas o kit sugerido) y lo envía."""
        c = cur()
        corte = q.fecha_corte(c)
        serie = q.serie_gasto(c, equipo, familia, meses)
        total = sum(p.valor for p in serie)
        if equipo:
            ficha = q.ficha_equipo(c, equipo)
            sujeto = f"{ficha.equipo.equipo} · {ficha.equipo.denominacion}" if ficha else equipo
            tabla = (
                "Materiales de mayor gasto (12 meses)",
                ["Material", "Cantidad", "Importe"],
                [
                    [t["texto_material"], f"{t['cantidad']:g} {t['unidad'] or ''}", _mill(t["importe"])]
                    for t in (ficha.top_materiales if ficha else [])
                ],
            )
            preds = q.predecir_reposicion(c, equipo, 30)
            extra = (
                "Reposición sugerida (próximos 30 días)",
                ["Material", "Próxima", "Costo"],
                [[p.texto_material, f"{p.proxima_estimada:%d/%m/%Y}", _mill(p.costo_estimado)] for p in preds[:10]],
            )
        else:
            sujeto = familia or "Toda la flota"
            rank = q.ranking_gasto(c, familia, meses * 30, 10)
            tabla = (
                "Equipos con mayor gasto",
                ["Equipo", "Denominación", "Gasto"],
                [[r["equipo"], r["denominacion"], _mill(r["gasto"])] for r in rank],
            )
            alertas = q.detectar_anomalias(c, 30, familia)
            extra = (
                "Alertas de consumo (30 días)",
                ["Equipo / material", "Detalle", "Importe"],
                [[f"{a.equipo} · {a.texto_material}", a.explicacion, _mill(a.importe_reciente)] for a in alertas],
            )
        img = graficas.grafica_barras_mensual(
            [(p.periodo, p.valor) for p in serie],
            f"Gasto mensual · {sujeto}",
            f"Últimos {meses} meses · total {_mill(total)} COP",
            s.media_dir / "graficas",
            ultimo_parcial=corte.day < 28,
        )
        resumen = [
            f"Gasto de los últimos {meses} meses: {_mill(total)} COP (datos SAP al {corte:%d/%m/%Y}).",
            f"Promedio mensual: {_mill(total / max(len(serie), 1))} COP.",
        ]
        if serie:
            pico = max(serie, key=lambda p: p.valor)
            resumen.append(f"Mes de mayor gasto: {pico.periodo} ({_mill(pico.valor)} COP).")
        pdf = graficas.informe_pdf(
            f"Informe de mantenimiento · {sujeto}", resumen, [tabla, extra], [img], s.media_dir / "informes", corte
        )
        return _json({"resumen": resumen, "nota": "El PDF ya se envió al usuario."}), {
            "media": [media(pdf, "documento", f"Informe · {sujeto}")]
        }

    # ---------------------------------------------------------------- Conocimiento
    @tool("buscar_manual", args_schema=BuscarManual, response_format="content_and_artifact")
    def buscar_manual(consulta: str, modelo: str | None = None, tipo: str | None = None):
        """Busca en los manuales técnicos (tractores Case IH Puma, John Deere 6165J y GAME 77ATX; alzadoras John
        Deere 2254; tractomulas Kenworth T800/T370: manual eléctrico, diagramas y caja de fusibles) y ENVÍA LA FOTO
        de la página con lo buscado resaltado. Úsala para procedimientos, especificaciones, fusibles, diagramas,
        códigos de error y despieces."""
        if deps.manuales is None:
            return _json({"error": "Los manuales no están cargados en este despliegue."}), {"paginas": []}
        res = deps.manuales.buscar(consulta, modelo, tipo, k=3)
        if not res:
            return _json({"resultados": [], "nota": "No encontré esa información en los manuales."}), {"paginas": []}
        mejor = res[0]
        imgs = []
        for pagina in [p for p in (mejor.pagina_figura, mejor.pagina) if p]:
            try:
                ruta = renderizar_pagina(
                    s.manuales_dir,
                    mejor.manual_id,
                    pagina,
                    s.media_dir / "manuales",
                    resaltar=consulta if pagina == mejor.pagina else None,
                )
                imgs.append(media(ruta, "imagen", f"📘 {mejor.titulo} · pág. {pagina}"))
            except Exception:  # noqa: BLE001 — sin el PDF en disco se responde solo con el texto
                pass
        resultados = [{"n": i + 1, **r.model_dump()} for i, r in enumerate(res)]
        contenido = {
            "resultados": resultados,
            "imagenes_enviadas": [m["pie"] for m in imgs],
            "instruccion": "Responde con lo que dice la página [1] en español (traduce si está en inglés o portugués) "
            "y cita «📘 manual, pág. N». La foto ya va adjunta.",
        }
        return _json(contenido), {"paginas": resultados, "media": imgs}

    # ---------------------------------------------------------------- Acción con confirmación humana
    @tool("registrar_novedad", args_schema=RegistrarNovedad, response_format="content_and_artifact")
    def registrar_novedad(
        equipo: str,
        descripcion: str,
        sistema: str = "",
        prioridad: str = "media",
        runtime: ToolRuntime[AgentContext] = None,
    ):
        """Registra una novedad de campo (falla, daño, fuga) de un equipo. Pide confirmación al usuario antes de
        guardar y solo la pueden usar supervisores y técnicos del taller."""
        ctx = (runtime.context if runtime else None) or AgentContext()
        if ctx.rol not in ROLES_TALLER:
            return _json(
                {"error": "Solo el personal del taller puede registrar novedades. Puedo informarte, pero no escribir."}
            ), {"registrada": False, "motivo": "rol"}
        eq = q.buscar_equipo(cur(), equipo, limite=1)
        if not eq:
            return _json({"error": f"No existe el equipo {equipo}."}), {"registrada": False, "motivo": "equipo"}
        n = novedades.Novedad(
            equipo=eq[0].equipo,
            denominacion=eq[0].denominacion,
            sistema=sistema,
            descripcion=descripcion,
            prioridad=prioridad,
        )
        respuesta = interrupt(
            {
                "tipo": "confirmar_novedad",
                "pregunta": (
                    f"¿Registro esta novedad?\n• Equipo: {n.equipo} · {n.denominacion}\n• Sistema: {n.sistema or '—'}\n"
                    f"• Prioridad: {n.prioridad}\n• Descripción: {n.descripcion}\n"
                    "Responde *SÍ* para confirmar o *NO* para cancelar."
                ),
                "novedad": n.model_dump(),
            }
        )
        if not SI.match(str(respuesta)):
            return _json({"registrada": False, "mensaje": "Cancelado por el usuario: no se guardó nada."}), {
                "registrada": False,
                "motivo": "cancelada",
            }
        guardada = novedades.registrar(s.novedades_db, n, ctx.user_id, ctx.canal, s.zona_horaria)
        return _json({"registrada": True, "id": guardada["id"], "mensaje": f"Novedad #{guardada['id']} registrada."}), {
            "registrada": True,
            "novedad": guardada,
        }

    return [
        buscar_equipo,
        ficha_equipo,
        flota_por_familia,
        ranking_gasto_equipos,
        historial_consumo,
        detalle_orden,
        donde_se_usa_material,
        grafica_gasto,
        buscar_repuesto,
        verificar_codigo_sap,
        repuestos_frecuentes,
        identificar_repuesto_por_foto,
        detectar_anomalias,
        predecir_reposicion,
        generar_informe_pdf,
        buscar_manual,
        registrar_novedad,
    ]

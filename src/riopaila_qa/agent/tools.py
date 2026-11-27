"""Herramientas del agente (function calling con ``@tool`` y esquemas Pydantic).

| Herramienta              | Fuente                     | Determinista | Ruta(s)            |
|--------------------------|----------------------------|--------------|--------------------|
| ``buscar_documentos``    | Qdrant + BM25 (híbrida)    | sí (top-k)   | rag, mixto         |
| ``consultar_indicadores``| CSV de indicadores         | sí           | datos, mixto       |
| ``comparar_cifras``      | aritmética en Python       | sí           | datos, mixto       |
| ``recordar_dato_usuario``| Store (largo plazo)        | sí           | memoria, rag       |
| ``infografia_riopaila``  | CSV de indicadores → PNG   | sí           | datos, mixto       |
| ``grafica_indicador``    | CSV de indicadores → PNG   | sí           | datos, mixto       |

Cada herramienta devuelve ``(contenido, artefacto)``: el contenido va al LLM y el
artefacto (fragmentos, filas, hallazgos del blindaje) va a la app y a la traza.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field

from riopaila_qa.agent import memory, visual
from riopaila_qa.rag.retriever import HybridRetriever
from riopaila_qa.rag.shield import ShieldMode, render_documents
from riopaila_qa.structured import (
    ComparacionCifras,
    ConsultaIndicadores,
    Indicador,
    comparar,
    consultar,
)


@dataclass
class AgentContext:
    """Contexto de ejecución inyectado en cada turno (no lo ve el LLM)."""

    user_id: str = "invitado"
    thread_id: str = ""
    rol: str = "invitado"  # supervisor | tecnico | invitado (Módulo 3: solo el taller escribe novedades)
    canal: str = "web"  # web | whatsapp
    adjuntos: list[str] = field(default_factory=list)  # rutas o data-URL de fotos que mandó el usuario


class BuscarDocumentos(BaseModel):
    """Esquema de ``buscar_documentos``."""

    consulta: str = Field(description="Pregunta o palabras clave a buscar en los documentos de Riopaila Castilla.")
    seccion: str | None = Field(
        None,
        description=(
            "Filtro opcional por sección: institucional, identidad, negocios-y-productos, sostenibilidad, "
            "gobierno-corporativo, procesos-productivos, contacto, noticias."
        ),
    )
    tipo: str | None = Field(None, description="Filtro opcional: 'pagina' o 'noticia'.")
    anio: int | None = Field(None, description="Filtro opcional por año de publicación de la noticia.")


class RecordarDato(BaseModel):
    """Esquema de ``recordar_dato_usuario``."""

    clave: str = Field(description="Qué dato es, en una palabra: nombre, empresa, cargo, ciudad, preferencia…")
    valor: str = Field(description="El valor exacto que dijo el usuario, p. ej. 'Ana' o 'Carvajal'.")


class InfografiaRiopaila(BaseModel):
    """Esquema de ``infografia_riopaila``."""

    tema: Literal["panorama", "energia", "etanol", "social"] = Field(
        "panorama",
        description=(
            "panorama = la empresa en cifras (ingresos, utilidades, mercado, países, trabajadores, inversión); "
            "energia = cogeneración con bagazo; etanol = alcohol carburante; social = inversión social y empleo."
        ),
    )


class GraficaIndicador(BaseModel):
    """Esquema de ``grafica_indicador``."""

    indicador: str = Field(
        description=(
            "Indicador del catálogo, p. ej. ingresos_operacionales, utilidad_neta, produccion_alcohol_carburante, "
            "vehiculos_oxigenados, ventas_energia, inversion_social, pagos_a_proveedores."
        )
    )


def _rows_payload(rows: list[Indicador]) -> list[dict]:
    return [r.model_dump() | {"valor_legible": r.valor_legible} for r in rows]


def build_tools(
    retriever: HybridRetriever | None,
    indicadores: tuple[Indicador, ...],
    shield_mode: ShieldMode = "marcar",
    media_dir: Path | None = None,
    media_base_url: str = "",
):
    """Crea las herramientas con sus dependencias (inyección explícita, fácil de probar)."""

    def _media(ruta: Path, pie: str) -> dict:
        try:
            rel = ruta.relative_to(media_dir).as_posix() if media_dir else ruta.name
        except ValueError:
            rel = ruta.name
        url = f"{media_base_url.rstrip('/')}/media/{rel}" if media_base_url else f"/media/{rel}"
        return {"tipo": "imagen", "ruta": str(ruta), "url": url, "pie": pie}

    def _cifras(filas: list[Indicador]) -> list[dict]:
        return [
            {
                "indicador": r.indicador,
                "cifra": visual.cifra_corta(r),
                "periodo": visual.periodo_legible(r),
                "descripcion": r.descripcion,
                "fuente_url": r.fuente_url,
            }
            for r in filas
        ]

    @tool("buscar_documentos", args_schema=BuscarDocumentos, response_format="content_and_artifact")
    def buscar_documentos(consulta: str, seccion: str | None = None, tipo: str | None = None, anio: int | None = None):
        """Busca en los documentos públicos de Riopaila Castilla (base vectorial Qdrant + BM25).

        Úsala cuando la respuesta esté en textos de la empresa: historia, productos, sostenibilidad,
        gobierno corporativo, noticias o metas mencionadas en un documento. Devuelve fragmentos
        numerados [n] con su título y URL para citar.
        """
        if retriever is None:
            return "El índice vectorial no está disponible: ejecuta scripts/build_index.py.", {
                "hits": [],
                "error": "sin_indice",
            }
        res = retriever.search(consulta, seccion=seccion or None, tipo=tipo or None, anio=anio or None)
        if not res.hits:
            return "No se encontraron fragmentos relevantes para esa consulta.", {"hits": [], "query": consulta}
        xml, findings = render_documents(res.hits, shield_mode)
        artifact = {
            "query": consulta,
            "filters": res.filters,
            "latency_ms": round(res.latency_ms, 1),
            "hits": [
                {
                    "n": h.rank,
                    "chunk_id": h.chunk.chunk_id,
                    "titulo": h.chunk.titulo,
                    "url": h.chunk.url,
                    "seccion": h.chunk.seccion,
                    "origen": h.chunk.origen,
                    "score": round(h.score, 5),
                    "dense_rank": h.dense_rank,
                    "lexical_rank": h.lexical_rank,
                    "fragmento": h.chunk.texto[:700],
                }
                for h in res.hits
            ],
            "shield": [f.__dict__ for f in findings],
        }
        return xml, artifact

    @tool("consultar_indicadores", args_schema=ConsultaIndicadores, response_format="content_and_artifact")
    def consultar_indicadores(
        indicador: str | None = None, anio: int | None = None, periodo: str | None = None, categoria: str | None = None
    ):
        """Consulta EXACTA del CSV de indicadores públicos de Riopaila Castilla (ingresos, utilidad,
        ventas de energía, alcohol carburante, inversión social, trabajadores…) por año y periodo
        (anual, S1/S2, T1–T4). Úsala para cualquier cifra: nunca estimes ni calcules un número tú mismo.
        """
        q = ConsultaIndicadores(indicador=indicador, anio=anio, periodo=periodo, categoria=categoria)
        res = consultar(indicadores, q)
        payload = {
            "filtros": res.filtros,
            "total": res.total,
            "filas": _rows_payload(res.filas),
            "nota": res.nota,
        }
        content = json.dumps(
            {k: v for k, v in payload.items() if k != "filas"}
            | {
                "filas": [
                    {
                        k: r[k]
                        for k in (
                            "id",
                            "indicador",
                            "anio",
                            "periodo",
                            "valor",
                            "unidad",
                            "calificador",
                            "valor_legible",
                            "descripcion",
                            "fuente_url",
                        )
                    }
                    for r in payload["filas"]
                ]
            },
            ensure_ascii=False,
        )
        return content, payload

    @tool("comparar_cifras", args_schema=ComparacionCifras, response_format="content_and_artifact")
    def comparar_cifras(valor_a: float, etiqueta_a: str, valor_b: float, etiqueta_b: str, unidad: str):
        """Compara dos cifras en la MISMA unidad y devuelve diferencia y porcentajes calculados en Python.
        Úsala siempre que haya que restar, dividir o dar un porcentaje (p. ej. lo logrado frente a una meta).
        """
        res = comparar(
            ComparacionCifras(
                valor_a=valor_a, etiqueta_a=etiqueta_a, valor_b=valor_b, etiqueta_b=etiqueta_b, unidad=unidad
            )
        )
        return res.model_dump_json(), res.model_dump()

    @tool("recordar_dato_usuario", args_schema=RecordarDato, response_format="content_and_artifact")
    def recordar_dato_usuario(clave: str, valor: str, runtime: ToolRuntime[AgentContext]):
        """Guarda en la memoria de largo plazo un dato que el usuario contó de sí mismo (nombre, empresa,
        cargo, ciudad, preferencias). Ese dato estará disponible en todas sus conversaciones futuras.
        """
        ctx = runtime.context or AgentContext()
        if runtime.store is None:
            return "No hay Store configurado: no se pudo guardar.", {"guardado": False}
        item = memory.save_fact(runtime.store, ctx.user_id, clave, valor, ctx.thread_id or None)
        return f"Guardado en el perfil de {ctx.user_id}: {item['clave']} = {item['valor']}", {"guardado": True, **item}

    @tool("infografia_riopaila", args_schema=InfografiaRiopaila, response_format="content_and_artifact")
    def infografia_riopaila(tema: str = "panorama"):
        """Envía una INFOGRAFÍA (imagen) "Riopaila Castilla en cifras" con las cifras públicas más recientes del
        tema, cada una con su año y su fuente. Úsala cuando pregunten qué es Riopaila, cómo le va, sus cifras,
        su energía, su etanol o su aporte social, y para dar la bienvenida a un visitante que quiere conocerla."""
        if media_dir is None:
            return json.dumps({"error": "Este despliegue no genera imágenes."}), {"cifras": []}
        ruta, filas = visual.infografia(indicadores, tema, Path(media_dir) / "graficas")
        cifras = _cifras(filas)
        contenido = {
            "tema": tema,
            "cifras": cifras,
            "nota": "La infografía ya se envió. Comenta 2 o 3 cifras en una frase cada una y cita la fuente.",
        }
        pie = f"📊 {visual.TEMAS.get(tema, visual.TEMAS['panorama'])[0]}"
        return json.dumps(contenido, ensure_ascii=False), {"cifras": cifras, "media": [_media(ruta, pie)]}

    @tool("grafica_indicador", args_schema=GraficaIndicador, response_format="content_and_artifact")
    def grafica_indicador(indicador: str):
        """Envía una GRÁFICA (imagen) de un indicador público de Riopaila Castilla por año (p. ej. cómo han
        evolucionado los ingresos, la utilidad, el etanol o la energía), con las cifras tal como las publicó."""
        if media_dir is None:
            return json.dumps({"error": "Este despliegue no genera imágenes."}), {"serie": []}
        nombre = consultar(indicadores, ConsultaIndicadores(indicador=indicador)).filas
        clave = nombre[0].indicador if nombre else indicador
        ruta, serie = visual.serie_indicador(indicadores, clave, Path(media_dir) / "graficas")
        if ruta is None:
            disponibles = sorted({r.indicador for r in indicadores})
            return json.dumps({"error": f"No hay datos de {indicador}.", "disponibles": disponibles}), {"serie": []}
        cifras = _cifras(serie)
        contenido = {"indicador": clave, "serie": cifras, "nota": "La gráfica ya se envió; comenta la tendencia."}
        pie = f"📈 {clave.replace('_', ' ').capitalize()}"
        return json.dumps(contenido, ensure_ascii=False), {"serie": cifras, "media": [_media(ruta, pie)]}

    return [
        buscar_documentos,
        consultar_indicadores,
        comparar_cifras,
        recordar_dato_usuario,
        infografia_riopaila,
        grafica_indicador,
    ]

"""Router del agente: decide **antes** de gastar una búsqueda (criterio 2.3).

Inspirado en el patrón *gatekeeper* System One de la Clase 9 (Jev): decisiones
tipadas con probabilidad, baratas, antes de encender el LLM caro.

1. **Noul por reglas** (milisegundos, sin LLM): ¿es un saludo o algo trivial?,
   ¿el usuario está contando un dato propio?, ¿pregunta por sí mismo?
2. **Choice por reglas**: puntúa señales numéricas (CSV) y documentales (RAG).
3. **Choice con LLM** (solo si la confianza de las reglas es baja y
   ``ROUTER_MODE=hibrido``): salida estructurada Pydantic con la ruta y su confianza.
4. **Confianza baja** (< 0.5) → ruta ``rag`` en modo cautela: el agente responde
   solo con evidencia o se abstiene.

Rutas: ``directo`` (sin herramientas), ``memoria`` (guardar perfil), ``rag``
(documentos en Qdrant), ``datos`` (CSV con @tool) y ``mixto`` (ambas fuentes).

Módulo 3 (Taller Castilla) suma tres rutas con sus herramientas:
``taller`` (flota, consumos SAP, repuestos, alertas, predicción, gráficas e informes),
``manual`` (manuales técnicos con la foto de la página, identificación por foto) y
``novedad`` (registrar una falla de campo, con confirmación humana).
"""

from __future__ import annotations

import re
import time
import unicodedata
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

Ruta = Literal["directo", "memoria", "rag", "datos", "mixto", "taller", "manual", "novedad"]
RUTAS: tuple[str, ...] = ("directo", "memoria", "rag", "datos", "mixto", "taller", "manual", "novedad")
LOW_CONFIDENCE = 0.5
LLM_THRESHOLD = 0.7

TOOLS_BY_ROUTE: dict[str, tuple[str, ...]] = {
    "directo": (),
    "memoria": ("recordar_dato_usuario",),
    "rag": ("buscar_documentos", "recordar_dato_usuario"),
    "datos": ("consultar_indicadores", "comparar_cifras", "infografia_riopaila", "grafica_indicador"),
    "mixto": (
        "buscar_documentos",
        "consultar_indicadores",
        "comparar_cifras",
        "infografia_riopaila",
        "grafica_indicador",
    ),
    "taller": (
        "buscar_equipo",
        "ficha_equipo",
        "flota_por_familia",
        "ranking_gasto_equipos",
        "historial_consumo",
        "detalle_orden",
        "donde_se_usa_material",
        "grafica_gasto",
        "buscar_repuesto",
        "verificar_codigo_sap",
        "repuestos_frecuentes",
        "detectar_anomalias",
        "predecir_reposicion",
        "generar_informe_pdf",
        "comparar_cifras",
    ),
    "manual": (
        "buscar_manual",
        "buscar_equipo",
        "buscar_repuesto",
        "verificar_codigo_sap",
        "identificar_repuesto_por_foto",
    ),
    "novedad": ("registrar_novedad", "buscar_equipo"),
}
RUTAS_TALLER = ("taller", "manual", "novedad")


class RouteDecision(BaseModel):
    """Decisión tipada del router (lo que ve la app y la traza)."""

    ruta: Ruta
    confianza: float = Field(ge=0, le=1)
    razon: str
    metodo: Literal["reglas", "llm", "reglas+llm"] = "reglas"
    cautela: bool = False
    senales: dict[str, float] = Field(default_factory=dict)
    latencia_ms: float = 0.0

    @property
    def herramientas(self) -> tuple[str, ...]:
        return TOOLS_BY_ROUTE[self.ruta]


class LLMRouteChoice(BaseModel):
    """Esquema que el LLM debe llenar cuando las reglas dudan."""

    ruta: Ruta = Field(description="directo | memoria | rag | datos | mixto | taller | manual | novedad")
    confianza: float = Field(ge=0, le=1, description="Probabilidad de que la ruta sea la correcta")
    razon: str = Field(description="Justificación en una frase")


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


GREETING = re.compile(
    r"^\W*(hola|buen[oa]s?( dias| tardes| noches)?|saludos|hey|que tal|como estas|gracias|muchas gracias|"
    r"ok|vale|listo|perfecto|chao|adios|hasta luego|bien y tu)\W*$"
)
META = re.compile(r"\b(quien eres|que eres|que puedes hacer|como funcionas|en que me ayudas|ayuda)\b")
DISCLOSURE = re.compile(
    r"\b(me llamo|mi nombre es|trabajo (en|como|para)|soy (el|la|un|una)?\s*\w+|mi cargo es|"
    r"prefiero|recuerda que|mi (empresa|area|correo|ciudad) es|vivo en)\b"
)
ABOUT_ME = re.compile(
    r"\b(como me llamo|cual es mi nombre|donde trabajo|en que trabajo|que sabes de mi|quien soy|"
    r"cual es mi (cargo|empresa|area)|que (te dije|recuerdas))\b"
)
NUMERIC = re.compile(
    r"\b(cuant[oa]s?|cifra|cifras|ventas?|vendi\w*|ingresos?|utilidad\w*|millones|billones|litros|"
    r"trimestre|semestre|porcentaje|crecimiento|crecio|toneladas|vehiculos|trabajadores|inversion|"
    r"participacion|dato exacto|total|sum[ae]|promedio|20[12]\d)\b|%|\bt[1-4]\b|\bs[12]\b"
)
DOCUMENTAL = re.compile(
    r"\b(que dice|segun|documento|corpus|noticia|politica|meta|metas|objetivo|esperaba|proyeccion|"
    r"compromiso|programa|proyecto|historia|fundad\w*|que es|que hace|como|por que|donde|explica|"
    r"describe|sostenib\w*|certifica\w*|comunidad\w*|cana|azucar|energia|alcohol|organic\w*)\b"
)
# --- Módulo 3 · taller -----------------------------------------------------------------------
FOTO = re.compile(r"\[foto adjunta\]")
TALLER = re.compile(
    r"\b(equipos?|flota|tractor\w*|cosechadora\w*|alzadora\w*|cargadora\w*|mulas?|tractomulas?|vagon\w*|"
    r"camion\w*|volqueta\w*|puma|case|john deere|kenworth|game|ch570|a8800|2254|t800|t370|"
    r"repuestos?|materiales?|codigo sap|sap|orden(es)?|ot|consum\w*|gast\w*|costos?|cuest\w*|"
    r"filtros?|aceites?|llantas?|cuchillas?|rodamientos?|mangueras?|baterias?|"
    r"anomal\w*|alerta\w*|raro|disparad\w*|predic\w*|reposicion|proxim\w* cambio|que le toca|kit|"
    r"grafica\w*|tendencia|informe|reporte|pdf|ranking|top|mas gast\w*|historial|hoja de vida|"
    r"taller|mantenimiento|preventivo|correctivo)\b"
)
MANUAL = re.compile(
    r"\b(manual\w*|diagrama\w*|plano\w*|fusibles?|reles?|torque|apriete|especificacion\w*|procedimiento\w*|"
    r"como (se )?(cambi|ajust|calibr|engras|purg|desmont|mont|revis|reviso|cambio|cambia)\w*|paso a paso|"
    r"codigo de (error|falla)|error \d+|falla \d+|despiece|numero de parte|referencia|capacidad de aceite|"
    r"intervalo\w*|cada cuant\w*|que pieza|que repuesto es|identifica\w*|esquema)\b"
)
NOVEDAD = re.compile(
    r"\b(registr\w*|report\w*|reportar|anota\w*|novedad\w*)\b.*\b(falla|fuga|dano|danad\w*|rot[oa]|"
    r"novedad|varad\w*|parad\w*|no prende|no arranca|recalent\w*|ruido)|"
    r"\b(se (vara|varo|dano|rompio|recalento)|esta (varad|botando|parad)\w*|bota (aceite|agua))"
)

# Vitrina de la compañía (perfil visitante): infografía y series de las cifras públicas del M1/M2.
VITRINA = re.compile(
    r"\b(en cifras|infografi\w*|como le (va|fue)|panorama|conocer (la empresa|riopaila)|quienes son|"
    r"que es riopaila|cifras (de|clave)|resumen de (la empresa|riopaila))\b|"
    r"\bgrafica\w* (de|del|de los|de la) (ingresos|utilidad\w*|ventas|produccion|alcohol|etanol|energia|"
    r"inversion|vehiculos|pagos)"
)
RIOPAILA_CORP = re.compile(r"\b(riopaila|accionistas?|sostenib\w*|ingresos|utilidad|ebitda|alcohol carburante)\b")
COMPARE = re.compile(r"\b(compar\w*|frente a|versus|vs|contra|cumpli\w*|alcanz\w*|diferencia|respecto)\b")


def route_by_rules(message: str) -> RouteDecision:
    """Decisión por reglas con una confianza heurística (rápida y explicable)."""
    t0 = time.perf_counter()
    m = _plain(message).strip()
    words = len(m.split())
    s = {
        "saludo": 1.0 if GREETING.match(m) else 0.0,
        "meta": 1.0 if META.search(m) and words <= 8 else 0.0,
        "dato_propio": 1.0 if DISCLOSURE.search(m) else 0.0,
        "sobre_mi": 1.0 if ABOUT_ME.search(m) else 0.0,
        "numerico": min(1.0, 0.35 * len(NUMERIC.findall(m))),
        "documental": min(1.0, 0.3 * len(DOCUMENTAL.findall(m))),
        "comparar": 1.0 if COMPARE.search(m) else 0.0,
        "foto": 1.0 if FOTO.search(m) else 0.0,
        "taller": min(1.0, 0.35 * len(TALLER.findall(m))),
        "manual": min(1.0, 0.45 * len(MANUAL.findall(m))),
        "novedad": 1.0 if NOVEDAD.search(m) else 0.0,
    }

    def done(ruta: str, conf: float, razon: str) -> RouteDecision:
        return RouteDecision(
            ruta=ruta,
            confianza=round(conf, 2),
            razon=razon,
            senales=s,
            latencia_ms=round((time.perf_counter() - t0) * 1000, 2),
        )

    if s["foto"]:
        return done("manual", 0.9, "Mandó una foto: se identifica la pieza y se busca su código SAP.")
    if s["novedad"]:
        return done("novedad", 0.85, "Reporta una falla de campo: se registra la novedad con confirmación humana.")
    if VITRINA.search(m):
        return done("datos", 0.9, "Quiere conocer la compañía: infografía o gráfica de cifras públicas con su fuente.")
    if s["manual"] >= 0.45 and s["manual"] >= s["taller"] - 0.35:
        return done(
            "manual",
            0.8 if s["taller"] else 0.75,
            "Pregunta técnica de procedimiento o especificación: se busca en los manuales (con la foto).",
        )
    if s["taller"] >= 0.35 and not RIOPAILA_CORP.search(m):
        conf = 0.85 if s["taller"] >= 0.7 else 0.7
        return done("taller", conf, "Pregunta del taller: flota, consumos, repuestos o alertas sobre datos SAP.")
    if s["saludo"] or (words <= 3 and not s["numerico"] and not s["documental"] and not s["sobre_mi"]):
        return done("directo", 0.97, "Saludo o mensaje trivial: no hace falta buscar.")
    if s["meta"]:
        return done("directo", 0.9, "Pregunta sobre el asistente: se responde sin buscar.")
    if s["sobre_mi"] and not s["numerico"]:
        return done("directo", 0.9, "Pregunta sobre el propio usuario: se responde con el perfil del Store.")
    if s["dato_propio"] and not s["numerico"] and "?" not in message:
        return done("memoria", 0.9, "El usuario comparte un dato propio: se guarda en la memoria de largo plazo.")
    if s["numerico"] >= 0.35 and s["comparar"] and (s["documental"] or "meta" in m):
        return done("mixto", 0.85, "Pide comparar una cifra con lo que dice un documento: CSV + RAG.")
    if s["numerico"] >= 0.7 and s["documental"] < 0.6:
        return done("datos", 0.85, "Pregunta numérica sobre indicadores: herramienta determinista sobre el CSV.")
    if s["numerico"] >= 0.35 and s["documental"] < 0.3:
        return done("datos", 0.65, "Parece numérica, pero con pocas señales.")
    if s["documental"] >= 0.3:
        conf = 0.75 if s["numerico"] < 0.35 else 0.6
        return done("rag", conf, "Pregunta sobre la empresa: se busca en los documentos (Qdrant).")
    return done("rag", 0.45, "Sin señales claras: se busca con cautela.")


ROUTER_PROMPT = """Eres el router de un asistente de Riopaila Castilla. Elige UNA ruta para el último mensaje:
- directo: saludos, agradecimientos, preguntas sobre el asistente o sobre el propio usuario (su nombre, dónde trabaja).
- memoria: el usuario cuenta un dato propio para que lo recordemos (nombre, empresa, cargo, preferencia).
- rag: la respuesta está en los documentos públicos de la empresa (historia, productos, sostenibilidad, noticias).
- datos: piden una cifra exacta de indicadores (ingresos, utilidad, ventas de energía, alcohol, por año/trimestre).
- mixto: piden comparar o combinar una cifra de los indicadores con algo que dice un documento (p. ej. una meta).
- taller: preguntas del Taller Castilla sobre equipos, flota, consumos y gastos en SAP, repuestos, códigos de material,
  alertas de consumo, predicción de reposición, gráficas o informes PDF.
- manual: procedimientos, especificaciones, diagramas, fusibles, códigos de error o despieces de los manuales técnicos,
  o identificar una pieza por foto.
- novedad: el usuario reporta una falla o daño de un equipo para que quede registrado.
Responde solo con el esquema. Mensaje:
<mensaje>{mensaje}</mensaje>"""


def route(message: str, llm: BaseChatModel | None = None, mode: str = "hibrido") -> RouteDecision:
    """Router híbrido: reglas primero; el LLM solo desempata cuando la confianza es baja."""
    rules = route_by_rules(message)
    if mode == "reglas" or llm is None or (mode == "hibrido" and rules.confianza >= LLM_THRESHOLD):
        return _finish(rules)
    t0 = time.perf_counter()
    try:
        choice = llm.with_structured_output(LLMRouteChoice).invoke(ROUTER_PROMPT.format(mensaje=message[:1500]))
        if not isinstance(choice, LLMRouteChoice):
            choice = LLMRouteChoice.model_validate(choice)
    except Exception as exc:  # el router nunca debe tumbar la conversación
        rules.razon += f" (LLM del router no disponible: {type(exc).__name__}; se usan las reglas)"
        return _finish(rules)
    decision = RouteDecision(
        ruta=choice.ruta,
        confianza=round(choice.confianza, 2),
        razon=choice.razon,
        metodo="llm" if mode == "llm" else "reglas+llm",
        senales=rules.senales,
        latencia_ms=round(rules.latencia_ms + (time.perf_counter() - t0) * 1000, 1),
    )
    return _finish(decision)


def _finish(d: RouteDecision) -> RouteDecision:
    if d.confianza < LOW_CONFIDENCE and d.ruta != "directo":
        d.ruta = "rag"
        d.cautela = True
        d.razon += " Confianza baja: se responde con cautela y solo con evidencia."
    return d

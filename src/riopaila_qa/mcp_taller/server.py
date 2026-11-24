"""Servidor MCP ``taller-riopaila``: el puente entre OpenClaw (WhatsApp) y el agente LangGraph.

OpenClaw es la puerta (WhatsApp, voz, allowlist, workspace, DeepSeek); el cerebro del taller es el agente
del repositorio (router + 21 herramientas + memoria + HITL) detrás de FastAPI. Este servidor expone tres
herramientas MCP con esquema tipado y permisos separados:

* ``consultar_asistente_taller`` — consultas de **solo lectura** (el API fuerza el rol invitado).
* ``gestionar_novedad_taller`` — registrar fallas con confirmación humana. En ``openclaw.json`` solo los
  números del taller la tienen habilitada (``tools.toolsBySender``), y el API vuelve a validar el rol.
* ``parte_diario_taller`` — resumen de alertas y gasto (lo usa la tarea programada de las 6 a.m.).

Cada número de WhatsApp tiene su propio hilo persistente (``wa-<número>``): el agente recuerda la conversación
aunque se reinicie el servidor. Las imágenes y PDF vuelven como rutas locales para adjuntarlas con ``MEDIA:``.

Ejecutar (stdio, lo lanza OpenClaw)::

    uv run --directory /opt/riopaila python -m riopaila_qa.mcp_taller
"""

from __future__ import annotations

import os
import re
from typing import Annotated

import httpx
from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

API_URL = os.getenv("TALLER_API_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = float(os.getenv("TALLER_API_TIMEOUT", "120"))

INSTRUCCIONES = (
    "Herramientas del Taller Castilla (Riopaila Castilla). Para cualquier pregunta de mantenimiento, equipos, "
    "repuestos, códigos SAP, consumos, gastos, manuales, diagramas, fusibles o alertas usa "
    "consultar_asistente_taller con el mensaje del usuario tal cual y su número. Para reportar una falla usa "
    "gestionar_novedad_taller. Copia la respuesta y agrega al final una línea 'MEDIA:<ruta>' por cada adjunto."
)

servidor = MCPServer(name="taller-riopaila", title="Asistente del Taller Castilla", instructions=INSTRUCCIONES)


class RespuestaTaller(BaseModel):
    """Lo que el agente del taller respondió, listo para reenviar por WhatsApp."""

    respuesta: str
    adjuntos: list[str] = Field(default_factory=list, description="Rutas locales de imágenes o PDF a adjuntar")
    ruta: str | None = Field(None, description="Ruta del router: taller, manual, novedad, rag, datos, directo…")
    herramientas: list[str] = Field(default_factory=list, description="Herramientas que ejecutó el agente")
    pendiente_confirmacion: bool = Field(False, description="True si el agente espera un SÍ/NO del usuario")
    como_enviar: str = ""


def _telefono(valor: str) -> str:
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) < 7:
        raise ValueError("Número de WhatsApp inválido: usa el formato E.164, p. ej. +573001112233")
    return digitos


def _chat(
    mensaje: str, telefono: str, adjuntos: list[str] | None, solo_lectura: bool, cliente: httpx.Client | None = None
) -> RespuestaTaller:
    try:
        tel = _telefono(telefono)
    except ValueError:
        # Si el gateway no entregó el número, se responde igual pero en solo lectura y en un hilo aparte.
        tel, solo_lectura = "desconocido", True
    cuerpo = {
        "mensaje": mensaje[:4000],
        "thread_id": f"wa-{tel}",
        "user_id": tel,
        "canal": "whatsapp",
        "adjuntos": [a for a in (adjuntos or []) if a][:4],
        "solo_lectura": solo_lectura,
    }
    cli = cliente or httpx.Client(timeout=TIMEOUT)
    try:
        r = cli.post(f"{API_URL}/api/chat", json=cuerpo)
        r.raise_for_status()
        datos = r.json()
    finally:
        if cliente is None:
            cli.close()
    rutas = [m["ruta"] for m in datos.get("media") or [] if m.get("ruta")]
    texto = datos.get("content") or datos.get("error") or "No obtuve respuesta del agente del taller."
    return RespuestaTaller(
        respuesta=texto,
        adjuntos=rutas,
        ruta=(datos.get("ruta") or {}).get("ruta"),
        herramientas=[h.get("name", "") for h in datos.get("herramientas") or []],
        pendiente_confirmacion=bool(datos.get("pendiente")),
        como_enviar=(
            "Responde con el texto y agrega al final, en líneas separadas y sin formato: "
            + " ".join(f"MEDIA:{p}" for p in rutas)
            if rutas
            else "Responde con el texto."
        ),
    )


@servidor.tool(name="consultar_asistente_taller")
def consultar_asistente_taller(
    mensaje: Annotated[
        str, Field(description="Mensaje del usuario, tal cual lo escribió (o la transcripción del audio).")
    ],
    telefono: Annotated[str, Field(description="Número de WhatsApp del remitente en formato E.164 (+57…).")],
    adjuntos: Annotated[
        list[str] | None, Field(description="Rutas locales de fotos que envió el usuario (si las hay).")
    ] = None,
) -> RespuestaTaller:
    """Pregunta al agente del Taller Castilla (solo lectura): equipos, consumos SAP, repuestos y códigos, alertas,
    predicción de cambios, gráficas, informes PDF, manuales con la foto de la página y documentos de la empresa."""
    return _chat(mensaje, telefono, adjuntos, solo_lectura=True)


@servidor.tool(name="gestionar_novedad_taller")
def gestionar_novedad_taller(
    mensaje: Annotated[str, Field(description="Reporte de la falla o la respuesta SÍ/NO a la confirmación.")],
    telefono: Annotated[str, Field(description="Número de WhatsApp del remitente en formato E.164.")],
) -> RespuestaTaller:
    """Registra una novedad de campo (falla, fuga, daño) de un equipo. El agente pide confirmación (SÍ/NO) antes de
    guardar: reenvía la respuesta del usuario con esta misma herramienta. Solo para personal del taller."""
    return _chat(mensaje, telefono, None, solo_lectura=False)


class ParteDiario(BaseModel):
    texto: str
    adjuntos: list[str] = Field(default_factory=list)


@servidor.tool(name="parte_diario_taller")
def parte_diario_taller(
    dias: Annotated[int, Field(ge=1, le=60, description="Ventana en días para el top de gasto.")] = 7,
) -> ParteDiario:
    """Parte del taller: consumos fuera de lo normal, equipos con mayor gasto y novedades abiertas, con gráfica."""
    with httpx.Client(timeout=TIMEOUT) as cli:
        r = cli.get(f"{API_URL}/api/taller/parte-diario", params={"dias": dias})
        r.raise_for_status()
        datos = r.json()
    return ParteDiario(texto=datos["texto"], adjuntos=datos.get("media", []))


def main() -> None:
    servidor.run("stdio")


if __name__ == "__main__":
    main()

"""Webhook de WhatsApp Cloud API (canal alterno y de contingencia).

El canal en producción es el WhatsApp Web de OpenClaw (gateway → MCP propio → este API). Este webhook deja listo el
camino oficial de Meta (anuncio 008): si se crea la app propia con número registrado y token permanente, basta con
apuntar el webhook a ``/api/webhook/whatsapp`` detrás de HTTPS y poner las variables en el ``.env``:

* ``WHATSAPP_VERIFY_TOKEN``: el *verify token* del handshake ``GET`` (sin él, el handshake se rechaza).
* ``WHATSAPP_APP_SECRET``: si existe, se exige la firma ``X-Hub-Signature-256`` en cada ``POST``.
* ``WHATSAPP_TOKEN`` + ``WHATSAPP_PHONE_NUMBER_ID``: si existen, la respuesta del agente se envía por la Graph API.

Igual que por OpenClaw, el número decide el perfil (``TALLER_ROLES``) y este canal es de solo lectura: las
novedades solo se registran por el gateway, con su lista blanca y la confirmación SÍ/NO.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

log = logging.getLogger("riopaila.webhook")
router = APIRouter(prefix="/api/webhook", tags=["whatsapp"])
GRAPH_URL = "https://graph.facebook.com/v21.0"


def extraer_mensajes(payload: dict) -> list[tuple[str, str]]:
    """``[(wa_id, texto)]`` de un payload de Cloud API (ignora estados de entrega y mensajes sin texto)."""
    salida: list[tuple[str, str]] = []
    for entrada in payload.get("entry", []) or []:
        for cambio in entrada.get("changes", []) or []:
            valor = cambio.get("value", {}) or {}
            for m in valor.get("messages", []) or []:
                texto = (m.get("text") or {}).get("body") or (m.get("button") or {}).get("text") or ""
                if m.get("from") and texto.strip():
                    salida.append((str(m["from"]), texto.strip()))
    return salida


def firma_valida(cuerpo: bytes, firma: str | None, secreto: str) -> bool:
    esperado = "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return bool(firma) and hmac.compare_digest(esperado, firma or "")


def _responder(svc, wa_id: str, texto: str) -> dict:
    res = svc.run_turn(texto, thread_id=f"wa-{wa_id}", user_id=wa_id, canal="whatsapp", solo_lectura=True)
    token, phone_id = os.environ.get("WHATSAPP_TOKEN"), os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    if token and phone_id and res.get("content"):
        try:
            httpx.post(
                f"{GRAPH_URL}/{phone_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={"messaging_product": "whatsapp", "to": wa_id, "type": "text", "text": {"body": res["content"]}},
                timeout=20,
            ).raise_for_status()
        except httpx.HTTPError as exc:  # el webhook ya respondió 200: el error queda en el log
            log.warning("No se pudo responder por Cloud API a %s: %s", wa_id[-4:], exc)
    return res


@router.get("/whatsapp", response_class=PlainTextResponse)
def verificar(
    modo: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    reto: str = Query("", alias="hub.challenge"),
) -> str:
    """Handshake de Meta: devuelve ``hub.challenge`` solo si el verify token coincide."""
    esperado = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
    if not esperado or modo != "subscribe" or not hmac.compare_digest(token, esperado):
        raise HTTPException(403, "verify token inválido")
    return reto


@router.post("/whatsapp")
async def recibir(request: Request, tareas: BackgroundTasks) -> dict:
    """Recibe el evento, responde 200 de inmediato y atiende cada mensaje en segundo plano."""
    cuerpo = await request.body()
    secreto = os.environ.get("WHATSAPP_APP_SECRET")
    if secreto and not firma_valida(cuerpo, request.headers.get("X-Hub-Signature-256"), secreto):
        raise HTTPException(401, "firma inválida")
    try:
        payload = json.loads(cuerpo or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "JSON inválido") from exc
    mensajes = extraer_mensajes(payload if isinstance(payload, dict) else {})
    svc = request.app.state.agent
    for wa_id, texto in mensajes:
        tareas.add_task(_responder, svc, wa_id, texto)
    return {"recibidos": len(mensajes)}

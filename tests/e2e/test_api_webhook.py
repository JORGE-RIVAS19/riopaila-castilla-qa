"""QA de la API y del webhook (anuncio 008): endpoints vivos, flujo del pitch y POST simulado de WhatsApp → 200."""

from __future__ import annotations

import os

from tests.e2e._comun import DESPLEGADO, EVAL_RETRIEVAL

PAYLOAD_WHATSAPP = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "WABA_ID",
            "changes": [
                {
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"display_phone_number": "573136538437", "phone_number_id": "PHONE_ID"},
                        "contacts": [{"profile": {"name": "Invitado"}, "wa_id": "573009998877"}],
                        "messages": [
                            {
                                "from": "573009998877",
                                "id": "wamid.e2e",
                                "timestamp": "1764340000",
                                "type": "text",
                                "text": {"body": "Hola, ¿qué es Riopaila Castilla en cifras?"},
                            }
                        ],
                    },
                }
            ],
        }
    ],
}


def test_salud_y_catalogo_de_herramientas(api):
    r = api.get("/api/health")
    assert r.status_code == 200
    salud = r.json()
    assert salud["estado"] == "ok" and salud["taller"]["activo"]
    assert len(salud["herramientas"]) >= 20
    assert {"infografia_riopaila", "grafica_indicador", "buscar_manual", "registrar_novedad"} <= set(
        salud["herramientas"]
    )
    if DESPLEGADO:  # el despliegue real corre con un LLM en la nube, nunca con Ollama
        assert salud["llm"]["proveedor"] in {"deepseek", "gemini", "openai", "anthropic"}


def test_endpoints_de_la_app(api):
    rutas = ["/api/datos/indicadores", "/api/graph", "/openapi.json", "/api/taller/resumen"]
    # La evaluación del retrieval del M2 se genera en el servidor (scripts/eval_retrieval.py, necesita el índice).
    if DESPLEGADO or EVAL_RETRIEVAL.exists():
        rutas.append("/api/eval/retrieval")
    for ruta in rutas:
        assert api.get(ruta).status_code == 200, ruta
    assert api.post("/api/route", json={"mensaje": "hola"}).json()["ruta"] == "directo"


def test_flujo_del_pitch_visitante(api):
    """Primer paso del pitch: el visitante pide conocer la empresa y recibe la infografía con fuentes."""
    r = api.post(
        "/api/chat",
        json={"mensaje": "¿Qué es Riopaila Castilla en cifras?", "user_id": "573009998877", "canal": "whatsapp"},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["content"].strip() and cuerpo["ruta"]["ruta"] == "datos" and cuerpo["rol"] == "invitado"
    if not DESPLEGADO:
        assert "infografia_riopaila" in [h["name"] for h in cuerpo["herramientas"]]
    for m in cuerpo["media"]:  # cada imagen que se enviaría por WhatsApp se puede descargar
        assert api.get(m["url"]).status_code == 200


def test_webhook_handshake(api):
    r = api.get(
        "/api/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "no", "hub.challenge": "1"}
    )
    assert r.status_code == 403  # sin el verify token correcto no hay handshake
    token = os.environ.get("E2E_WHATSAPP_VERIFY_TOKEN", "token-de-prueba" if not DESPLEGADO else "")
    if token:
        r = api.get(
            "/api/webhook/whatsapp",
            params={"hub.mode": "subscribe", "hub.verify_token": token, "hub.challenge": "reto-123"},
        )
        assert r.status_code == 200 and r.text == "reto-123"


def test_webhook_post_simulado_responde_200(api):
    r = api.post("/api/webhook/whatsapp", json=PAYLOAD_WHATSAPP)
    assert r.status_code == 200 and r.json() == {"recibidos": 1}
    # Un evento de estado (entregado/leído) no trae mensajes: 200 y nada que atender.
    estado = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"statuses": [{}]}}]}]}
    assert api.post("/api/webhook/whatsapp", json=estado).json() == {"recibidos": 0}
    assert api.post("/api/webhook/whatsapp", content=b"{no es json").status_code == 400

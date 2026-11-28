# QA end-to-end con Playwright (anuncio 008)

Auditoría automática de **la app, la API y el webhook** antes de la sustentación. Playwright no entra a WhatsApp: la
conversación real se prueba desde el teléfono del invitado; lo que se automatiza es todo lo demás.

## Qué se audita (`tests/e2e/`)

| Lo que pide el anuncio 008 | Prueba | Cómo se verifica |
|---|---|---|
| **Flujo del pitch:** abrir la app, hacer la pregunta, ver la respuesta **con citas** y **la tool ejecutada** | `test_web.py::test_flujo_del_pitch_en_la_web` | pregunta del corpus → pestaña *Fuentes* con `[n]` → pestaña *Herramientas* con `buscar_documentos`; luego *“¿Qué es Riopaila Castilla en cifras?”* → infografía visible |
| **Consola sin errores** y **sin 404/500** en la red | mismo test | escucha `console`, `pageerror` y cada respuesta HTTP ≥ 400 en el chat y en *Datos*, *Memoria*, *Arquitectura* y *Evaluación* |
| **Webhook:** POST simulado con el payload de WhatsApp → **200** | `test_api_webhook.py::test_webhook_post_simulado_responde_200` | payload de Cloud API → `{"recibidos": 1}`; evento de estado → `0`; JSON inválido → 400 |
| Handshake del webhook | `test_webhook_handshake` | verify token incorrecto → 403; correcto → devuelve `hub.challenge` |
| **Teléfono (390 × 844) y escritorio** | el test web corre parametrizado en ambos | además falla si aparece scroll horizontal |
| Endpoints del backend | `test_salud_y_catalogo_de_herramientas`, `test_endpoints_de_la_app`, `test_flujo_del_pitch_visitante` | salud, ≥ 20 herramientas, LLM en la nube, indicadores, grafo, router, perfil visitante con infografía descargable |
| **Los tests en `tests/e2e/` y se corren antes de cada push** | CI (`.github/workflows/ci.yml`, job `e2e`) + hook `.githooks/pre-push` | el CI compila la web, instala Chromium y corre la QA en cada push y PR; sube capturas y trazas como artefacto |

## Cómo correrla

```bash
uv run playwright install chromium            # una vez
cd frontend && pnpm build && cd ..            # la web se sirve desde el mismo API
uv run pytest tests/e2e -v                    # local: API con modelo guionado y corpus indexado
git config core.hooksPath .githooks           # opcional: QA automática antes de cada git push

# Contra la app desplegada en Google Cloud (DeepSeek real), desde el servidor:
E2E_BASE_URL=http://127.0.0.1:8000 uv run pytest tests/e2e -v
```

Capturas y trazas quedan en `tests/e2e/artifacts/` (fuera del repo); la traza se abre paso a paso con
`uv run playwright show-trace tests/e2e/artifacts/traza_telefono.zip`.

## Resultados

| Fecha | Dónde | Resultado |
|---|---|---|
| 27-nov-2026 | Servidor `taller-castilla` (Google Cloud), app desplegada con DeepSeek | **7 passed** en 16,3 s |
| 27-nov-2026 | Local con modelo guionado (flujo con citas y tool) | **7 passed** |

**Bugs que encontró la QA antes del sábado** (para eso es):

1. `GET /api/eval/retrieval` respondía **404**: la evaluación del retrieval del M2 nunca se había generado. Ahora la
   genera `deploy/scripts/04_actualizar.sh` en el servidor.
2. En modo desplegado la fixture `base_url` no cedía la URL (`did not yield a value`) y ninguna prueba corría.
3. Las herramientas nuevas de la vitrina salían sin nombre legible en el inspector de la web.

## Evidencia

| Teléfono: respuesta con la tool ejecutada | Escritorio: infografía de la vitrina y la tool en el inspector |
|---|---|
| ![QA en teléfono](qa/qa_citas_telefono.png) | ![QA en escritorio](qa/qa_pitch_escritorio.png) |

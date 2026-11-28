# Despliegue del Asistente del Taller Castilla (Google Cloud + OpenClaw + WhatsApp)

Guía para dejar el bot respondiendo por WhatsApp desde un **número real**, en un **servidor real** (no localhost),
con el modelo por **API en la nube**. Tiempo estimado: 60–90 minutos la primera vez.

## 0. Qué necesitas

| Qué | Para qué | Dónde |
|---|---|---|
| Cuenta de Google Cloud con facturación (créditos de prueba sirven) | la máquina virtual | console.cloud.google.com |
| **API key de DeepSeek** con saldo (USD 5 alcanzan) | modelo principal (gateway y agente) | platform.deepseek.com |
| **API key de Gemini** | respaldo, visión de fotos y transcripción de notas de voz | aistudio.google.com |
| **Celular con WhatsApp y un número dedicado** (SIM nueva o WhatsApp Business) | el número del bot; nunca el personal | — |
| Los 3 Excel de SAP y los PDF de manuales | datos reales (solo viven en el servidor) | tu computador |
| Números E.164 del taller (+57…) y de los invitados | lista blanca y permisos | — |

## 1. Crear la máquina virtual

Compute Engine → Instancias de VM → **Crear instancia**:

- Nombre `taller-castilla`, región `us-central1` (o `southamerica-east1`).
- Tipo **e2-standard-4** (4 vCPU, 16 GB) para la semana de la sustentación; luego se puede bajar a e2-standard-2.
- Disco de arranque: **Ubuntu 24.04 LTS**, 50 GB, SSD balanceado.
- Firewall: **no** marques HTTP/HTTPS. El bot no necesita puertos abiertos: WhatsApp conecta hacia afuera y la web se
  ve por túnel SSH.

Entra con el botón **SSH** de la consola.

## 2. Preparar el servidor

```bash
curl -fsSL https://raw.githubusercontent.com/JORGE-RIVAS19/riopaila-castilla-qa/main/deploy/scripts/01_preparar_servidor.sh -o 01.sh
bash 01.sh            # paquetes, Docker (sandbox), Node 24, uv, Ollama (solo embeddings), repo en /opt/riopaila
exit                  # vuelve a entrar por SSH para que apliquen el grupo docker y el PATH
```

## 3. Subir los datos reales y cargarlos

En la ventana SSH: ⚙️ → **Subir archivo** → los 3 Excel de SAP y todos los PDF de manuales. Quedan en tu carpeta home;
muévelos a `~/carga`:

```bash
mkdir -p ~/carga && mv ~/*.xlsx ~/*.XLSX ~/*.pdf ~/carga/ 2>/dev/null
cd /opt/riopaila && cp deploy/env.servidor.example .env && nano .env   # pega las keys y los números del taller
bash deploy/scripts/02_cargar_datos.sh ~/carga
```

El script construye `data/taller/taller.duckdb` (≈20 s), copia los manuales con su nombre estable, extrae 5.217 páginas
con OCR de los escaneados (≈2 min) y vectoriza corpus y manuales en Qdrant con embeddings locales (≈20–40 min en CPU).

## 4. OpenClaw, WhatsApp y servicios

```bash
cp deploy/numeros.env.example deploy/numeros.env && nano deploy/numeros.env   # lista blanca, taller, parte diario
bash deploy/scripts/03_configurar_openclaw.sh
```

El script instala OpenClaw (versión fija), los plugins de WhatsApp y DeepSeek, pide las keys (quedan en
`~/.openclaw/.env`, permisos 600), copia el workspace (SOUL, AGENTS, USER, MEMORY, bitácora y skill), genera
`~/.openclaw/openclaw.json` desde la plantilla endurecida, levanta el API como servicio systemd, instala el gateway
como servicio y muestra el **QR**: escanéalo desde el celular del bot en *WhatsApp → Dispositivos vinculados*.
Al final programa el parte diario de las 6:00 a. m. y corre `openclaw security audit`.

## 5. Verificar (la prueba de 3 minutos)

```bash
bash deploy/scripts/verificar.sh
openclaw logs --follow      # y escríbele al bot desde el teléfono de un invitado
```

Ver la torre de control web desde tu portátil (túnel SSH, nada expuesto a internet):

```bash
gcloud compute ssh taller-castilla -- -L 8000:127.0.0.1:8000 -L 18789:127.0.0.1:18789
# API y docs: http://127.0.0.1:8000/docs · Control UI de OpenClaw: http://127.0.0.1:18789
```

## 6. Operación y contingencia

| Síntoma | Qué hacer |
|---|---|
| El bot no responde | `openclaw gateway status` · `openclaw channels status --probe` · `sudo systemctl status riopaila-api` |
| WhatsApp desvinculado | `openclaw channels login --channel whatsapp` y escanear de nuevo |
| DeepSeek sin saldo / 429 | el agente cae solo a Gemini (`LLM_FALLBACK_PROVIDER`); en OpenClaw, `fallbacks` del modelo |
| Qdrant ocupado al reindexar | `sudo systemctl stop riopaila-api` antes de `scripts/index_manuales.py` |
| Se cae la VM | la memoria está en disco (SQLite + workspace): al reiniciar, systemd levanta API y gateway |
| Plan B en la sustentación | segundo celular vinculado como respaldo + la web por túnel; si todo falla, se muestra el repo y los logs |

Actualizar el código: `cd /opt/riopaila && git pull && uv sync --locked && sudo systemctl restart riopaila-api`.

Después de la sustentación: rota las keys (DeepSeek, Gemini, LangSmith), baja la VM a e2-standard-2 o elimínala.

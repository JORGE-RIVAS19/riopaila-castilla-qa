#!/usr/bin/env bash
# Paso 3 · Instala OpenClaw, el workspace del taller, la configuración endurecida, el API y el parte diario.
# Antes: llena deploy/numeros.env (copia de numeros.env.example) y ten a mano las keys de DeepSeek y Gemini.
# Uso:  bash 03_configurar_openclaw.sh
set -euo pipefail
OPENCLAW_VERSION="${OPENCLAW_VERSION:-2026.11.2}"
REPO=/opt/riopaila
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
UV="$(command -v uv)"
cd "$REPO"
source deploy/numeros.env

echo "==> OpenClaw $OPENCLAW_VERSION + plugins de WhatsApp y DeepSeek"
npm install -g "openclaw@$OPENCLAW_VERSION" --allow-scripts=openclaw
openclaw plugins install @openclaw/whatsapp
openclaw plugins install @openclaw/deepseek-provider

echo "==> Secretos en ~/.openclaw/.env (no se versiona)"
mkdir -p "$HOME/.openclaw" && chmod 700 "$HOME/.openclaw"
if [ ! -f "$HOME/.openclaw/.env" ]; then
  read -rsp "DEEPSEEK_API_KEY: " DS; echo
  read -rsp "GEMINI_API_KEY: " GM; echo
  printf 'DEEPSEEK_API_KEY=%s\nGEMINI_API_KEY=%s\nOPENCLAW_GATEWAY_TOKEN=%s\n' "$DS" "$GM" "$(openssl rand -hex 32)" > "$HOME/.openclaw/.env"
  chmod 600 "$HOME/.openclaw/.env"
fi

echo "==> Workspace (SOUL, AGENTS, USER, MEMORY, bitácora y skill)"
WS="$HOME/.openclaw/workspace"
mkdir -p "$WS/memory" "$WS/skills" "$WS/media"
for f in SOUL.md AGENTS.md USER.md MEMORY.md; do cp -n "deploy/openclaw/workspace/$f" "$WS/$f"; done
cp -rn deploy/openclaw/workspace/memory/. "$WS/memory/"
cp -rn deploy/openclaw/workspace/skills/. "$WS/skills/"

echo "==> openclaw.json desde la plantilla"
comillas() { echo "$1" | tr ',' '\n' | sed 's/.*/"&"/' | paste -sd, -; }
STAFF_TOOLS=""
for n in $(echo "$STAFF" | tr ',' ' '); do STAFF_TOOLS+="\"e164:$n\": {}, "; done
sed -e "s|__ALLOW_FROM__|$(comillas "$ALLOW_FROM")|" \
    -e "s|__STAFF_TOOLS__|$STAFF_TOOLS|" \
    -e "s|__UV__|$UV|" -e "s|__REPO__|$REPO|g" \
    -e "s|__MODELO_GEMINI__|${MODELO_GEMINI:-gemini-3.6-flash}|g" \
    deploy/openclaw/openclaw.json5 > "$HOME/.openclaw/openclaw.json"
chmod 600 "$HOME/.openclaw/openclaw.json"
openclaw config validate || true

echo "==> API del agente como servicio (systemd)"
sed -i "s|^MEDIA_DIR=.*|MEDIA_DIR=$WS/media|" .env
sed -e "s|__USUARIO__|$USER|" -e "s|__REPO__|$REPO|g" -e "s|__UV__|$UV|" deploy/systemd/riopaila-api.service \
  | sudo tee /etc/systemd/system/riopaila-api.service >/dev/null
sudo systemctl daemon-reload && sudo systemctl enable --now riopaila-api
# El API tarda en cargar modelos e índices: espera hasta 2 min sin abortar el script.
for _ in $(seq 1 40); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null; then break; fi
  sleep 3
done
curl -s http://127.0.0.1:8000/api/health | jq '.llm, .taller' || echo "AVISO: el API aún no responde; revisa 'sudo systemctl status riopaila-api'"

echo "==> Imagen del sandbox de OpenClaw (sin ella el agente falla con 'Sandbox image not found')"
if ! docker image inspect openclaw-sandbox:bookworm-slim >/dev/null 2>&1; then
  docker build -t openclaw-sandbox:bookworm-slim - <<'DOCKERFILE'
FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
  bash ca-certificates curl git jq python3 ripgrep \
  && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash sandbox
USER sandbox
WORKDIR /home/sandbox
CMD ["sleep", "infinity"]
DOCKERFILE
fi

echo "==> Gateway como servicio + vincular WhatsApp (escanea el QR con el celular del BOT)"
sudo loginctl enable-linger "$USER"   # el servicio de usuario sigue vivo al cerrar la sesión SSH
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
# systemd --user rechaza unidades en carpetas escribibles por el grupo (SERVICE_DEFINITION_UNKNOWN).
chmod go-w "$HOME"
mkdir -p "$HOME/.config/systemd/user"
chmod 700 "$HOME/.config" "$HOME/.config/systemd" "$HOME/.config/systemd/user"
openclaw gateway install --force
openclaw channels login --channel whatsapp
openclaw channels status --probe
openclaw mcp doctor || true
echo "IMPORTANTE: WhatsApp oculta el número de quien escribe por primera vez (LID). Desde el celular del BOT"
echo "escríbele 'hola' a cada número del taller y de los invitados antes de que ellos le escriban."

echo "==> Parte diario a las 6:00 a.m. (lunes a sábado)"
for n in $(echo "$PARTE_DIARIO_A" | tr ',' ' '); do
  openclaw automations add --name "Parte diario taller ($n)" --cron "0 6 * * 1-6" --tz "America/Bogota" \
    --session isolated --announce --channel whatsapp --to "$n" \
    --message "Llama taller-riopaila__parte_diario_taller(dias=7) y envía el texto tal cual con su gráfica (línea MEDIA:)." || true
done

echo "==> Auditoría de seguridad"
openclaw security audit

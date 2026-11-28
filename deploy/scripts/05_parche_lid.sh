#!/usr/bin/env bash
# Paso 5 · Ajuste del plugin de WhatsApp de OpenClaw para remitentes con número oculto (LID).
#
# Problema (visto en la VM el 27-nov-2026): cuando WhatsApp no le entrega al bot el número de quien escribe
# (usuarios con nombre de usuario, o primer contacto sin chat previo), el plugin lanza
# "WhatsApp inbound LID identity unavailable" y descarta el mensaje ANTES de mirar dmPolicy. Ni "open" lo evita.
# Ajuste: si no hay número, usar el identificador LID como identidad. El bot responde a ese mismo chat y, como ese
# remitente no está en TALLER_ROLES ni en toolsBySender, entra como visitante (muestra anonimizada, sin escritura).
# Ver docs/adr/ADR-012-whatsapp-abierto-lid.md.
#
#   bash deploy/scripts/05_parche_lid.sh            # aplica (idempotente) y reinicia el gateway
#   bash deploy/scripts/05_parche_lid.sh --revertir # restaura el original (.orig) y reinicia
#   bash deploy/scripts/05_parche_lid.sh --sin-reiniciar  # lo usa 03_configurar_openclaw.sh antes de instalar el gateway
set -uo pipefail
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"

ORIGINAL='const from = group ? remoteJid : await socketSession.resolveInboundJid(remoteJid);'
AJUSTADO='const from = group ? remoteJid : ((await socketSession.resolveInboundJid(remoteJid)) ?? ((remoteJid.endsWith("@lid") || remoteJid.endsWith("@hosted.lid")) ? remoteJid : null));'

# Solo el plugin instalado (nunca la base SQLite de estado ni las copias temporales de ~/.openclaw/tmp).
mapfile -t ARCHIVOS < <(grep -rl --include="*.mjs" "WhatsApp inbound LID identity unavailable" "$HOME/.openclaw/npm" 2>/dev/null)
if [ "${#ARCHIVOS[@]}" -eq 0 ]; then
  echo "No encontré el plugin de WhatsApp en ~/.openclaw/npm (¿está instalado?)."; exit 1
fi

for f in "${ARCHIVOS[@]}"; do
  if [ "${1:-}" = "--revertir" ]; then
    [ -f "$f.orig" ] && cp "$f.orig" "$f" && echo "Revertido: $f"
    continue
  fi
  if grep -qF "$AJUSTADO" "$f"; then
    echo "Ya estaba ajustado: $f"; continue
  fi
  if ! grep -qF "$ORIGINAL" "$f"; then
    echo "AVISO: esta versión del plugin no tiene la línea esperada; no toco $f"; continue
  fi
  cp "$f" "$f.orig"
  python3 - "$f" "$ORIGINAL" "$AJUSTADO" <<'PY'
import sys
ruta, original, ajustado = sys.argv[1:4]
texto = open(ruta, encoding="utf-8").read()
open(ruta, "w", encoding="utf-8").write(texto.replace(original, ajustado, 1))
PY
  if node --check "$f"; then
    echo "Ajustado: $f"
  else
    cp "$f.orig" "$f"; echo "ERROR de sintaxis: restauré el original de $f"; exit 1
  fi
done

[ "${1:-}" = "--sin-reiniciar" ] && exit 0
openclaw gateway restart
sleep 15
openclaw channels status --probe

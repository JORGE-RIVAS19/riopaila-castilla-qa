#!/usr/bin/env bash
# Paso 4 · Actualiza el servidor a una rama nueva SIN reinstalar nada, con vuelta atrás en un comando.
#
#   bash deploy/scripts/04_actualizar.sh                         # trae la rama desde GitHub
#   bash deploy/scripts/04_actualizar.sh ~/riopaila-m3.bundle     # o desde un bundle subido por SSH
#   bash deploy/scripts/04_actualizar.sh --volver                 # deshace: rama anterior y AGENTS.md anterior
#
# Qué hace: cambia de rama, uv sync, compila la web (si hay pnpm), genera la evaluación del retrieval del M2,
# actualiza AGENTS.md del workspace (guarda copia), reinicia API y gateway, y corre la QA con Playwright.
set -uo pipefail
RAMA="${RAMA:-feat/m3-perfiles-visitante}"
REPO=/opt/riopaila
WS="$HOME/.openclaw/workspace"
ESTADO="$HOME/.riopaila_actualizacion"
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
export COREPACK_ENABLE_DOWNLOAD_PROMPT=0
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
cd "$REPO"

esperar_api() {
  for _ in $(seq 1 60); do curl -sf http://127.0.0.1:8000/api/health >/dev/null && return 0; sleep 3; done
  echo "AVISO: el API no responde aún: sudo journalctl -u riopaila-api -n 50"; return 1
}

if [ "${1:-}" = "--volver" ]; then
  [ -f "$ESTADO" ] || { echo "No hay una actualización que deshacer."; exit 1; }
  ANTERIOR="$(cat "$ESTADO")"
  echo "==> Volviendo a $ANTERIOR"
  git checkout "$ANTERIOR" && uv sync --locked
  [ -f "$WS/AGENTS.md.anterior" ] && cp "$WS/AGENTS.md.anterior" "$WS/AGENTS.md"
  sudo systemctl restart riopaila-api && openclaw gateway restart
  esperar_api && curl -s http://127.0.0.1:8000/api/health | jq '{llm, herramientas: (.herramientas|length)}'
  exit 0
fi

echo "==> Rama $RAMA"
git rev-parse --abbrev-ref HEAD > "$ESTADO"
if [ -n "${1:-}" ]; then
  git fetch "$1" "+refs/heads/$RAMA:refs/heads/$RAMA" || exit 1
else
  git fetch origin "+refs/heads/$RAMA:refs/remotes/origin/$RAMA" || exit 1
  git branch -f "$RAMA" "origin/$RAMA" 2>/dev/null || true
fi
git checkout "$RAMA" || exit 1
uv sync --locked || exit 1

echo "==> Web (torre de control) compilada para servirla desde el API"
if command -v corepack >/dev/null; then
  (cd frontend && corepack pnpm install --frozen-lockfile && corepack pnpm build) || echo "AVISO: no compiló la web"
fi

echo "==> Evaluación del retrieval del M2 (Qdrant local: se detiene el API mientras corre)"
sudo systemctl stop riopaila-api
uv run python scripts/eval_retrieval.py || echo "AVISO: falló la evaluación del retrieval"
sudo systemctl start riopaila-api

echo "==> Workspace de OpenClaw: AGENTS.md con el menú de visitante (copia en AGENTS.md.anterior)"
cp "$WS/AGENTS.md" "$WS/AGENTS.md.anterior" 2>/dev/null || true
cp deploy/openclaw/workspace/AGENTS.md "$WS/AGENTS.md"
openclaw gateway restart

echo "==> Estado"
esperar_api
curl -s http://127.0.0.1:8000/api/health | jq '{llm, taller: {activo: .taller.activo, muestra_visitantes: .taller.muestra_visitantes}, herramientas: (.herramientas|length)}'

echo "==> QA con Playwright contra la app desplegada"
uv run playwright install --with-deps chromium >/dev/null 2>&1 || echo "AVISO: no se pudo instalar Chromium"
E2E_BASE_URL=http://127.0.0.1:8000 uv run pytest tests/e2e -q -p no:cacheprovider
echo "Capturas y trazas: $REPO/tests/e2e/artifacts/  ·  Para deshacer: bash deploy/scripts/04_actualizar.sh --volver"

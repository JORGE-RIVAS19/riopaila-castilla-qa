#!/usr/bin/env bash
# Paso 1 · Prepara una VM Ubuntu 24.04 de Google Cloud: paquetes, Docker (sandbox), Node 24, uv, Ollama y el repo.
# Uso:  bash 01_preparar_servidor.sh
set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/JORGE-RIVAS19/riopaila-castilla-qa.git}"
RAMA="${RAMA:-main}"
REPO=/opt/riopaila

echo "==> Paquetes base"
sudo apt-get update -y
sudo apt-get install -y git curl ca-certificates build-essential jq tesseract-ocr tesseract-ocr-spa ffmpeg

echo "==> Docker (sandbox de OpenClaw)"
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sudo sh; fi
sudo usermod -aG docker "$USER"

echo "==> Node 24 (requisito de OpenClaw)"
if ! node -v 2>/dev/null | grep -q '^v2[4-9]'; then
  curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
mkdir -p "$HOME/.npm-global" && npm config set prefix "$HOME/.npm-global"
grep -q npm-global "$HOME/.bashrc" || echo 'export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"

echo "==> uv"
if ! command -v uv >/dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then curl -LsSf https://astral.sh/uv/install.sh | sh; fi
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"

echo "==> Ollama (solo para embeddings locales)"
if ! command -v ollama >/dev/null; then curl -fsSL https://ollama.com/install.sh | sh; fi
sudo systemctl enable --now ollama
ollama pull nomic-embed-text-v2-moe

echo "==> Repositorio en $REPO (rama $RAMA)"
sudo mkdir -p "$REPO" && sudo chown "$USER":"$USER" "$REPO"
if [ ! -d "$REPO/.git" ]; then git clone --branch "$RAMA" "$REPO_URL" "$REPO"; else git -C "$REPO" pull --ff-only; fi
cd "$REPO" && uv sync --locked

echo "==> Listo. Cierra la sesión SSH y vuelve a entrar (para que el grupo docker y el PATH apliquen)."

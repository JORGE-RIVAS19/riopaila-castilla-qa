#!/usr/bin/env bash
# Paso 2 · Carga los datos reales (solo en el servidor): base SAP, manuales con OCR e índices Qdrant.
# Antes: sube a ~/carga los 3 Excel de SAP y los PDF de manuales (botón "Subir archivo" de la consola SSH).
# Uso:  bash 02_cargar_datos.sh [~/carga]
set -euo pipefail
CARGA="${1:-$HOME/carga}"
REPO=/opt/riopaila
export PATH="$HOME/.local/bin:$PATH"
cd "$REPO"
[ -f .env ] || { echo "Falta $REPO/.env (copia deploy/env.servidor.example y llena las keys)"; exit 1; }
sudo systemctl stop riopaila-api 2>/dev/null || true   # Qdrant embebido: un solo proceso a la vez

echo "==> Base del taller (DuckDB) desde SAP"
mkdir -p data/taller
uv run python scripts/build_taller.py \
  --equipos "$(ls "$CARGA"/*EQUIPOS*.xlsx | head -1)" \
  --historial "$(ls "$CARGA"/*HISTORIAL*.[xX][lL][sS][xX] | head -1)" \
  --materiales "$(ls "$CARGA"/*MATERIALES*.xlsx | head -1)" \
  --destino data/taller/taller.duckdb

echo "==> Manuales: nombres estables + páginas (OCR de los escaneados)"
uv run python scripts/preparar_manuales.py "$CARGA" data/manuales

echo "==> Índice del corpus público (M2) y de los manuales (M3) en Qdrant"
uv run python scripts/build_index.py
uv run python scripts/index_manuales.py

sudo systemctl start riopaila-api 2>/dev/null || true
echo "==> Datos cargados."

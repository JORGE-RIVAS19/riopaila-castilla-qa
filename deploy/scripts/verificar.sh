#!/usr/bin/env bash
# La prueba de 3 minutos del Anuncio 007 (correr el viernes en la noche y el sábado a las 7:30 a.m.).
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
cd /opt/riopaila
echo "--- API";      curl -s http://127.0.0.1:8000/api/health | jq '{llm, taller, herramientas: (.herramientas|length)}'
echo "--- Gateway";  openclaw gateway status
echo "--- Canales";  openclaw channels status --probe
echo "--- MCP";      openclaw mcp doctor || true
echo "--- Auditoría"; openclaw security audit
echo "--- Git";      git log --oneline --graph -10 && git status --short
echo "Ahora escríbele al bot desde el teléfono de un invitado y mira: openclaw logs --follow"

# Arquitectura verificable con Archify

`candidate.json` describe la arquitectura del Módulo 3 (17 componentes, 17 relaciones, 4 tarjetas). Cada componente
cita el archivo y las líneas del repositorio que lo prueban, fijados a un commit (`meta.repository.revision`), así que
Archify puede **verificar** que el diagrama dice la verdad del código antes de publicarlo.

## Generar el HTML (Windows, PowerShell, en la carpeta del repo)

```powershell
git clone https://github.com/tt-a1i/archify $HOME\archify
git -C $HOME\archify checkout v3.2.0          # versión fija (publicada el 18-oct-2026)
git fetch origin; git checkout main; git pull  # el commit citado debe existir localmente
node $HOME\archify\archify\bin\archify.mjs finalize architecture docs/arquitectura/candidate.json `
  docs/arquitectura/arquitectura_m3.html --repo-root . --quality showcase --json
```

`finalize` valida el esquema, publica el HTML, revisa la procedencia de cada fuente contra el commit y abre Chrome/Edge
en privado para el chequeo de legibilidad. Si todo pasa, `docs/arquitectura/arquitectura_m3.html` queda listo (modo
claro/oscuro, animación, exportar a SVG/PNG). Súbelo con un PR (`docs/archify-m3`).

Si falla un gate, el JSON de salida dice cuál (`evidence.summaryReceipt`); los ajustes son de posición (`pos`/`size`)
o de etiquetas, nunca del contenido.
